"""Agent module — extraction, cross-reference, and reasoning with dual LLM."""

from agent.cross_reference import cross_reference
from agent.extract_fields import extract_notice_fields
from agent.llm_client import get_llm_client, llm_complete
from agent.models import (
    Citation,
    CrossReferenceResult,
    Explanation,
    ExplanationSection,
    ExtractedFields,
    ExtractionResult,
    MatchedKBEntry,
    MatchedTransaction,
    NoticeRecord,
    ReasoningResult,
)
from agent.reasoning import generate_explanation

__all__ = [
    "cross_reference",
    "extract_notice_fields",
    "generate_explanation",
    "get_llm_client",
    "llm_complete",
    "Citation",
    "CrossReferenceResult",
    "Explanation",
    "ExplanationSection",
    "ExtractedFields",
    "ExtractionResult",
    "MatchedKBEntry",
    "MatchedTransaction",
    "NoticeRecord",
    "ReasoningResult",
]
