"""Phase 5 — Reasoning agent that generates the four-part explanation.

Combines extracted notice fields + matched transactions + KB entry into
a plain-language explanation with citations, confidence scoring, and
a low-confidence fallback path.

Four parts:
1. What it means — plain-language summary of the notice
2. Why you got it — tied to specific transaction IDs and amounts
3. What to do next — actionable steps with deadlines
4. Confidence level — how sure we are, with sources cited

Every factual claim carries a citation (transaction ID or KB source).
No unsourced claims — this is non-negotiable per docs/Rules.md.
"""

from __future__ import annotations

import json
import logging
import re

from agent.llm_client import llm_complete
from agent.models import (
    Citation,
    CrossReferenceResult,
    Explanation,
    ExplanationSection,
    ExtractedFields,
    ReasoningResult,
)

log = logging.getLogger(__name__)

REASONING_SYSTEM_PROMPT = """\
You are a GST/tax compliance expert explaining notices to small merchants in India.

You will receive:
1. Extracted fields from a GST notice
2. Matched transactions from the merchant's payment history
3. A matched GST rule/knowledge base entry

Generate a plain-language explanation with exactly 4 sections. Return ONLY a JSON object.

JSON structure:
{
  "what_it_means": {
    "title": "What This Notice Means",
    "content": "2-3 paragraph plain-language explanation. No jargon. Explain like talking to a non-accountant.",
    "citations": [{"claim": "...", "source": "KB:filename.md", "source_type": "kb_entry"}]
  },
  "why_you_got_it": {
    "title": "Why You Likely Got This Notice",
    "content": "Explain the likely trigger, referencing specific transaction IDs and amounts from the matched transactions. If flagged mismatches exist, explain them.",
    "citations": [{"claim": "...", "source": "pay_xxxxx", "source_type": "transaction"}]
  },
  "what_to_do": {
    "title": "What To Do Next",
    "content": "Step-by-step actionable instructions with deadlines. Number the steps.",
    "citations": [{"claim": "...", "source": "KB:filename.md", "source_type": "kb_entry"}]
  },
  "confidence": {
    "title": "Confidence & Disclaimer",
    "content": "Explain how confident you are in this analysis and why. Always add: 'This is not legal advice. Consult a qualified CA for your specific situation.'",
    "citations": []
  }
}

Rules:
- Return ONLY the JSON object, no markdown fences, no explanation.
- Do NOT use <think> tags.
- Every factual claim MUST have at least one citation.
- Use plain language — the merchant is NOT an accountant.
- Never state legal conclusions as certain. Use "likely", "based on available information".
- If transactions are missing for the period, say so — don't invent data.
- If confidence is low, say so explicitly and recommend consulting a CA.
- For "why you got it", if you see flagged mismatches (timing lag, unreconciled refund, etc.), explain what they mean in simple terms.
"""

REASONING_USER_PROMPT = """\
Explain this GST notice to the merchant.

## Notice Fields
- Notice Type: {notice_type}
- GSTIN: {gstin}
- Tax Period: {tax_period}
- Amount in Question: Rs. {amount:,.0f}
- Section Cited: {section_cited}
- Reply Due: {due_date}

## Matched Transactions ({txn_count} total, {flagged_count} flagged)
{transactions_text}

## GST Rule (from Knowledge Base)
{kb_text}

Generate the 4-part explanation as a JSON object."""

CA_ESCALATION_TEMPLATE = (
    "IMPORTANT: Our analysis has low confidence for this notice. "
    "We could not reliably determine the full context. "
    "We strongly recommend you consult a qualified Chartered Accountant (CA) "
    "before taking any action. This is not legal advice — a CA can review your "
    "specific situation and provide authoritative guidance."
)

def _parse_json_response(raw: str) -> dict:
    """Extract a JSON object from LLM response.

    Handles <think> tags from Qwen models — strips everything between
    opening and closing <think> (including nested tags), then extracts JSON.
    """
    text = raw.strip()

    # Aggressively strip ALL <think> content — remove everything between
    # first <think> and last </think> (handles nested tags from Qwen)
    first_think = text.find("<think>")
    last_think_end = text.rfind("</think>")

    if first_think != -1 and last_think_end != -1 and last_think_end > first_think:
        # Remove entire block from first <think> to last </think>
        text = text[:first_think] + text[last_think_end + len("</think>"):]
        text = text.strip()
    elif first_think != -1 and last_think_end == -1:
        # Opening tag without closing — response was truncated mid-thinking
        # The JSON was never output. Signal to retry.
        raise ValueError("LLM response truncated during thinking — no JSON output")

    if not text:
        raise ValueError("No content after stripping think tags")

    # Try extracting from markdown fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding JSON object by brace matching
    brace_match = re.search(r"\{[\s\S]*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {raw[:200]}")


def _format_transactions_text(
    matched: list, flagged: list
) -> str:
    """Format matched transactions into a readable text block for the prompt."""
    if not matched:
        return "No transactions found in the database for this tax period."

    lines = []
    for t in matched[:10]:  # Limit to avoid prompt bloat / token limits
        flag = ""
        if any(f.payment_id == t.payment_id for f in flagged):
            flag = " [FLAGGED MISMATCH]"
        gstin_info = f", Payer GSTIN: {t.payer_gstin}" if t.payer_gstin else ""
        lines.append(
            f"- {t.payment_id}: Rs.{t.amount:,.0f} on {t.created_at[:10]}, "
            f"Status: {t.status}{gstin_info}{flag}"
        )

    if len(matched) > 10:
        lines.append(f"- ... and {len(matched) - 10} more transactions")

    return "\n".join(lines)


