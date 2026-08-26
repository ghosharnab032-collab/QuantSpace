"""Payment API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    """Request to create a Razorpay order."""

    product: str = Field(
        min_length=1,
        max_length=100,
    )


class CreateOrderResponse(BaseModel):
    """Razorpay order returned to the frontend."""

    order_id: str
    amount: int
    currency: str
    key_id: str
    product: str


class VerifyPaymentRequest(BaseModel):
    """Razorpay payment verification payload."""

    razorpay_order_id: str = Field(
        min_length=1,
    )

    razorpay_payment_id: str = Field(
        min_length=1,
    )

    razorpay_signature: str = Field(
        min_length=1,
    )


class VerifyPaymentResponse(BaseModel):
    """Payment verification result."""

    verified: bool
    entitlement: str | None = None
