"""CRUD operations for application users."""

from __future__ import annotations

from typing import Any

from server.db.database import get_db_client


async def create_user(
    email: str,
    password_hash: str,
) -> dict[str, Any]:
    """Create a user."""

    client = await get_db_client()

    result = await client.execute(
        """
        INSERT INTO users (email, password_hash)
        VALUES (?, ?)
        RETURNING id, email, created_at, is_active
        """,
        [email, password_hash],
    )

    if not result.rows:
        raise RuntimeError("User creation returned no row.")

    row = result.rows[0]

    return {
        "id": row[0],
        "email": row[1],
        "created_at": row[2],
        "is_active": bool(row[3]),
    }


async def get_user_by_email(
    email: str,
) -> dict[str, Any] | None:
    """Find a user by email."""

    client = await get_db_client()

    result = await client.execute(
        """
        SELECT id, email, password_hash, created_at, is_active
        FROM users
        WHERE email = ?
        """,
        [email],
    )

    if not result.rows:
        return None

    row = result.rows[0]

    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "created_at": row[3],
        "is_active": bool(row[4]),
    }


async def get_user_by_id(
    user_id: int,
) -> dict[str, Any] | None:
    """Find a user by ID."""

    client = await get_db_client()

    result = await client.execute(
        """
        SELECT id, email, created_at, is_active
        FROM users
        WHERE id = ?
        """,
        [user_id],
    )

    if not result.rows:
        return None

    row = result.rows[0]

    return {
        "id": row[0],
        "email": row[1],
        "created_at": row[2],
        "is_active": bool(row[3]),
    }