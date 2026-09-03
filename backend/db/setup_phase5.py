"""Phase 5 — Create the notices table for audit log storage.

Stores every processed notice with extracted fields, cross-reference
results, explanation, confidence, and full audit trail.

Run once (after setup_phase3.py):
    cd backend && uv run python -m db.setup_phase5
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

DDL_NOTICES = """
CREATE TABLE IF NOT EXISTS notices (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    notice_type             text NOT NULL,
    gstin                   text NOT NULL,
    tax_period              text NOT NULL,
    amount                  numeric(12,2) NOT NULL,
    section_cited           text NOT NULL,
    due_date                text NOT NULL,
    extraction_confidence   text NOT NULL,
    explanation_json        jsonb NOT NULL,
    overall_confidence      text NOT NULL,
    is_low_confidence       boolean NOT NULL DEFAULT false,
    provider_used           text NOT NULL,
    extraction_provider     text NOT NULL,
    matched_txn_count       integer NOT NULL DEFAULT 0,
    flagged_txn_count       integer NOT NULL DEFAULT 0,
    kb_entry_section        text,
    audit_log               jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_text                text DEFAULT '',
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notices_gstin ON notices(gstin);
CREATE INDEX IF NOT EXISTS idx_notices_notice_type ON notices(notice_type);
CREATE INDEX IF NOT EXISTS idx_notices_created ON notices(created_at);
"""


def _run_ddl(sql: str) -> None:
    """Run SQL against Supabase Postgres via psycopg."""
    import psycopg
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def setup() -> None:
    print("=== Phase 5 Setup ===\n")

    print("Creating notices table...")
    _run_ddl(DDL_NOTICES)
    print("  notices table ready")

    # Verify
    import psycopg
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM notices")
            count = cur.fetchone()[0]
            print(f"  Current records: {count}")
    finally:
        conn.close()

    print("\n=== Phase 5 Setup Complete ===")


if __name__ == "__main__":
    setup()
