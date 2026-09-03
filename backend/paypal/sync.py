"""Sync PayPal transactions into the Supabase transactions table.

Bridges real payment data from the PayPal Transaction Search (Reporting) API
into the existing transactions table, so the cross-reference logic can work
with a mix of synthetic, Razorpay, and PayPal data.

The `source` column on transactions distinguishes:
- 'synthetic' — seeded test data (Phase 3)
- 'razorpay'  — pulled from Razorpay Test Mode API (Phase 6)
- 'paypal'    — pulled from PayPal Reporting API (this module)

Run manually:
    cd backend && PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=... uv run python -m paypal.sync

Or via API:
    POST /api/paypal/sync
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from dotenv import load_dotenv

from paypal.client import PayPalClient, is_configured, get_credentials

load_dotenv()

log = logging.getLogger(__name__)

# PayPal's default reporting range in days when no explicit range is given.
DEFAULT_RANGE_DAYS = 31


def _get_pg_connection(database_url: str | None = None):
    return psycopg.connect(database_url or os.environ["DATABASE_URL"])


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return a float from a value that may be None or an amount dict."""
    if value is None:
        return default
    if isinstance(value, dict):
        # PayPal amounts are {"currency_code": "INR", "value": "123.45"}
        value = value.get("value")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _parse_paypal_datetime(value: str | None) -> str | None:
    """Normalize a PayPal RFC 3339 datetime to an ISO string (UTC naive)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    except ValueError:
        return value


def _quarter_for_month(month: int, year: int) -> str:
    quarter_map = {
        1: ("Jan-Mar", year), 2: ("Jan-Mar", year), 3: ("Jan-Mar", year),
        4: ("Apr-Jun", year), 5: ("Apr-Jun", year), 6: ("Apr-Jun", year),
        7: ("Jul-Sep", year), 8: ("Jul-Sep", year), 9: ("Jul-Sep", year),
        10: ("Oct-Dec", year), 11: ("Oct-Dec", year), 12: ("Oct-Dec", year),
    }
    label, q_year = quarter_map[month]
    return f"{label} {q_year}"


def _parse_paypal_transaction(detail: dict) -> dict | None:
    """Convert a PayPal transaction_detail object to our transactions row.

    The reporting response groups each line by `transaction_info`, `payer_info`,
    and `cart_info`. Returns None if the transaction should be skipped.
    """
    info = detail.get("transaction_info") or {}
    payer = detail.get("payer_info") or {}

    # PayPal amounts are {"currency_code": "INR", "value": "123.45"}. The gross
    # transaction amount lives in `transaction_amount` on the reporting entity.
    gross = info.get("transaction_amount") or {}
    currency = gross.get("currency_code") or ""

    # Only keep INR transactions (this app reconciles GST in INR).
    if currency != "INR":
        return None

    status = info.get("transaction_status", "")
    if not status:
        return None

    # Map PayPal transaction status to our canonical status.
    status_map = {
        "S": "captured",    # Success
        "P": "pending",     # Pending
        "V": "refunded",    # Voided
        "D": "failed",      # Denied
        "F": "failed",      # Failed
        "R": "refunded",    # Refunded
        "N": "reversed",    # Reversed
    }
    canonical_status = status_map.get(status.upper(), status.lower())

    # Only keep statuses meaningful for reconciliation.
    if canonical_status not in ("captured", "pending", "failed", "refunded", "reversed"):
        return None

    transaction_id = info.get("transaction_id") or ""
    if not transaction_id:
        return None

    created_iso = _parse_paypal_datetime(info.get("transaction_initiation_date"))
    created_dt = None
    if created_iso:
        try:
            created_dt = datetime.fromisoformat(created_iso)
        except ValueError:
            created_dt = None

    if created_dt is not None:
        tax_period = _quarter_for_month(created_dt.month, created_dt.year)
    else:
        tax_period = "Unknown"

    amount_inr = _safe_float(gross)

    refund_of = None
    refund_amount = 0.0
    event_code = (info.get("transaction_event_code") or "").lower()
    if "refund" in event_code or "reverse" in event_code or canonical_status in ("refunded", "reversed"):
        refund_of = info.get("paypal_reference_id") or None
        refund_amount = abs(amount_inr)
        amount_inr = 0.0

    # Reconstruct the "order id" — PayPal does not have a direct order column in
    # reporting, so we use the invoice/custom field if present, else the id.
    order_id = info.get("invoice_id") or info.get("custom_field") or transaction_id

    payer_gstin = None
    # GSTIN is not exposed by the PayPal reporting API directly. If the merchant
    # stores it in a custom field or cart item note, we pick it up here.
    if order_id and order_id != transaction_id and "gst" in order_id.lower():
        payer_gstin = order_id.split(";")[-1] if ";" in order_id else None

    notes: dict = {
        "paypal_payer": payer.get("email_address"),
        "payer_name": (payer.get("payer_name") or {}).get("given_name"),
        "transaction_event_code": info.get("transaction_event_code"),
        "cart_items": detail.get("cart_info") or {},
    }

    return {
        "payment_id": transaction_id,
        "order_id": order_id or "",
        "amount": round(amount_inr, 2),
        "currency": "INR",
        "status": canonical_status,
        "payment_method": "paypal",
        "payer_gstin": payer_gstin,
        "description": info.get("transaction_subject") or info.get("transaction_note") or "",
        "created_at": created_iso,
        "settled_at": _parse_paypal_datetime(info.get("transaction_updated_date")),
        "settlement_id": None,  # PayPal settlement info is account-level
        "refund_of": refund_of,
        "refund_amount": round(refund_amount, 2),
        "tax_period": tax_period,
        "tax_amount": round(abs(amount_inr) * 0.18, 2),  # Assume 18% GST
        "notes": notes,
        "source": "paypal",
    }


def _default_date_range(days: int = None) -> tuple[str, str]:
    """Return (start_date, end_date) covering the trailing N days (<=31)."""
    days = days or DEFAULT_RANGE_DAYS
    end = datetime.now(timezone.utc)
    start = end - _dt.timedelta(days=min(days, 31))
    return (
        start.strftime("%Y-%m-%dT00:00:00Z"),
        end.strftime("%Y-%m-%dT00:00:00Z"),
    )


def sync_transactions(
    count: int = 100,
    start_date: str | None = None,
    end_date: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    sandbox: bool = True,
    database_url: str | None = None,
) -> dict:
    """Pull transactions from PayPal Reporting and upsert into Supabase.

    Args:
        count: Max number of transactions to fetch.
        start_date: RFC 3339 start datetime (defaults to trailing 31 days).
        end_date: RFC 3339 end datetime (defaults to now).
        client_id: Optional per-tenant PayPal client id (falls back to .env).
        client_secret: Optional per-tenant PayPal client secret.
        sandbox: Whether to target the sandbox API (default True).
        database_url: Optional per-tenant DB (falls back to .env).

    Returns:
        Summary dict with counts of synced, skipped, and errored records.
    """
    resolved_id = client_id or (get_credentials() or (None, None))[0]
    resolved_secret = client_secret or (get_credentials() or (None, None))[1]

    if not (resolved_id and resolved_secret):
        return {
            "status": "error",
            "message": "PayPal credentials not configured. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env or provide in the request.",
        }

    result = {"synced": 0, "skipped": 0, "errors": 0, "status": "ok", "message": ""}

    try:
        client = PayPalClient(resolved_id, resolved_secret, sandbox=sandbox)

        start, end = _default_date_range()
        if start_date:
            start = start_date
        if end_date:
            end = end_date

        details = client.list_transactions_all(
            start_date=start, end_date=end, max_records=count
        )
        log.info("Fetched %d transactions from PayPal", len(details))

        rows = []
        for d in details:
            row = _parse_paypal_transaction(d)
            if row is None:
                result["skipped"] += 1
                continue
            rows.append(row)

        if not rows:
            result["message"] = f"Fetched {len(details)} transactions, none converted (non-INR or unrecognized)"
            return result

        conn = _get_pg_connection(database_url)
        try:
            with conn.cursor() as cur:
                for row in rows:
                    try:
                        cur.execute(
                            """
                            INSERT INTO transactions (
                                payment_id, order_id, amount, currency, status,
                                payment_method, payer_gstin, description,
                                created_at, settled_at, settlement_id,
                                refund_of, refund_amount, tax_period, tax_amount,
                                notes, source
                            ) VALUES (
                                %(payment_id)s, %(order_id)s, %(amount)s, %(currency)s, %(status)s,
                                %(payment_method)s, %(payer_gstin)s, %(description)s,
                                %(created_at)s, %(settled_at)s, %(settlement_id)s,
                                %(refund_of)s, %(refund_amount)s, %(tax_period)s, %(tax_amount)s,
                                %(notes)s::jsonb, %(source)s
                            )
                            ON CONFLICT (payment_id) DO UPDATE SET
                                status = EXCLUDED.status,
                                settled_at = EXCLUDED.settled_at,
                                settlement_id = EXCLUDED.settlement_id,
                                refund_amount = EXCLUDED.refund_amount,
                                source = EXCLUDED.source
                            """,
                            row,
                        )
                        result["synced"] += 1
                    except Exception as e:
                        log.warning("Failed to upsert transaction %s: %s", row["payment_id"], e)
                        result["errors"] += 1

                conn.commit()
        finally:
            conn.close()

        result["message"] = (
            f"Synced {result['synced']} transactions from PayPal "
            f"({'sandbox' if sandbox else 'live'}). "
            f"Skipped {result['skipped']}, errors: {result['errors']}"
        )
        log.info("PayPal sync complete: %s", result["message"])

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"PayPal API error: {e}"
        log.error("PayPal sync failed: %s", e)

    return result


def get_paypal_status(
    client_id: str | None = None, client_secret: str | None = None
) -> dict:
    """Check PayPal configuration and return status info."""
    if client_id and client_secret:
        configured = True
    else:
        configured = is_configured()
        if configured:
            creds = get_credentials()
            assert creds is not None
            client_id = creds[0]

    result = {
        "configured": configured,
        "client_id": None if not client_id else client_id,
        "mode": None,
    }
    if client_id:
        # Detect sandbox vs live by the "sb-" sandbox client-id prefix used by
        # PayPal developer sandbox apps. Fall back to reporting the presence
        # without guessing for custom/live apps.
        if client_id.startswith("sb-"):
            result["mode"] = "sandbox"
        else:
            result["mode"] = "live"
    return result
