"""Phase 0 Supabase acceptance probe.

Proves the backend can talk to Supabase with a real read+write:

1. Create a throwaway table via raw Postgres (supabase-py's REST client can't
   run DDL, so DDL uses DATABASE_URL + psycopg).
2. Insert + read back a row through the app-level Supabase client (the same
   one future phases use).
3. Drop the table.

Run manually once .env has the three Supabase vars:

    cd backend && uv run python -m db.check_supabase

Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

TABLE = "_phase0_probe"


def _run_ddl(sql: str) -> None:
    """Run a single SQL statement against Supabase Postgres (no params)."""
    import psycopg

    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def run_probe() -> None:
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL"):
        if not os.getenv(var):
            print(f"Missing {var} in backend/.env — cannot run probe.")
            sys.exit(1)

    # 1. Create table (DDL).
    _run_ddl(
        f'CREATE TABLE IF NOT EXISTS {TABLE} ('
        "  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
        "  note text NOT NULL"
        ")"
    )
    print(f"Created table {TABLE!r}.")

    # 2. Insert + read through the app-level client.
    from .supabase_client import get_client

    client = get_client()
    assert client is not None, "supabase client unexpectedly None"
    client.table(TABLE).insert({"note": "phase0 probe hello"}).execute()
    print("Inserted a row via Supabase client.")

    rows = client.table(TABLE).select("*").execute().data
    print(f"Read back {len(rows)} row(s): {rows}")
    if not rows or rows[0].get("note") != "phase0 probe hello":
        raise RuntimeError("read-back did not match the inserted value")

    # 3. Clean up.
    _run_ddl(f"DROP TABLE IF EXISTS {TABLE}")
    print("Dropped probe table. Supabase connectivity confirmed ✅")


if __name__ == "__main__":
    try:
        run_probe()
    except Exception as exc:  # noqa: BLE001 - report any failure to the user
        print(f"Probe failed: {exc}", file=sys.stderr)
        sys.exit(1)