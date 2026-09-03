"""PayPal Reporting (Transaction Search) API client.

Authenticates with OAuth 2.0 client-credentials grant: the app exchanges its
Client ID + Client Secret for a short-lived access token, then uses that Bearer
token for all subsequent requests.

Only sandbox credentials should be used — never production (live) keys in this
codebase.

API reference: https://developer.paypal.com/api/transaction-search/v1/
"""

from __future__ import annotations

import os
import logging
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

PAYPAL_LIVE_BASE = "https://api-m.paypal.com"
PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com"


def _env_or_none(name: str) -> str | None:
    value = os.getenv(name)
    return value if value and value.strip() else None


def is_configured() -> bool:
    """Check if PayPal credentials are configured."""
    return (
        _env_or_none("PAYPAL_CLIENT_ID") is not None
        and _env_or_none("PAYPAL_CLIENT_SECRET") is not None
    )


def get_credentials() -> tuple[str, str] | None:
    """Return (client_id, client_secret) or None if not configured."""
    client_id = _env_or_none("PAYPAL_CLIENT_ID")
    client_secret = _env_or_none("PAYPAL_CLIENT_SECRET")
    if client_id and client_secret:
        return client_id, client_secret
    return None


class PayPalClient:
    """HTTP client for the PayPal Reporting (Transaction Search) API.

    Uses OAuth 2.0 client-credentials to obtain an access token and stores it
    for reuse, refreshing it when it expires. All payment-reporting methods
    return parsed JSON or raise on error.
    """

    def __init__(self, client_id: str, client_secret: str, sandbox: bool = True):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = PAYPAL_SANDBOX_BASE if sandbox else PAYPAL_LIVE_BASE
        self._access_token: str | None = None
        self._client = httpx.Client(timeout=30.0)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _authenticate(self) -> str:
        """Exchange client credentials for an OAuth 2.0 access token."""
        resp = self._client.post(
            f"{self.base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Accept": "application/json",
                "Accept-Language": "en_US",
            },
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token")
        log.info("PayPal: obtained OAuth access token")
        return self._access_token

    def _headers(self) -> dict[str, str]:
        """Return an Authorization header, obtaining a token on first use."""
        if not self._access_token:
            self._authenticate()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None):
        """Make a GET request with a valid Bearer token (retrying once on 401)."""
        resp = self._client.get(
            f"{self.base_url}{path}", params=params or {}, headers=self._headers()
        )
        if resp.status_code == 401 and self._access_token:
            # Token may have expired early — refresh once and retry.
            self._access_token = None
            resp = self._client.get(
                f"{self.base_url}{path}", params=params or {}, headers=self._headers()
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Transactions (Reporting)
    # ------------------------------------------------------------------

    def list_transactions(
        self,
        start_date: str,
        end_date: str,
        page_size: int = 100,
        page: int = 1,
        fields: str = "all",
    ) -> dict:
        """List transactions via GET /v1/reporting/transactions.

        Args:
            start_date: RFC 3339 start datetime (e.g. "2024-04-01T00:00:00Z").
            end_date: RFC 3339 end datetime. Max range is 31 days.
            page_size: Number of records per page (max 500).
            page: One-based page number.
            fields: "all" or a comma-separated field list.

        Returns:
            PayPal response: {"transaction_details": [...], "total_items": N,
            "total_pages": N, "page": N, "last_refreshed_datetime": "..."}
        """
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "page_size": min(page_size, 500),
            "page": page,
            "fields": fields,
        }
        log.info(
            "PayPal: GET /v1/reporting/transactions (start=%s, end=%s, page=%d, size=%d)",
            start_date, end_date, page, params["page_size"],
        )
        return self._get("/v1/reporting/transactions", params)

    def list_transactions_all(
        self,
        start_date: str,
        end_date: str,
        max_records: int = 500,
    ) -> list[dict]:
        """Paginate through all transactions up to max_records.

        Returns a flat list of transaction_detail items.
        """
        all_items: list[dict] = []
        page = 1
        page_size = 100

        while len(all_items) < max_records:
            remaining = max_records - len(all_items)
            batch = self.list_transactions(
                start_date=start_date,
                end_date=end_date,
                page_size=min(page_size, remaining),
                page=page,
            )
            items = batch.get("transaction_details", [])
            if not items:
                break
            all_items.extend(items)
            page += 1

            # Stop when we reach the last page.
            total_pages = batch.get("total_pages", 0)
            if page > total_pages:
                break
            if len(items) < page_size:
                break

        log.info("PayPal: fetched %d transactions total", len(all_items))
        return all_items[:max_records]

    # ------------------------------------------------------------------
    # Balances (Reporting)
    # ------------------------------------------------------------------

    def get_balance(self, as_of_time: str | None = None) -> dict:
        """Get account balances via GET /v1/reporting/balances."""
        params: dict[str, Any] = {}
        if as_of_time:
            params["as_of_time"] = as_of_time
        return self._get("/v1/reporting/balances", params)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
