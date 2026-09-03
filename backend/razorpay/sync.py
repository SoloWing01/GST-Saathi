"""Sync Razorpay Test Mode transactions into the Supabase transactions table.

This bridges Phase 6: pulls real payment data from Razorpay Test Mode API
and upserts it into the existing transactions table, so the cross-reference
logic can work with a mix of synthetic and real data.

The `source` column on transactions distinguishes:
- 'synthetic' — seeded test data (Phase 3)
- 'razorpay'  — pulled from Razorpay Test Mode API (Phase 6)

Run manually:
    cd backend && uv run python -m razorpay.sync

Or via API:
    POST /api/razorpay/sync
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv

from razorpay.client import RazorpayTestClient, is_configured, get_credentials

load_dotenv()

log = logging.getLogger(__name__)


def _get_pg_connection(database_url: str | None = None):
    return psycopg.connect(database_url or os.environ["DATABASE_URL"])


def _parse_razorpay_payment(payment: dict) -> dict | None:
    """Convert a Razorpay payment object to our transactions table row format.

    Returns None if the payment should be skipped (e.g. non-INR, non-captured).
    """
    # Only keep INR payments
    if payment.get("currency") != "INR":
        return None

    # Only keep relevant statuses
    status = payment.get("status", "")
    if status not in ("captured", "refunded", "failed"):
        return None

    # Parse timestamps
    created_at = datetime.fromtimestamp(
        payment.get("created_at", 0), tz=timezone.utc
    )

    # Determine tax period from created_at
    # Map to our canonical format: "Apr-Jun 2024", "Jul-Sep 2024", etc.
    month = created_at.month
    year = created_at.year
    quarter_map = {
        1: ("Jan-Mar", year), 2: ("Jan-Mar", year), 3: ("Jan-Mar", year),
        4: ("Apr-Jun", year), 5: ("Apr-Jun", year), 6: ("Apr-Jun", year),
        7: ("Jul-Sep", year), 8: ("Jul-Sep", year), 9: ("Jul-Sep", year),
        10: ("Oct-Dec", year), 11: ("Oct-Dec", year), 12: ("Oct-Dec", year),
    }
    q_label, q_year = quarter_map[month]
    tax_period = f"{q_label} {q_year}"

    # Amount in paise from Razorpay → INR
    amount_paise = payment.get("amount", 0)
    amount_inr = amount_paise / 100.0

    # Refund handling.
    #
    # The payment entity exposes refunds via `refund_status` (partial/full) and
    # `amount_refunded` (in paise) — there is no `refund_id` on the payment.
    # For a fully refunded payment we also expose the reason via `refund_status`
    # and record how much was actually refunded.
    refund_of = None
    refund_amount = 0.0
    if status == "refunded":
        refund_status = (payment.get("refund_status") or "").lower()
        # `amount_refunded` is the authoritative refunded amount in paise.
        amount_refunded_paise = payment.get("amount_refunded", 0)
        refund_amount = amount_refunded_paise / 100.0
        amount_inr = 0.0  # Refund row has 0 base amount
        if refund_status == "partial":
            # For a partial refund, keep the original captured amount visible
            # and reference the refunded portion.
            amount_inr = (amount_paise - amount_refunded_paise) / 100.0

    # Extract GSTIN from notes or description
    notes = payment.get("notes", {}) or {}
    payer_gstin = notes.get("gstin") or notes.get("payer_gstin")

    # Build the row
    return {
        "payment_id": payment.get("id", ""),
        "order_id": payment.get("order_id", "") or "",
        "amount": amount_inr,
        "currency": payment.get("currency", "INR"),
        "status": status,
        "payment_method": payment.get("method", ""),
        "payer_gstin": payer_gstin,
        "description": payment.get("description", ""),
        "created_at": created_at.isoformat(),
        "settled_at": None,  # Razorpay settlements are separate API calls
        "settlement_id": payment.get("settlement_id"),
        "refund_of": refund_of,
        "refund_amount": refund_amount,
        "tax_period": tax_period,
        "tax_amount": round(amount_inr * 0.18, 2),  # Assume 18% GST
        "notes": notes if isinstance(notes, dict) else {},
        "source": "razorpay",
    }


def sync_transactions(
    count: int = 100,
    from_timestamp: int | None = None,
    to_timestamp: int | None = None,
    key_id: str | None = None,
    key_secret: str | None = None,
    database_url: str | None = None,
) -> dict:
    """Pull payments from Razorpay Test Mode and upsert into Supabase.

    Args:
        count: Max number of payments to fetch.
        from_timestamp: Unix timestamp — start of time range.
        to_timestamp: Unix timestamp — end of time range.
        key_id: Optional per-tenant Razorpay key id (falls back to .env).
        key_secret: Optional per-tenant Razorpay key secret.
        database_url: Optional per-tenant DB (falls back to .env).

    Returns:
        Summary dict with counts of synced, skipped, and errored records.
    """
    resolved_key_id = key_id or (get_credentials() or (None, None))[0]
    resolved_key_secret = key_secret or (get_credentials() or (None, None))[1]

    if not (resolved_key_id and resolved_key_secret):
        return {
            "status": "error",
            "message": "Razorpay credentials not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env or provide in the request.",
        }

    result = {"synced": 0, "skipped": 0, "errors": 0, "status": "ok", "message": ""}

    try:
        client = RazorpayTestClient(resolved_key_id, resolved_key_secret)

        # Fetch payments from Razorpay
        payments = client.list_payments_all(
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            max_records=count,
        )
        log.info("Fetched %d payments from Razorpay", len(payments))

        # Convert to our format
        rows = []
        for p in payments:
            row = _parse_razorpay_payment(p)
            if row is None:
                result["skipped"] += 1
                continue
            rows.append(row)

        if not rows:
            result["message"] = f"Fetched {len(payments)} payments, none converted"
            return result

        # Upsert into Supabase via psycopg
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
                        log.warning("Failed to upsert payment %s: %s", row["payment_id"], e)
                        result["errors"] += 1

                conn.commit()
        finally:
            conn.close()

        result["message"] = (
            f"Synced {result['synced']} payments from Razorpay Test Mode. "
            f"Skipped {result['skipped']}, errors: {result['errors']}"
        )
        log.info("Razorpay sync complete: %s", result["message"])

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Razorpay API error: {e}"
        log.error("Razorpay sync failed: %s", e)

    return result


def get_razorpay_status(key_id: str | None = None, key_secret: str | None = None) -> dict:
    """Check Razorpay configuration and return status info."""
    if key_id and key_secret:
        configured = True
    else:
        configured = is_configured()
        if configured:
            creds = get_credentials()
            assert creds is not None
            key_id = creds[0]

    result = {
        "configured": configured,
        "key_id": None,
        "mode": None,
    }
    if configured:
        result["key_id"] = key_id
        # Detect test vs live mode from key prefix
        if key_id.startswith("rzp_test_"):
            result["mode"] = "test"
        elif key_id.startswith("rzp_live_"):
            result["mode"] = "live"
        else:
            result["mode"] = "unknown"
    return result
