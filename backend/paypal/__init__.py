"""PayPal integration — client, sync, and credentials.

This module provides:
- PayPalClient: authenticated HTTP client for the PayPal Reporting (Transaction
  Search) API, mirroring the Razorpay integration for GST reconciliation.
- sync_transactions: pull transactions from PayPal and store in Supabase
- is_configured: check if PayPal credentials are available

Usage:
    from paypal import is_configured, sync_transactions

    if is_configured():
        result = sync_transactions()
"""

from paypal.client import is_configured, get_credentials, PayPalClient

__all__ = ["is_configured", "get_credentials", "PayPalClient"]
