"""Pydantic models for extracted notice fields, LLM responses, and cross-reference results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedFields(BaseModel):
    """Structured fields extracted from a GST/tax notice."""

    notice_type: str | None = Field(
        default=None, description="Type of notice, e.g. ASMT-10, DRC-01, REG-17, GSTR-3A"
    )
    gstin: str | None = Field(
        default=None, description="GST Identification Number of the recipient"
    )
    tax_period: str | None = Field(
        default=None, description="Tax period the notice refers to, e.g. 'April 2024 - June 2024'"
    )
    amount: float | None = Field(
        default=None, description="Amount in question (numeric, in INR)"
    )
    section_cited: str | None = Field(
        default=None, description="Section/rule of the CGST Act cited in the notice"
    )
    due_date: str | None = Field(
        default=None, description="Due date for reply, e.g. '30 days from receipt' or a specific date"
    )
    raw_text: str = Field(
        default="", description="Original raw text of the notice (populated after extraction)"
    )


class ExtractionResult(BaseModel):
    """Result of LLM-based field extraction, including confidence info."""

    fields: ExtractedFields
    confidence: str = Field(
        ...,
        description="Overall extraction confidence: 'high', 'medium', or 'low'",
    )
    extraction_confidence: str = Field(
        ...,
        description="Per-field confidence: 'high' if all fields extracted cleanly, "
        "'medium' if some fields approximated, 'low' if critical fields missing/uncertain",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="List of field names that could not be extracted or are uncertain",
    )
    provider_used: str = Field(
        default="unknown",
        description="Which LLM provider was used: 'groq' or 'google'",
    )


# ---------------------------------------------------------------------------
# Phase 4 — Cross-reference models
# ---------------------------------------------------------------------------


class MatchedTransaction(BaseModel):
    """A single transaction matched against the notice."""

    payment_id: str
    order_id: str
    amount: float
    status: str
    payer_gstin: str | None = None
    description: str | None = None
    created_at: str
    settled_at: str | None = None
    tax_period: str
    tax_amount: float
    refund_of: str | None = None
    refund_amount: float = 0
    match_reason: str = Field(
        ...,
        description="Why this transaction was matched: 'tax_period', 'gstin_match', "
        "'amount_proximity', 'flagged_mismatch'",
    )


class MatchedKBEntry(BaseModel):
    """A KB entry matched via pgvector similarity."""

    id: int
    filename: str
    section: str
    title: str
    content: str
    similarity: float = Field(
        ..., description="Cosine similarity score (0-1, higher = more relevant)"
    )


class AuditStep(BaseModel):
    """A single step in the cross-reference audit trail."""

    step: str
    action: str
    result: str
    details: str = ""


class CrossReferenceResult(BaseModel):
    """Complete result of cross-referencing notice fields against data + KB."""

    matched_transactions: list[MatchedTransaction] = Field(
        default_factory=list,
        description="Transactions matching the notice's tax period and/or GSTIN",
    )
    flagged_transactions: list[MatchedTransaction] = Field(
        default_factory=list,
        description="Transactions with deliberate mismatches in the same period",
    )
    kb_entry: MatchedKBEntry | None = Field(
        default=None,
        description="Best matching KB entry from pgvector similarity search",
    )
    total_transactions_in_period: int = Field(
        default=0,
        description="Total number of transactions in the same tax period",
    )
    total_amount_in_period: float = Field(
        default=0,
        description="Sum of all transaction amounts in the same tax period",
    )
    total_tax_in_period: float = Field(
        default=0,
        description="Sum of all tax amounts in the same tax period",
    )
    audit_log: list[AuditStep] = Field(
        default_factory=list,
        description="Step-by-step audit trail of the cross-reference process",
    )


# ---------------------------------------------------------------------------
# Phase 5 — Reasoning / explanation models
# ---------------------------------------------------------------------------


class Citation(BaseModel):
    """A citation linking a claim to its source."""

    claim: str = Field(..., description="The factual claim being cited")
    source: str = Field(
        ...,
        description="Source of the claim: a transaction ID, KB filename, or 'notice_text'",
    )
    source_type: str = Field(
        ...,
        description="Type of source: 'transaction', 'kb_entry', 'notice', or 'computed'",
    )


class ExplanationSection(BaseModel):
    """One section of the four-part explanation."""

    title: str = Field(..., description="Section heading")
    content: str = Field(..., description="Explanation text in plain language")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Sources backing up claims in this section",
    )


class Explanation(BaseModel):
    """The four-part explanation generated by the reasoning agent."""

    what_it_means: ExplanationSection
    why_you_got_it: ExplanationSection
    what_to_do: ExplanationSection
    confidence: ExplanationSection


class ReasoningResult(BaseModel):
    """Complete result of the reasoning agent — explanation + metadata."""

    explanation: Explanation
    overall_confidence: str = Field(
        ...,
        description="Overall confidence: 'high', 'medium', or 'low'",
    )
    is_low_confidence: bool = Field(
        default=False,
        description="True if confidence is low — triggers CA escalation banner",
    )
    ca_escalation_note: str = Field(
        default="",
        description="Non-empty when confidence is low — advises consulting a CA",
    )
    provider_used: str = Field(
        default="unknown",
        description="Which LLM provider generated the explanation",
    )


class NoticeRecord(BaseModel):
    """Record stored in the notices table — full audit of a processed notice."""

    id: int | None = None
    notice_type: str
    gstin: str
    tax_period: str
    amount: float
    section_cited: str
    due_date: str
    extraction_confidence: str
    explanation_json: dict
    overall_confidence: str
    is_low_confidence: bool
    provider_used: str
    extraction_provider: str
    matched_txn_count: int
    flagged_txn_count: int
    kb_entry_section: str | None = None
    audit_log: list[dict]
    raw_text: str = ""
    created_at: str | None = None
