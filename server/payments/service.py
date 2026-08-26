"""Payment business logic with persistence and idempotency."""

from __future__ import annotations

from server.config import settings
from server.db import (
    create_payment,
    get_payment_by_order_id,
    get_payment_by_payment_id,
    get_verified_payment,
    grant_entitlement,
    mark_payment_verified,
)
from server.payments.client import get_razorpay_client


PRODUCT_ENTITLEMENTS = {
    "monte_carlo": "monte_carlo",
}

# Amounts are server-controlled and are expressed in paise.
PRODUCT_PRICES = {
    "monte_carlo": 49900,
}


async def create_order(
    *,
    user_id: int,
    product: str,
) -> dict:
    """Create a Razorpay order and persist the order locally."""

    if product not in PRODUCT_ENTITLEMENTS:
        raise ValueError(
            f"Unknown product: {product}"
        )

    amount = PRODUCT_PRICES[product]

    if amount <= 0:
        raise ValueError(
            "Configured product price must be greater than zero."
        )

    client = get_razorpay_client()

    order = client.order.create(
        {
            "amount": amount,
            "currency": "INR",
            "receipt": f"{product}-{user_id}",
            "notes": {
                "product": product,
                "user_id": str(user_id),
            },
        }
    )

    payment = await create_payment(
        user_id=user_id,
        product=product,
        amount=amount,
        currency=order["currency"],
        razorpay_order_id=order["id"],
    )

    return {
        "order_id": payment["razorpay_order_id"],
        "amount": payment["amount"],
        "currency": payment["currency"],
        "key_id": settings.razorpay_key_id,
        "product": payment["product"],
    }


async def verify_payment(
    *,
    user_id: int,
    product: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict:
    """
    Verify a Razorpay payment and grant entitlement idempotently.

    The order must already exist in our local payments table.
    """

    if product not in PRODUCT_ENTITLEMENTS:
        raise ValueError(
            f"Unknown product: {product}"
        )

    # ---------------------------------------------------------------
    # 1. Check whether this order was already verified.
    # ---------------------------------------------------------------

    existing_verified = await get_verified_payment(
        razorpay_order_id,
    )

    if existing_verified is not None:
        if existing_verified["user_id"] != user_id:
            raise ValueError(
                "Payment does not belong to this user."
            )

        return {
            "verified": True,
            "entitlement": PRODUCT_ENTITLEMENTS[
                existing_verified["product"]
            ],
        }

    # ---------------------------------------------------------------
    # 2. Check whether this payment ID has already been used.
    # ---------------------------------------------------------------

    existing_payment = await get_payment_by_payment_id(
        razorpay_payment_id,
    )

    if existing_payment is not None:
        if existing_payment["user_id"] != user_id:
            raise ValueError(
                "Payment does not belong to this user."
            )

        if existing_payment["status"] == "verified":
            return {
                "verified": True,
                "entitlement": PRODUCT_ENTITLEMENTS[
                    existing_payment["product"]
                ],
            }

        raise ValueError(
            "Payment has already been processed."
        )

    # ---------------------------------------------------------------
    # 3. Find the locally-created order.
    # ---------------------------------------------------------------

    payment = await get_payment_by_order_id(
        razorpay_order_id,
    )

    if payment is None:
        raise ValueError(
            "Payment order was not found."
        )

    if payment["user_id"] != user_id:
        raise ValueError(
            "Payment does not belong to this user."
        )

    if payment["product"] != product:
        raise ValueError(
            "Payment product does not match the order."
        )

    if payment["status"] == "verified":
        return {
            "verified": True,
            "entitlement": PRODUCT_ENTITLEMENTS[
                payment["product"]
            ],
        }

    # ---------------------------------------------------------------
    # 4. Verify the Razorpay signature.
    # ---------------------------------------------------------------

    client = get_razorpay_client()

    client.utility.verify_payment_signature(
        {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        }
    )

    # ---------------------------------------------------------------
    # 5. Mark the local payment as verified.
    # ---------------------------------------------------------------

    verified_payment = await mark_payment_verified(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
    )

    if verified_payment is None:
        existing_verified = await get_verified_payment(
            razorpay_order_id,
        )

        if existing_verified is None:
            raise ValueError(
                "Payment could not be verified."
            )

        if existing_verified["user_id"] != user_id:
            raise ValueError(
                "Payment does not belong to this user."
            )

        return {
            "verified": True,
            "entitlement": PRODUCT_ENTITLEMENTS[
                existing_verified["product"]
            ],
        }

    # ---------------------------------------------------------------
    # 6. Grant the entitlement.
    # ---------------------------------------------------------------

    entitlement = PRODUCT_ENTITLEMENTS[
        verified_payment["product"]
    ]

    await grant_entitlement(
        user_id,
        entitlement,
    )

    return {
        "verified": True,
        "entitlement": entitlement,
    }