def _format_kb_text(kb_entry) -> str:
    """Format the KB entry into a readable text block for the prompt."""
    if kb_entry is None:
        return "No matching GST rule found in the knowledge base."

    return (
        f"Rule: {kb_entry.title}\n"
        f"Section: {kb_entry.section}\n"
        f"File: {kb_entry.filename}\n"
        f"Relevance: {kb_entry.similarity:.0%}\n\n"
        f"Full Rule Content:\n{kb_entry.content[:800]}"
    )


def _determine_overall_confidence(
    extraction_confidence: str,
    has_transactions: bool,
    has_kb: bool,
    flagged_count: int,
    llm_confidence_text: str,
) -> tuple[str, bool]:
    """Determine overall confidence based on all signals.

    Returns:
        Tuple of (confidence_level, is_low_confidence).
    """
    low_signals = 0

    if extraction_confidence == "low":
        low_signals += 2
    elif extraction_confidence == "medium":
        low_signals += 1

    if not has_transactions:
        low_signals += 1  # No transaction data to cross-reference

    if not has_kb:
        low_signals += 1  # No KB rule matched

    # Check LLM's own confidence assessment
    llm_lower = llm_confidence_text.lower()
    if any(w in llm_lower for w in ["low confidence", "not sure", "uncertain", "cannot determine"]):
        low_signals += 2
    elif any(w in llm_lower for w in ["medium confidence", "partially"]):
        low_signals += 1

    if low_signals >= 3:
        return "low", True
    elif low_signals >= 1:
        return "medium", False
    else:
        return "high", False


def _build_citations(raw_citations: list[dict]) -> list[Citation]:
    """Convert raw citation dicts into Citation models."""
    citations = []
    for c in raw_citations:
        if isinstance(c, dict) and "claim" in c and "source" in c:
            citations.append(Citation(
                claim=c["claim"],
                source=c["source"],
                source_type=c.get("source_type", "unknown"),
            ))
    return citations


def _parse_explanation(raw_json: dict) -> Explanation:
    """Parse the LLM's JSON response into an Explanation model."""
    sections = {}
    for key, title in [
        ("what_it_means", "What This Notice Means"),
        ("why_you_got_it", "Why You Likely Got This Notice"),
        ("what_to_do", "What To Do Next"),
        ("confidence", "Confidence & Disclaimer"),
    ]:
        section_data = raw_json.get(key, {})
        sections[key] = ExplanationSection(
            title=section_data.get("title", title),
            content=section_data.get("content", "Information not available."),
            citations=_build_citations(section_data.get("citations", [])),
        )

    return Explanation(**sections)


async def generate_explanation(
    fields: ExtractedFields,
    xref: CrossReferenceResult,
    extraction_confidence: str = "high",
    raw_text: str = "",
    tenant_id: str = "default",
) -> ReasoningResult:
    """Generate the four-part explanation using the reasoning LLM.

    Args:
        fields: Extracted notice fields from Phase 2.
        xref: Cross-reference results from Phase 4.
        extraction_confidence: Confidence from field extraction.
        raw_text: Original notice text (for context).
        tenant_id: Tenant/session id whose credentials should be used.

    Returns:
        ReasoningResult with explanation, confidence, and metadata.
    """
    # Build the prompt
    txn_text = _format_transactions_text(
        xref.matched_transactions, xref.flagged_transactions
    )
    kb_text = _format_kb_text(xref.kb_entry)

    prompt = REASONING_USER_PROMPT.format(
        notice_type=fields.notice_type if fields.notice_type else "Unknown",
        gstin=fields.gstin if fields.gstin else "Unknown",
        tax_period=fields.tax_period if fields.tax_period else "Unknown",
        amount=fields.amount if fields.amount is not None else 0,
        section_cited=fields.section_cited if fields.section_cited else "Unknown",
        due_date=fields.due_date if fields.due_date else "Not specified",
        txn_count=xref.total_transactions_in_period,
        flagged_count=len(xref.flagged_transactions),
        transactions_text=txn_text,
        kb_text=kb_text,
    )

    log.info("Calling LLM for explanation generation")

    # Retry loop — Qwen may truncate mid-thinking, so we retry on parse failure
    raw_json = None
    provider_used = "unknown"
    for attempt in range(3):
        raw_response, provider_used = await llm_complete(
            prompt=prompt,
            system=REASONING_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=8192,
            tenant_id=tenant_id,
        )
        log.info(
            "LLM response attempt %d: provider=%s, chars=%d",
            attempt + 1, provider_used, len(raw_response),
        )
        try:
            raw_json = _parse_json_response(raw_response)
            break
        except ValueError as e:
            if "truncated during thinking" in str(e):
                log.warning("Attempt %d: %s — retrying", attempt + 1, e)
                continue
            raise
    if raw_json is None:
        raise ValueError("All 3 attempts failed — LLM response truncated during thinking")

    explanation = _parse_explanation(raw_json)

    # Determine overall confidence
    has_transactions = xref.total_transactions_in_period > 0
    has_kb = xref.kb_entry is not None
    confidence_text = explanation.confidence.content

    overall_confidence, is_low = _determine_overall_confidence(
        extraction_confidence,
        has_transactions,
        has_kb,
        len(xref.flagged_transactions),
        confidence_text,
    )

    # Build CA escalation note for low confidence
    ca_note = CA_ESCALATION_TEMPLATE if is_low else ""

    return ReasoningResult(
        explanation=explanation,
        overall_confidence=overall_confidence,
        is_low_confidence=is_low,
        ca_escalation_note=ca_note,
        provider_used=provider_used,
    )
