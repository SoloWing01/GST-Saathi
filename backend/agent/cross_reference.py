"""Phase 4 — Cross-reference logic.

Given extracted notice fields:
1. Query Supabase transactions table for matching/near-matching records
2. Embed notice text and run pgvector similarity search against KB embeddings
3. Return structured result with matched transactions, KB entry, and audit trail
"""

from __future__ import annotations

from contextlib import contextmanager

import asyncio
import json
import logging

import psycopg
import psycopg_pool
from sentence_transformers import SentenceTransformer

from agent.models import (
    AuditStep,
    CrossReferenceResult,
    ExtractedFields,
    MatchedKBEntry,
    MatchedTransaction,
)

log = logging.getLogger(__name__)

# Lazy-loaded embedding model (preloaded at app startup via cross_reference.ensure_models_loaded)
_embedding_model: SentenceTransformer | None = None
_embedding_lock = asyncio.Lock()

# Reusable synchronous Postgres pools keyed by connection string — avoids opening
# a new connection per request. Safe to use across threads (the cross-reference
# runs in a thread pool via asyncio.to_thread during a request so it never
# blocks the event loop).
_pg_pools: dict[str, psycopg_pool.ConnectionPool] = {}


def ensure_models_loaded() -> None:
    """Preload the embedding model so the first request isn't slow (blocks).

    Call this once at application startup (FastAPI lifespan) rather than on
    the first user request.
    """
    _get_embedding_model()


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def _pool_for(database_url: str) -> psycopg_pool.ConnectionPool | None:
    """Get (or lazily create) a pool for the given connection string."""
    if not database_url:
        return None
    pool = _pg_pools.get(database_url)
    if pool is not None and not pool.closed:
        return pool
    try:
        pool = psycopg_pool.ConnectionPool(
            database_url,
            min_size=1,
            max_size=10,
            open=True,
            timeout=30,
        )
        _pg_pools[database_url] = pool
        log.info("Postgres connection pool initialized (max_size=10)")
        return pool
    except Exception as e:
        log.warning("Failed to init pool for new DB: %s", e)
        return None


def init_connection_pool() -> None:
    """Create the shared Postgres pool for the default (.env) DB. Call at startup."""
    pass


@contextmanager
def _get_pg_connection(database_url: str | None = None):
    """Yield a Postgres connection for the given DB.

    Uses the shared pool when possible; falls back to a raw connection.
    Using it as a context manager returns the connection to the pool on exit.
    """
    if not database_url:
        raise RuntimeError("No DATABASE_URL configured for this tenant.")
    url = database_url
    if url:
        pool = _pool_for(url)
        if pool is not None and not pool.closed:
            with pool.connection() as conn:
                yield conn
            return
    if url:
        # No pool possible — use a dedicated connection.
        conn = psycopg.connect(url)
        try:
            yield conn
        finally:
            conn.close()
        return
    raise RuntimeError("No DATABASE_URL configured for this tenant.")


# ---------------------------------------------------------------------------
# Tax period normalization
# ---------------------------------------------------------------------------

# Map of common tax period text variations to a canonical form
_PERIOD_ALIASES = {
    "april 2024 - june 2024": "Apr-Jun 2024",
    "april 2024 to june 2024": "Apr-Jun 2024",
    "apr-jun 2024": "Apr-Jun 2024",
    "q1 fy 2024-25": "Apr-Jun 2024",
    "q1 fy2024-25": "Apr-Jun 2024",
    "q1 2024-25": "Apr-Jun 2024",
    "october 2024 - december 2024": "Oct-Dec 2024",
    "october 2024 to december 2024": "Oct-Dec 2024",
    "oct-dec 2024": "Oct-Dec 2024",
    "q3 fy 2024-25": "Oct-Dec 2024",
    "q3 fy2024-25": "Oct-Dec 2024",
    "q3 2024-25": "Oct-Dec 2024",
    "july 2024 - september 2024": "Jul-Sep 2024",
    "july 2024 to september 2024": "Jul-Sep 2024",
    "jul-sep 2024": "Jul-Sep 2024",
    "q2 fy 2024-25": "Jul-Sep 2024",
    "q2 fy2024-25": "Jul-Sep 2024",
    "q2 2024-25": "Jul-Sep 2024",
    "january 2024 - march 2024": "Jan-Mar 2024",
    "jan-mar 2024": "Jan-Mar 2024",
    "q4 fy 2023-24": "Jan-Mar 2024",
    "september 2024": "Sep 2024",
}


def _normalize_tax_period(period: str) -> str:
    """Normalize a tax period string to match what's in the transactions table."""
    lower = period.strip().lower()

    # Check exact aliases
    if lower in _PERIOD_ALIASES:
        return _PERIOD_ALIASES[lower]

    # Try to extract month names and year
    # e.g. "April 2024 - June 2024" -> "Apr-Jun 2024"
    month_abbr = {
        "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
        "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
        "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
    }

    for full, abbr in month_abbr.items():
        lower = lower.replace(full, abbr)

    # Clean up separators
    lower = lower.replace(" - ", "-").replace(" to ", "-").replace("  ", " ")
    return lower.strip().title()


