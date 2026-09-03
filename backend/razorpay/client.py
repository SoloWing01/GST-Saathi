"""Razorpay Test Mode API client.

Authenticates with Basic Auth (key_id:key_secret) per Razorpay docs.
Only test mode keys should be used — never production keys in this codebase.

API reference: https://razorpay.com/docs/api/payments/
"""

from __future__ import annotations

import os
import logging
from base64 import b64encode
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


def _env_or_none(name: str) -> str | None:
    value = os.getenv(name)
    return value if value and value.strip() else None


def is_configured() -> bool:
    """Check if Razorpay Test Mode credentials are configured."""
    return (
        _env_or_none("RAZORPAY_KEY_ID") is not None
        and _env_or_none("RAZORPAY_KEY_SECRET") is not None
    )


def get_credentials() -> tuple[str, str] | None:
    """Return (key_id, key_secret) or None if not configured."""
    key_id = _env_or_none("RAZORPAY_KEY_ID")
    key_secret = _env_or_none("RAZORPAY_KEY_SECRET")
    if key_id and key_secret:
        return key_id, key_secret
    return None


class RazorpayTestClient:
    """HTTP client for Razorpay Test Mode API.

    Uses Basic Auth per Razorpay docs:
        Authorization: Basic base64(key_id:key_secret)

    All methods return parsed JSON or raise on error.
    """

    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self._auth_header = (
            "Basic " + b64encode(f"{key_id}:{key_secret}".encode()).decode()
        )
        self._client = httpx.Client(
            base_url=RAZORPAY_API_BASE,
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request to the Razorpay API."""
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    def list_payments(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
        count: int = 100,
        skip: int = 0,
    ) -> dict:
        """List payments via GET /payments.

        Args:
            from_timestamp: Unix timestamp — start of time range.
            to_timestamp: Unix timestamp — end of time range.
            count: Number of records to fetch (max 100 per page).
            skip: Number of records to skip (for pagination).

        Returns:
            Razorpay response: {"entity": "list", "count": N, "items": [...]}
        """
        params: dict[str, Any] = {"count": min(count, 100), "skip": skip}
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp

        log.info(
            "Razorpay: GET /payments (count=%d, skip=%d, from=%s, to=%s)",
            params["count"], skip, from_timestamp, to_timestamp,
        )
        return self._get("/payments", params)

    def get_payment(self, payment_id: str) -> dict:
        """Get a single payment by ID via GET /payments/:id."""
        return self._get(f"/payments/{payment_id}")

    def list_payments_all(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
        max_records: int = 500,
    ) -> list[dict]:
        """Paginate through all payments up to max_records.

        Returns a flat list of payment items.
        """
        all_items: list[dict] = []
        skip = 0
        page_size = 100

        while len(all_items) < max_records:
            remaining = max_records - len(all_items)
            batch = self.list_payments(
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                count=min(page_size, remaining),
                skip=skip,
            )
            items = batch.get("items", [])
            if not items:
                break
            all_items.extend(items)
            skip += len(items)

            # Razorpay returns fewer items than requested when there are no more
            if len(items) < page_size:
                break

        log.info("Razorpay: fetched %d payments total", len(all_items))
        return all_items[:max_records]

    # ------------------------------------------------------------------
    # Settlements
    # ------------------------------------------------------------------

    def list_settlements(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
        count: int = 100,
        skip: int = 0,
    ) -> dict:
        """List settlements via GET /settlements."""
        params: dict[str, Any] = {"count": min(count, 100), "skip": skip}
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp
        return self._get("/settlements", params)

    # ------------------------------------------------------------------
    # Settlement Recon
    # ------------------------------------------------------------------

    def get_settlement_recon(
        self,
        year: int,
        month: int,
        day: int | None = None,
        count: int = 100,
        skip: int = 0,
    ) -> dict:
        """Get settlement-recon details via GET /settlements/recon/combined.

        This is the Payments-API way to see the net settlement picture (credits
        and debits for payments, refunds, transfers and adjustments) for a given
        month/day. There is no general `/v1/balance` endpoint on the Payments
        API — balance is a RazorpayX (Payouts) endpoint.

        Args:
            year: 4-digit year, e.g. 2024.
            month: Month 1-12.
            day: Optional day 1-31.
            count: Number of records (max 1000).
            skip: Number of records to skip.

        Returns:
            Razorpay response: {"entity": "collection", "count": N, "items": [...]}
        """
        params: dict[str, Any] = {
            "year": year,
            "month": month,
            "count": min(count, 1000),
            "skip": skip,
        }
        if day:
            params["day"] = day
        return self._get("/settlements/recon/combined", params)

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
