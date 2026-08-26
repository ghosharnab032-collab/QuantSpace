"""Payment database operations."""

from __future__ import annotations

from typing import Optional

from .database import get_db_client


async def create_payment(
    *,
    user_id: int,
    product: str,
    amount: int,
    currency: str,
    razorpay_order_id: str,
) -> dict:
    """Create a pending payment record."""

    client = await get_db_client()

    result = await client.execute(
        """
        INSERT INTO payments (
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
            status
        )
        VALUES (?, ?, ?, ?, ?, 'created')
        RETURNING
            id,
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
            razorpay_payment_id,
            status,
            created_at,
            verified_at
        """,
        [
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
        ],
    )

    row = result.rows[0]

    return _payment_from_row(row)


async def get_payment_by_order_id(
    razorpay_order_id: str,
) -> Optional[dict]:
    """Get a payment by Razorpay order ID."""

    client = await get_db_client()

    result = await client.execute(
        """
        SELECT
            id,
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
            razorpay_payment_id,
            status,
            created_at,
            verified_at
        FROM payments
        WHERE razorpay_order_id = ?
        """,
        [razorpay_order_id],
    )

    if not result.rows:
        return None

    return _payment_from_row(result.rows[0])


async def get_payment_by_payment_id(
    razorpay_payment_id: str,
) -> Optional[dict]:
    """Get a payment by Razorpay payment ID."""

    client = await get_db_client()

    result = await client.execute(
        """
        SELECT
            id,
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
            razorpay_payment_id,
            status,
            created_at,
            verified_at
        FROM payments
        WHERE razorpay_payment_id = ?
        """,
        [razorpay_payment_id],
    )

    if not result.rows:
        return None

    return _payment_from_row(result.rows[0])


async def mark_payment_verified(
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
) -> Optional[dict]:
    """Mark a payment as verified."""

    client = await get_db_client()

    result = await client.execute(
        """
        UPDATE payments
        SET
            razorpay_payment_id = ?,
            status = 'verified',
            verified_at = CURRENT_TIMESTAMP
        WHERE razorpay_order_id = ?
          AND status != 'verified'
        RETURNING
            id,
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
            razorpay_payment_id,
            status,
            created_at,
            verified_at
        """,
        [
            razorpay_payment_id,
            razorpay_order_id,
        ],
    )

    if not result.rows:
        return None

    return _payment_from_row(result.rows[0])


async def get_verified_payment(
    razorpay_order_id: str,
) -> Optional[dict]:
    """Return an already verified payment, if one exists."""

    client = await get_db_client()

    result = await client.execute(
        """
        SELECT
            id,
            user_id,
            product,
            amount,
            currency,
            razorpay_order_id,
            razorpay_payment_id,
            status,
            created_at,
            verified_at
        FROM payments
        WHERE razorpay_order_id = ?
          AND status = 'verified'
        """,
        [razorpay_order_id],
    )

    if not result.rows:
        return None

    return _payment_from_row(result.rows[0])


def _payment_from_row(row) -> dict:
    """Convert a database row into a payment dictionary."""

    return {
        "id": row[0],
        "user_id": row[1],
        "product": row[2],
        "amount": row[3],
        "currency": row[4],
        "razorpay_order_id": row[5],
        "razorpay_payment_id": row[6],
        "status": row[7],
        "created_at": row[8],
        "verified_at": row[9],
    }