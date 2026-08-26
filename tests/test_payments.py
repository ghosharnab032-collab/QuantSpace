"""Payment API tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from server.main import app


client = TestClient(app)


def _create_authenticated_user():
    """Create a unique authenticated test user."""

    from server.auth.jwt import create_access_token
    from server.auth.password import hash_password
    from server.db import create_user

    import asyncio

    async def setup():
        email = (
            f"payments-{uuid.uuid4().hex}"
            "@example.com"
        )

        user = await create_user(
            email=email,
            password_hash=hash_password(
                "StrongPassword123!"
            ),
        )

        token = create_access_token(
            user_id=user["id"],
        )

        return user, token

    return asyncio.run(setup())


def test_payment_order_requires_authentication():
    """Unauthenticated users cannot create orders."""

    response = client.post(
        "/api/v1/payments/order",
        json={
            "product": "monte_carlo",
            "amount": 49900,
        },
    )

    assert response.status_code == 401


def test_payment_order_rejects_unknown_product():
    """Unknown products are rejected."""

    user, token = _create_authenticated_user()

    with patch(
        "server.payments.router.create_order",
        new_callable=AsyncMock,
        side_effect=ValueError(
            "Unknown product: invalid"
        ),
    ):
        response = client.post(
            "/api/v1/payments/order",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "product": "invalid",
                "amount": 49900,
            },
        )

    assert response.status_code == 400

    assert (
        "Unknown product"
        in response.json()["detail"]
    )


def test_payment_order_success():
    """A valid order is returned to the frontend."""

    user, token = _create_authenticated_user()

    mock_order = {
        "order_id": "order_test_123",
        "amount": 49900,
        "currency": "INR",
        "key_id": "rzp_test_example",
        "product": "monte_carlo",
    }

    with patch(
        "server.payments.router.create_order",
        new_callable=AsyncMock,
        return_value=mock_order,
    ):
        response = client.post(
            "/api/v1/payments/order",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "product": "monte_carlo",
                "amount": 49900,
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["order_id"] == "order_test_123"
    assert data["amount"] == 49900
    assert data["currency"] == "INR"
    assert data["product"] == "monte_carlo"


def test_payment_order_handles_razorpay_failure():
    """Razorpay configuration failures return 503."""

    user, token = _create_authenticated_user()

    with patch(
        "server.payments.router.create_order",
        new_callable=AsyncMock,
        side_effect=RuntimeError(
            "RAZORPAY_KEY_ID is not configured."
        ),
    ):
        response = client.post(
            "/api/v1/payments/order",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "product": "monte_carlo",
                "amount": 49900,
            },
        )

    assert response.status_code == 503


def test_payment_verification_success():
    """A valid payment grants the purchased entitlement."""

    user, token = _create_authenticated_user()

    mock_result = {
        "verified": True,
        "entitlement": "monte_carlo",
    }

    with patch(
        "server.payments.router.verify_payment",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post(
            "/api/v1/payments/verify",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "razorpay_order_id": "order_test_123",
                "razorpay_payment_id": "pay_test_123",
                "razorpay_signature": "valid_signature",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["verified"] is True
    assert data["entitlement"] == "monte_carlo"


def test_payment_verification_failure():
    """Invalid Razorpay signatures are rejected."""

    user, token = _create_authenticated_user()

    with patch(
        "server.payments.router.verify_payment",
        new_callable=AsyncMock,
        side_effect=ValueError(
            "Payment verification failed."
        ),
    ):
        response = client.post(
            "/api/v1/payments/verify",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "razorpay_order_id": "order_test_123",
                "razorpay_payment_id": "pay_test_123",
                "razorpay_signature": "invalid_signature",
            },
        )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Payment verification failed."
    )