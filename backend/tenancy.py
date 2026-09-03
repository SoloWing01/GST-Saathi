"""In-memory per-tenant credential store.

Every user (including the developer) MUST provide their own API keys to use
the application. There is no fallback to server-side .env keys.

Required:
  - At least one LLM provider key (Groq and/or Google Gemini)

Optional (at least one recommended):
  - Supabase (URL + service role key)
  - Razorpay (key ID + key secret)
  - PayPal (client ID + client secret)

Credentials are held in memory only — never written to disk — and keyed by
an arbitrary tenant/session id supplied by the caller via X-Tenant-ID header.

Note on security:
- Secrets live only in process memory and are lost on restart.
- Do NOT surface stored values through read endpoints (return booleans/states
  only). The frontend keeps its own copy in the browser.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class TenantCredentials:
    """Credentials a user must supply to use this tenant/session.

    Every user must provide at least one LLM provider key. The payment/Supabase
    integrations are optional but at least one is required for a useful setup.
    """

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    google_api_key: str | None = None
    google_model: str | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None

    def any_set(self) -> bool:
        return any(
            v for v in (
                self.supabase_url, self.supabase_service_role_key,
                self.database_url, self.groq_api_key, self.google_api_key,
                self.razorpay_key_id, self.razorpay_key_secret,
                self.paypal_client_id, self.paypal_client_secret,
            )
        )

    # ------------------------------------------------------------------
    # Required-provider validation
    # ------------------------------------------------------------------

    def has_llm(self) -> bool:
        """True when at least one LLM provider key is supplied."""
        return bool(self.groq_api_key or self.google_api_key)

    def has_supabase(self) -> bool:
        """True when a usable Supabase setup is supplied."""
        return bool(self.supabase_url and self.supabase_service_role_key)

    def has_razorpay(self) -> bool:
        """True when a usable Razorpay setup is supplied."""
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    def has_paypal(self) -> bool:
        """True when a usable PayPal setup is supplied."""
        return bool(self.paypal_client_id and self.paypal_client_secret)

    def has_any_payment_provider(self) -> bool:
        """True when at least one payment provider (Razorpay / PayPal) is set."""
        return self.has_razorpay() or self.has_paypal()

    def validate_required(self) -> list[str]:
        """Return a list of missing-requirement messages (empty when OK).

        Rules:
        - At least one LLM provider is mandatory for every user.
        - At least one of Supabase / Postgres / Razorpay / PayPal is required
          so the app has somewhere to pull data from.
        - Any payment provider supplied must be complete (both key fields).
        """
        missing: list[str] = []

        if not self.has_llm():
            missing.append(
                "Provide at least one LLM API key (Groq or Google Gemini)."
            )

        has_any_db_or_data = (
            self.has_supabase()
            or self.database_url
            or self.has_razorpay()
            or self.has_paypal()
        )
        if not has_any_db_or_data:
            missing.append(
                "Provide Supabase credentials, a Postgres DATABASE_URL, "
                "or a payment provider (Razorpay / PayPal)."
            )

        if self.razorpay_key_id and not self.razorpay_key_secret:
            missing.append("Razorpay key secret is required when a key ID is provided.")
        if self.razorpay_key_secret and not self.razorpay_key_id:
            missing.append("Razorpay key ID is required when a key secret is provided.")

        if self.paypal_client_id and not self.paypal_client_secret:
            missing.append("PayPal client secret is required when a client ID is provided.")
        if self.paypal_client_secret and not self.paypal_client_id:
            missing.append("PayPal client ID is required when a client secret is provided.")

        if self.supabase_url and not self.supabase_service_role_key:
            missing.append("Supabase service role key is required when a URL is provided.")
        if self.supabase_service_role_key and not self.supabase_url:
            missing.append("Supabase URL is required when a service role key is provided.")

        return missing


class CredentialStore:
    """Thread-safe in-memory map of tenant_id -> TenantCredentials."""

    def __init__(self) -> None:
        self._store: dict[str, TenantCredentials] = {}
        self._lock = threading.Lock()

    def put(self, tenant_id: str, creds: TenantCredentials) -> None:
        with self._lock:
            self._store[tenant_id] = creds

    def get(self, tenant_id: str) -> TenantCredentials | None:
        with self._lock:
            return self._store.get(tenant_id)

    def clear(self, tenant_id: str) -> None:
        with self._lock:
            self._store.pop(tenant_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._store.clear()


_store = CredentialStore()


def get_store() -> CredentialStore:
    return _store


def resolve_tenant_id(tenant_id: str | None) -> str:
    """Return a usable tenant id, defaulting to 'default' when absent."""
    return (tenant_id or "").strip() or "default"


def get_tenant(tenant_id: str | None) -> TenantCredentials | None:
    """Return the tenant's stored credentials, or None if not set."""
    return _store.get(resolve_tenant_id(tenant_id))
