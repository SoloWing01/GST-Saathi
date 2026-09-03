"""Phase 3 — Create tables and seed synthetic transaction data.

Creates:
1. pgvector extension (for KB embeddings)
2. `transactions` table — Razorpay-style payment/settlement records
3. `gst_kb_embeddings` table — KB embeddings with pgvector
4. Seeds transactions with synthetic data including deliberate mismatches

Run once:
    cd backend && uv run python -m db.setup_phase3
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS transactions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payment_id      text NOT NULL UNIQUE,       -- Razorpay-style payment ID
    order_id        text NOT NULL,              -- Razorpay-style order ID
    amount          numeric(12,2) NOT NULL,     -- Payment amount in INR
    currency        text NOT NULL DEFAULT 'INR',
    status          text NOT NULL,              -- captured, failed, refunded, pending
    payment_method  text,                       -- upi, netbanking, card, wallet
    payer_gstin     text,                       -- GSTIN of the payer (if B2B)
    description     text,
    created_at      timestamptz NOT NULL,
    settled_at      timestamptz,               -- When settled to merchant
    settlement_id   text,                       -- Razorpay settlement batch ID
    refund_of       text,                       -- payment_id this refund relates to
    refund_amount   numeric(12,2) DEFAULT 0,
    tax_period      text NOT NULL,              -- e.g. "2024-07" or "Apr-Jun 2024"
    tax_amount      numeric(12,2) DEFAULT 0,    -- GST collected on this payment
    notes           jsonb
);

CREATE INDEX IF NOT EXISTS idx_txn_tax_period ON transactions(tax_period);
CREATE INDEX IF NOT EXISTS idx_txn_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_txn_created ON transactions(created_at);
"""

