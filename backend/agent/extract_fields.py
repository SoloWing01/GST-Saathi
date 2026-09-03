"""LLM-based field extraction from raw GST/tax notice text.

Uses the dual LLM client (Groq primary, Gemini fallback) to extract
structured fields from notice text. Validates the output against
Pydantic models and flags low-confidence extractions.
"""

from __future__ import annotations

import json
import logging
import re

from agent.llm_client import llm_complete
from agent.models import ExtractedFields, ExtractionResult

log = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """\
You are a precise data-extraction assistant for Indian GST/tax notices.

Given the raw text of a GST notice, extract these fields into a JSON object:
{
  "notice_type": "string — e.g. ASMT-10, DRC-01, REG-17, GSTR-3A, etc.",
  "gstin": "string — 15-character GST Identification Number",
  "tax_period": "string — the tax period mentioned, e.g. 'April 2024 - June 2024'",
  "amount": "number — the amount in question in INR (numeric only, no commas or currency symbol)",
  "section_cited": "string — section/rule of CGST Act cited, e.g. 'Section 61', 'Section 73', 'Rule 36(4)'",
  "due_date": "string — deadline for reply, e.g. '30 days from receipt' or '15-Feb-2025'"
}

Rules:
- Return ONLY the JSON object, no markdown fences, no explanation, no thinking.
- Do NOT use <think> tags. Output ONLY the JSON.
- If a field cannot be found in the text, use null for that field.
- For amount, extract the total disputed/demand amount as a number (e.g. 90000, not "Rs. 90,000").
- If multiple amounts appear, use the total demand amount.
- gstin must be exactly 15 characters (2 digit state code + 10 char PAN + 1 char Z + 1 char checksum).
- notice_type should be the short code (e.g. "ASMT-10"), not the full description.
"""

EXTRACTION_USER_PROMPT = """\
Extract the structured fields from this GST/tax notice:

---
{notice_text}
---

Return ONLY a JSON object with the 6 fields. Use null for any field you cannot determine."""


def _parse_json_response(raw: str) -> dict:
    """Extract a JSON object from LLM response, handling markdown fences and thinking tags."""
    text = raw.strip()

    # Strip <think>...</think> blocks (some models like Qwen output these)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Also handle unclosed <think> tags (model ran out of tokens before closing)
    text = re.sub(r"<think>[\s\S]*$", "", text).strip()

    # Try to extract from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find the first { ... } block
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {raw[:200]}")


def _assess_confidence(fields_dict: dict) -> tuple[str, list[str]]:
    """Assess extraction confidence based on which fields were found.

    Returns:
        Tuple of (overall_confidence, list_of_missing_field_names).
    """
    required_fields = ["notice_type", "gstin", "tax_period", "amount", "section_cited", "due_date"]
    missing = []
    uncertain = []

    for field in required_fields:
        value = fields_dict.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            missing.append(field)
        elif field == "gstin" and isinstance(value, str):
            # Validate GSTIN format: 15 chars, alphanumeric
            clean = value.replace(" ", "").upper()
            if len(clean) != 15 or not clean.isalnum():
                uncertain.append(field)
                fields_dict[field] = clean  # Store cleaned version
        elif field == "amount" and (not isinstance(value, (int, float)) or value <= 0):
            uncertain.append(field)

    if len(missing) >= 3:
        return "low", missing
    elif len(missing) >= 1 or len(uncertain) >= 2:
        return "medium", missing + uncertain
    else:
        return "high", []


async def extract_notice_fields(notice_text: str, tenant_id: str = "default") -> ExtractionResult:
    """Extract structured fields from raw notice text using the dual LLM.

    Args:
        notice_text: Raw text extracted from the notice (PDF, OCR, or pasted).
        tenant_id: Tenant/session id whose credentials should be used.

    Returns:
        ExtractionResult with fields, confidence, and provider info.

    Raises:
        RuntimeError: If LLM call fails on all providers.
        ValueError: If the notice text is empty or too short.
    """
    if not notice_text or len(notice_text.strip()) < 20:
        raise ValueError("Notice text is too short to extract fields from.")

    prompt = EXTRACTION_USER_PROMPT.format(notice_text=notice_text[:4000])  # Truncate very long notices

    log.info("Calling LLM for field extraction (%d chars of notice text)", len(notice_text))
    raw_response, provider_used = await llm_complete(
        prompt=prompt,
        system=EXTRACTION_SYSTEM_PROMPT,
        temperature=0.0,  # Deterministic extraction
        max_tokens=4096,
        tenant_id=tenant_id,
    )
    log.info("LLM response received from provider: %s (%d chars)", provider_used, len(raw_response))

    # Parse the JSON response
    fields_dict = _parse_json_response(raw_response)

    # Assess confidence
    overall_confidence, missing_fields = _assess_confidence(fields_dict)

    # Build the ExtractedFields model (populate raw_text separately)
    fields_dict.pop("raw_text", None)  # Don't let LLM set this
    fields = ExtractedFields(**fields_dict, raw_text=notice_text)

    return ExtractionResult(
        fields=fields,
        confidence=overall_confidence,
        extraction_confidence=overall_confidence,
        missing_fields=missing_fields,
        provider_used=provider_used,
    )
