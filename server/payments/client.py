"""Razorpay client wrapper."""

from __future__ import annotations

import razorpay

from server.config import settings


def get_razorpay_client() -> razorpay.Client:
    """Return a configured Razorpay client."""

    if not settings.razorpay_key_id:
        raise RuntimeError(
            "RAZORPAY_KEY_ID is not configured."
        )

    if not settings.razorpay_key_secret:
        raise RuntimeError(
            "RAZORPAY_KEY_SECRET is not configured."
        )

    return razorpay.Client(
        auth=(
            settings.razorpay_key_id,
            settings.razorpay_key_secret,
        )
    )