# ---------------------------------------------------------------------------
# Transaction matching
# ---------------------------------------------------------------------------

def _find_matching_transactions(
    fields: ExtractedFields,
    database_url: str | None = None,
) -> tuple[list[MatchedTransaction], list[MatchedTransaction], AuditStep]:
    """Find transactions matching the notice's tax period and GSTIN.

    Returns:
        Tuple of (all_matching, flagged_only, audit_step).
    """
    audit = AuditStep(
        step="transaction_lookup",
        action="Query Supabase transactions table",
        result="",
    )

    normalized_period = _normalize_tax_period(fields.tax_period or "")
    log.info("Normalized tax period: '%s' -> '%s'", fields.tax_period, normalized_period)

    with _get_pg_connection(database_url) as conn:
        with conn.cursor() as cur:
            # 1. Get all transactions in the tax period
            # Prefer Razorpay-sourced data when available, fall back to synthetic
            cur.execute(
                "SELECT payment_id, order_id, amount, status, payer_gstin, "
                "       description, created_at, settled_at, tax_period, "
                "       tax_amount, refund_of, refund_amount, notes, source "
                "FROM transactions "
                "WHERE tax_period = %s "
                "ORDER BY source DESC, created_at",
                (normalized_period,),
            )
            rows = cur.fetchall()

            if not rows:
                # Try fuzzy match — maybe the period string is slightly different
                cur.execute(
                    "SELECT payment_id, order_id, amount, status, payer_gstin, "
                    "       description, created_at, settled_at, tax_period, "
                    "       tax_amount, refund_of, refund_amount, notes, source "
                    "FROM transactions "
                    "WHERE tax_period ILIKE %s "
                    "ORDER BY source DESC, created_at",
                    (f"%{normalized_period[:6]}%",),
                )
                rows = cur.fetchall()
                if rows:
                    audit.details = f"Fuzzy period match used (original: '{fields.tax_period}')"

            all_transactions = []
            flagged_transactions = []
            total_amount = 0.0
            total_tax = 0.0

            source_counts: dict[str, int] = {}

            for row in rows:
                pid, oid, amt, status, gstin, desc, created, settled, tp, tax, ref_of, ref_amt, notes, source = row
                total_amount += float(amt)
                total_tax += float(tax)
                source_counts[source] = source_counts.get(source, 0) + 1

                # Determine match reason
                reasons = []
                if gstin and fields.gstin and gstin == fields.gstin:
                    reasons.append("gstin_match")
                if fields.amount is not None and abs(float(amt) - fields.amount) < fields.amount * 0.1:
                    reasons.append("amount_proximity")
                if notes and isinstance(notes, dict) and notes.get("flag"):
                    reasons.append("flagged_mismatch")
                if not reasons:
                    reasons.append("tax_period")

                txn = MatchedTransaction(
                    payment_id=pid,
                    order_id=oid,
                    amount=float(amt),
                    status=status,
                    payer_gstin=gstin,
                    description=desc,
                    created_at=str(created),
                    settled_at=str(settled) if settled else None,
                    tax_period=tp,
                    tax_amount=float(tax),
                    refund_of=ref_of,
                    refund_amount=float(ref_amt) if ref_amt else 0,
                    match_reason=", ".join(reasons),
                )
                all_transactions.append(txn)

                if notes and isinstance(notes, dict) and notes.get("flag"):
                    flagged_transactions.append(txn)

            source_detail = ", ".join(f"{k}: {v}" for k, v in source_counts.items())
            audit.result = f"Found {len(all_transactions)} transactions in period '{normalized_period}'"
            audit.details = (
                f"Total amount: ₹{total_amount:,.2f}, Total tax: ₹{total_tax:,.2f}, "
                f"Flagged: {len(flagged_transactions)}, Sources: {source_detail}"
            )

            return all_transactions, flagged_transactions, audit


# ---------------------------------------------------------------------------
# KB similarity search
# ---------------------------------------------------------------------------

