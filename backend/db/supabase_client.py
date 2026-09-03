"""Single Supabase client module for the backend.

Per docs/Rules.md: all Supabase access goes through this module — no raw
connection/query code scattered elsewhere. If creds are missing (no .env or
placeholders only), the client is None and the app still boots; routes that
need Supabase report it via /api/health instead of crashing.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # reads backend/.env into process env

# Creators return None (not raise) when creds are absent, so callers can
# degrade gracefully.
def _env_or_none(name: str) -> str | None:
    value = os.getenv(name)
    return value if value and value.strip() else None


@lru_cache(maxsize=1)
def get_client():
    """Return a cached Supabase client, or None if creds aren't configured."""
    return build_client(_env_or_none("SUPABASE_URL"), _env_or_none("SUPABASE_SERVICE_ROLE_KEY"))


def build_client(url: str | None, service_role_key: str | None):
    """Build a Supabase client from explicit credentials, or None if absent."""
    if not url or not service_role_key:
        return None
    from supabase import create_client

    return create_client(url, service_role_key)


def is_available() -> bool:
    """True when a client can be built (creds configured in .env)."""
    return get_client() is not None