"""Payment API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from server.auth.dependencies import get_current_user
from server.payments.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from server.payments.service import (
    create_order,
    verify_payment,
)


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.post(
    "/order",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_order(
    request: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
) -> CreateOrderResponse:
    """Create and persist a Razorpay order."""

    try:
        order = await create_order(
            user_id=current_user["id"],
            product=request.product,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CreateOrderResponse(**order)


@router.post(
    "/verify",
    response_model=VerifyPaymentResponse,
)
async def verify_payment_route(
    request: VerifyPaymentRequest,
    current_user: dict = Depends(get_current_user),
) -> VerifyPaymentResponse:
    """Verify a Razorpay payment and grant its entitlement."""

    try:
        result = await verify_payment(
            user_id=current_user["id"],
            product="monte_carlo",
            razorpay_order_id=request.razorpay_order_id,
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_signature=request.razorpay_signature,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed.",
        ) from exc

    return VerifyPaymentResponse(
        verified=result["verified"],
        entitlement=result["entitlement"],
    )
