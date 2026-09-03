"""Phase 6 migration — Add `source` column to transactions table.

Distinguishes synthetic (Phase 3) from Razorpay (Phase 6) data.
Existing rows default to 'synthetic'.

Run once:
    cd backend && uv run python -m db.migrate_phase6
"""

from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

MIGRATION_SQL = """
-- Add source column to track data origin
ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'synthetic';

-- Index for filtering by source
CREATE INDEX IF NOT EXISTS idx_txn_source ON transactions(source);

-- Verify
DO $$
BEGIN
    RAISE NOTICE 'Phase 6 migration complete: source column added';
END $$;
"""


def run_migration():
    print("=== Phase 6 Migration ===\n")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            # Check if column already exists
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'transactions' AND column_name = 'source'"
            )
            if cur.fetchone():
                print("Column 'source' already exists — skipping migration")
                return

            print("Adding 'source' column to transactions table...")
            cur.execute(MIGRATION_SQL)
            conn.commit()
            print("Migration complete")
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
