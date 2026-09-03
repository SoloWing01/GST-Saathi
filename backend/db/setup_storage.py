"""Create the Supabase Storage bucket for uploaded notices.

Run once:
    cd backend && uv run python -m db.setup_storage
"""

from __future__ import annotations

import sys

from db.supabase_client import get_client


def setup() -> None:
    client = get_client()
    if client is None:
        print("Supabase client not configured — check backend/.env", file=sys.stderr)
        sys.exit(1)

    bucket_id = "notice-uploads"

    existing = client.storage.list_buckets()
    if any(b.name == bucket_id for b in existing):
        print(f"Bucket '{bucket_id}' already exists.")
        return

    client.storage.create_bucket(bucket_id, options={"public": False})
    print(f"Created bucket '{bucket_id}'.")


if __name__ == "__main__":
    setup()
