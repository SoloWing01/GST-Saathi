"""Razorpay integration — client, sync, and data models.

This module provides:
- RazorpayTestClient: authenticated HTTP client for Razorpay Test Mode API
- sync_transactions: pull payments from Razorpay and store in Supabase
- is_configured: check if Razorpay credentials are available

Usage:
    from razorpay import is_configured, sync_transactions

    if is_configured():
        result = sync_transactions(count=100)
"""

from razorpay.client import is_configured, get_credentials, RazorpayTestClient

__all__ = ["is_configured", "get_credentials", "RazorpayTestClient"]