def _find_matching_kb_entry(
    fields: ExtractedFields,
    database_url: str | None = None,
) -> tuple[MatchedKBEntry | None, AuditStep]:
    """Embed the notice text and find the most relevant KB entry via pgvector.

    First tries a direct section-code lookup (exact match on section field).
    Falls back to pgvector similarity search if no exact match.

    Returns:
        Tuple of (best_match_or_None, audit_step).
    """
    audit = AuditStep(
        step="kb_lookup",
        action="Direct section lookup + pgvector similarity search",
        result="",
    )
    with _get_pg_connection(database_url) as conn:

        with conn.cursor() as cur:
            notice_type = (fields.notice_type or "").upper().strip()
            section_cited = fields.section_cited or ""
            tax_period = fields.tax_period or ""

            if notice_type:
                # 1. Try direct section lookup (fastest and most accurate)
                cur.execute(
                    "SELECT id, filename, section, title, content "
                    "FROM gst_kb_embeddings "
                    "WHERE UPPER(section) = %s OR UPPER(filename) LIKE %s "
                    "LIMIT 1",
                    (notice_type, f"%{notice_type.lower().replace('-', '')}%"),
                )
                row = cur.fetchone()

                if row:
                    kb_id, filename, section, title, content = row
                    match = MatchedKBEntry(
                        id=kb_id,
                        filename=filename,
                        section=section,
                        title=title,
                        content=content[:2000],
                        similarity=1.0,  # Exact match
                    )
                    audit.result = f"Direct match: '{title}' (section: {section})"
                    audit.details = f"File: {filename}"
                    return match, audit

            # 2. Fall back to pgvector similarity search
            search_text = " ".join(filter(None, [
                notice_type, section_cited, tax_period,
            ]))
            if not search_text.strip():
                search_text = "GST Act notice"
            search_text += " CGST Act GST notice"

            model = _get_embedding_model()
            embedding = model.encode(search_text, normalize_embeddings=True).tolist()

            cur.execute(
                """
                SELECT id, filename, section, title, content,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM gst_kb_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT 1
                """,
                (json.dumps(embedding), json.dumps(embedding)),
            )
            row = cur.fetchone()

            if row is None:
                audit.result = "No KB entries found"
                return None, audit

            kb_id, filename, section, title, content, similarity = row

            match = MatchedKBEntry(
                id=kb_id,
                filename=filename,
                section=section,
                title=title,
                content=content[:2000],
                similarity=round(float(similarity), 4),
            )

            audit.result = f"Similarity match: '{title}' (score: {match.similarity})"
            audit.details = f"Section: {section}, File: {filename}"

            return match, audit


# ---------------------------------------------------------------------------
# Main cross-reference function
# ---------------------------------------------------------------------------

def _cross_reference_sync(
    fields: ExtractedFields,
    database_url: str | None = None,
) -> CrossReferenceResult:
    """Cross-reference extracted notice fields against transactions + KB.

    This is the core Phase 4 logic. It:
    1. Normalizes the tax period
    2. Queries transactions table for matching records
    3. Identifies flagged mismatches in the same period
    4. Runs pgvector similarity search against KB embeddings
    5. Returns structured result with full audit trail
    """
    audit_log: list[AuditStep] = []

    # Step 1: Normalize tax period
    audit_log.append(AuditStep(
        step="normalize_period",
        action=f"Normalize tax period '{fields.tax_period}'",
        result=f"Normalized to '{_normalize_tax_period(fields.tax_period or '')}'",
    ))

    # When no database is configured, skip transaction/KB lookup and return an
    # empty result so the pipeline can still produce an LLM explanation. The
    # explanation step works purely from the extracted fields + raw text.
    if not database_url:
        audit_log.append(AuditStep(
            step="transaction_lookup",
            action="Query transactions table",
            result="Skipped — no DATABASE_URL configured for this tenant. Add Supabase or a Postgres DATABASE_URL to enable transaction & knowledge-base cross-referencing.",
        ))
        audit_log.append(AuditStep(
            step="kb_lookup",
            action="Direct section lookup + pgvector similarity search",
            result="Skipped — no DATABASE_URL configured for this tenant.",
        ))
        return CrossReferenceResult(
            matched_transactions=[],
            flagged_transactions=[],
            kb_entry=None,
            total_transactions_in_period=0,
            total_amount_in_period=0.0,
            total_tax_in_period=0.0,
            audit_log=audit_log,
        )

    # Step 2: Find matching transactions
    matching_txns, flagged_txns, txn_audit = _find_matching_transactions(fields, database_url)
    audit_log.append(txn_audit)

    # Step 3: Find matching KB entry
    kb_entry, kb_audit = _find_matching_kb_entry(fields, database_url)
    audit_log.append(kb_audit)

    # Step 4: Compute totals
    total_amount = sum(t.amount for t in matching_txns)
    total_tax = sum(t.tax_amount for t in matching_txns)

    log.info(
        "Cross-reference complete: %d transactions, %d flagged, KB match=%s",
        len(matching_txns),
        len(flagged_txns),
        kb_entry.section if kb_entry else "none",
    )

    return CrossReferenceResult(
        matched_transactions=matching_txns,
        flagged_transactions=flagged_txns,
        kb_entry=kb_entry,
        total_transactions_in_period=len(matching_txns),
        total_amount_in_period=total_amount,
        total_tax_in_period=total_tax,
        audit_log=audit_log,
    )


async def cross_reference(
    fields: ExtractedFields,
    database_url: str | None = None,
) -> CrossReferenceResult:
    """Async wrapper — runs the synchronous cross-reference in a thread pool."""
    return await asyncio.to_thread(_cross_reference_sync, fields, database_url)