DDL_GST_KB_EMBEDDINGS = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS gst_kb_embeddings (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    filename        text NOT NULL,              -- source markdown filename
    section         text NOT NULL,              -- e.g. "ASMT-10", "Section 73"
    title           text NOT NULL,              -- human-readable title
    content         text NOT NULL,              -- full markdown content
    embedding       vector(384) NOT NULL,       -- all-MiniLM-L6-v2 = 384 dims
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_embedding ON gst_kb_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 5);
"""

# ---------------------------------------------------------------------------
# Synthetic transaction data
# ---------------------------------------------------------------------------

# Merchant GSTIN for our synthetic scenario
MERCHANT_GSTIN = "27AABCU9603R1ZM"
MERCHANT_NAME = "QUICK COMMERCE PRIVATE LIMITED"

def _generate_transactions() -> list[dict]:
    """Generate ~40 synthetic Razorpay transactions across Q1 FY 2024-25 (Apr-Jun).

    Includes:
    - Normal captured payments
    - Refunds (some matched, some unmatched)
    - Settlement records
    - Deliberate mismatches for testing:
      a) TIMING LAG: settlement 7 days after capture (not same-day)
      b) UNRECONCILED REFUND: refund exists but no matching payment record
      c) GENUINE GAP: GSTR-3B shows 11,80,000 but GSTR-1 shows 12,45,000
      d) ITC MISMATCH: ITC claimed > ITC available in GSTR-2B
    """
    txns = []
    base_date = datetime(2024, 4, 1, tzinfo=timezone.utc)
    rng_seed = 42

    def _rid():
        nonlocal rng_seed
        rng_seed += 1
        return f"pay_{uuid.uuid5(uuid.NAMESPACE_DNS, f'txn-{rng_seed}').hex[:14]}"

    def _oid():
        nonlocal rng_seed
        rng_seed += 1
        return f"order_{uuid.uuid5(uuid.NAMESPACE_DNS, f'ord-{rng_seed}').hex[:14]}"

    def _sid():
        nonlocal rng_seed
        rng_seed += 1
        return f"setl_{uuid.uuid5(uuid.NAMESPACE_DNS, f'set-{rng_seed}').hex[:14]}"

    # --- Normal B2B payments (April) ---
    april_amounts = [45000, 32000, 18500, 67000, 23000, 89000, 12000, 54000, 38000, 71000]
    for i, amt in enumerate(april_amounts):
        created = base_date + timedelta(days=i)
        settled = created + timedelta(days=1)  # normal T+1 settlement
        tax = round(amt * 0.18, 2)
        txns.append({
            "payment_id": _rid(),
            "order_id": _oid(),
            "amount": amt,
            "currency": "INR",
            "status": "captured",
            "payment_method": ["upi", "netbanking", "card", "wallet"][i % 4],
            "payer_gstin": f"24{'BCDPQ' if i % 2 == 0 else 'XYZAB'}{1000+i:04d}N1Z{'5' if i % 2 else '3'}",
            "description": f"B2B supply — Invoice INV-2024-04-{100+i}",
            "created_at": created.isoformat(),
            "settled_at": settled.isoformat(),
            "settlement_id": _sid(),
            "refund_of": None,
            "refund_amount": 0,
            "tax_period": "Apr-Jun 2024",
            "tax_amount": tax,
            "notes": {"invoice_number": f"INV-2024-04-{100+i}", "type": "b2b"},
        })

    # --- Normal B2B payments (May) ---
    may_amounts = [55000, 29000, 76000, 41000, 33000, 19000, 62000, 48000, 85000, 27000]
    for i, amt in enumerate(may_amounts):
        created = base_date + timedelta(days=30 + i)
        settled = created + timedelta(days=1)
        tax = round(amt * 0.18, 2)
        txns.append({
            "payment_id": _rid(),
            "order_id": _oid(),
            "amount": amt,
            "currency": "INR",
            "status": "captured",
            "payment_method": ["upi", "card", "netbanking", "wallet"][i % 4],
            "payer_gstin": f"24{'ACDEF' if i % 2 == 0 else 'GHIJK'}{2000+i:04d}N1Z{'5' if i % 2 else '3'}",
            "description": f"B2B supply — Invoice INV-2024-05-{200+i}",
            "created_at": created.isoformat(),
            "settled_at": settled.isoformat(),
            "settlement_id": _sid(),
            "refund_of": None,
            "refund_amount": 0,
            "tax_period": "Apr-Jun 2024",
            "tax_amount": tax,
            "notes": {"invoice_number": f"INV-2024-05-{200+i}", "type": "b2b"},
        })

    # --- Normal B2B payments (June) ---
    june_amounts = [36000, 58000, 44000, 72000, 21000, 65000, 39000, 51000, 83000, 28000]
    for i, amt in enumerate(june_amounts):
        created = base_date + timedelta(days=60 + i)
        settled = created + timedelta(days=1)
        tax = round(amt * 0.18, 2)
        txns.append({
            "payment_id": _rid(),
            "order_id": _oid(),
            "amount": amt,
            "currency": "INR",
            "status": "captured",
            "payment_method": ["upi", "wallet", "card", "netbanking"][i % 4],
            "payer_gstin": f"24{'LMNOP' if i % 2 == 0 else 'QRSTU'}{3000+i:04d}N1Z{'5' if i % 2 else '3'}",
            "description": f"B2B supply — Invoice INV-2024-06-{300+i}",
            "created_at": created.isoformat(),
            "settled_at": settled.isoformat(),
            "settlement_id": _sid(),
            "refund_of": None,
            "refund_amount": 0,
            "tax_period": "Apr-Jun 2024",
            "tax_amount": tax,
            "notes": {"invoice_number": f"INV-2024-06-{300+i}", "type": "b2b"},
        })

    # --- DELIBERATE MISMATCH A: Timing lag ---
    # Payment on 15-May, settled on 25-May (10 days instead of T+1)
    timing_lag_payment = _rid()
    txns.append({
        "payment_id": timing_lag_payment,
        "order_id": _oid(),
        "amount": 78000,
        "currency": "INR",
        "status": "captured",
        "payment_method": "netbanking",
        "payer_gstin": "27ZZZZZ1234N1Z5",
        "description": "B2B supply — Large order (late settlement)",
        "created_at": "2024-05-15T10:30:00+00:00",
        "settled_at": "2024-05-25T18:00:00+00:00",  # 10-day lag!
        "settlement_id": _sid(),
        "refund_of": None,
        "refund_amount": 0,
        "tax_period": "Apr-Jun 2024",
        "tax_amount": 14040,
        "notes": {"invoice_number": "INV-2024-05-TIMELAG", "type": "b2b", "flag": "timing_lag"},
    })

    # --- DELIBERATE MISMATCH B: Refund without matching payment ---
    # A refund of ₹25,000 but the original payment is NOT in our records
    orphan_refund_id = _rid()
    txns.append({
        "payment_id": orphan_refund_id,
        "order_id": _oid(),
        "amount": 0,
        "currency": "INR",
        "status": "refunded",
        "payment_method": "card",
        "payer_gstin": "27OLDGSTIN9N1Z3",
        "description": "Refund — original payment predates our records",
        "created_at": "2024-06-10T14:00:00+00:00",
        "settled_at": "2024-06-12T10:00:00+00:00",
        "settlement_id": _sid(),
        "refund_of": "pay_original_not_in_records",  # DOES NOT EXIST
        "refund_amount": 25000,
        "tax_period": "Apr-Jun 2024",
        "tax_amount": -4500,  # Negative — refund of tax
        "notes": {"invoice_number": "REF-ORPHAN-001", "type": "refund", "flag": "unreconciled_refund"},
    })

    # --- DELIBERATE MISMATCH C: Genuine gap — payment captured but GSTR-3B shows less ---
    # This ₹65,000 payment is in our books (GSTR-1) but not reflected in GSTR-3B
    gap_payment_id = _rid()
    txns.append({
        "payment_id": gap_payment_id,
        "order_id": _oid(),
        "amount": 65000,
        "currency": "INR",
        "status": "captured",
        "payment_method": "upi",
        "payer_gstin": "09ABCDEF1234N1Z1",
        "description": "B2B supply — Included in GSTR-1 but missing from GSTR-3B",
        "created_at": "2024-06-20T09:15:00+00:00",
        "settled_at": "2024-06-21T16:00:00+00:00",
        "settlement_id": _sid(),
        "refund_of": None,
        "refund_amount": 0,
        "tax_period": "Apr-Jun 2024",
        "tax_amount": 11700,
        "notes": {"invoice_number": "INV-2024-06-GAP", "type": "b2b", "flag": "gstr3b_gap"},
    })

    # --- DELIBERATE MISMATCH D: ITC claimed more than available ---
    # A payment where ITC was claimed at ₹2,10,000 but GSTR-2B shows only ₹1,85,000
    itc_mismatch_id = _rid()
    txns.append({
        "payment_id": itc_mismatch_id,
        "order_id": _oid(),
        "amount": 120000,
        "currency": "INR",
        "status": "captured",
        "payment_method": "netbanking",
        "payer_gstin": MERCHANT_GSTIN,  # Our own GSTIN — this is ITC for us
        "description": "ITC purchase — ITC claimed exceeds GSTR-2B available",
        "created_at": "2024-04-08T11:00:00+00:00",
        "settled_at": "2024-04-09T17:30:00+00:00",
        "settlement_id": _sid(),
        "refund_of": None,
        "refund_amount": 0,
        "tax_period": "Apr-Jun 2024",
        "tax_amount": 21600,
        "notes": {
            "invoice_number": "INV-SUPPLIER-ITC-001",
            "type": "itc_purchase",
            "itc_claimed": 210000,
            "itc_in_gstr2b": 185000,
            "flag": "itc_mismatch",
        },
    })

    # --- DELIBERATE MISMATCH E: Refund to correct payment (normal case) ---
    refund_for_txn5 = txns[4]["payment_id"]  # Refund for the 5th April payment (₹23,000)
    txns.append({
        "payment_id": _rid(),
        "order_id": txns[4]["order_id"],
        "amount": 0,
        "currency": "INR",
        "status": "refunded",
        "payment_method": "upi",
        "payer_gstin": txns[4]["payer_gstin"],
        "description": "Partial refund — goods returned",
        "created_at": "2024-05-05T08:00:00+00:00",
        "settled_at": "2024-05-07T12:00:00+00:00",
        "settlement_id": _sid(),
        "refund_of": refund_for_txn5,
        "refund_amount": 15000,
        "tax_period": "Apr-Jun 2024",
        "tax_amount": -2700,
        "notes": {"invoice_number": "REF-001", "type": "refund", "flag": "matched_refund"},
    })

    return txns


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
    print("=== Phase 3 Setup ===\n")

    # 1. Enable pgvector + create tables
    print("1. Creating tables...")
    # Create tables first (without IVFFlat index — needs data to train)
    _run_ddl(DDL_GST_KB_EMBEDDINGS.replace(
        "CREATE INDEX IF NOT EXISTS idx_kb_embedding ON gst_kb_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 5);",
        "-- IVFFlat index deferred until after data insertion"
    ))
    print("   - gst_kb_embeddings table + pgvector extension ready")

    _run_ddl(DDL_TRANSACTIONS)
    print("   - transactions table ready")

    # 2. Seed transactions
    print("\n2. Seeding synthetic transactions...")
    from db.supabase_client import get_client

    client = get_client()
    if client is None:
        print("   ERROR: Supabase client not configured", file=sys.stderr)
        sys.exit(1)

    # Check if data already exists
    existing = client.table("transactions").select("id").limit(1).execute()
    if existing.data:
        print("   Transactions table already has data — skipping seed")
    else:
        txns = _generate_transactions()
        # Insert in batches (Supabase handles up to 1000 rows per insert)
        for i in range(0, len(txns), 50):
            batch = txns[i:i+50]
            client.table("transactions").insert(batch).execute()
        print(f"   Inserted {len(txns)} synthetic transactions")

    # 3. Verify mismatch records
    print("\n3. Verifying deliberate mismatches...")
    mismatches = client.table("transactions").select("*").contains(
        "notes", {"flag": "timing_lag"}
    ).execute()
    print(f"   Timing lag records: {len(mismatches.data)}")

    orphan = client.table("transactions").select("*").contains(
        "notes", {"flag": "unreconciled_refund"}
    ).execute()
    print(f"   Unreconciled refund records: {len(orphan.data)}")

    gap = client.table("transactions").select("*").contains(
        "notes", {"flag": "gstr3b_gap"}
    ).execute()
    print(f"   GSTR-3B gap records: {len(gap.data)}")

    itc = client.table("transactions").select("*").contains(
        "notes", {"flag": "itc_mismatch"}
    ).execute()
    print(f"   ITC mismatch records: {len(itc.data)}")

    # 4. Summary
    total = client.table("transactions").select("id", count="exact").execute()
    print(f"\n4. Total transactions: {total.count}")

    # Query by tax period
    q1 = client.table("transactions").select("id", count="exact").eq(
        "tax_period", "Apr-Jun 2024"
    ).execute()
    print(f"   Q1 FY 2024-25 transactions: {q1.count}")

    print("\n=== Phase 3 Setup Complete ===")


if __name__ == "__main__":
    setup()
