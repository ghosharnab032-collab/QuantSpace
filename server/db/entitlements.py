"""Entitlement database operations."""

from typing import Optional

from .database import get_db_client


async def grant_entitlement(
    user_id: int,
    feature: str,
    expires_at: Optional[str] = None,
) -> dict:
    """Grant or reactivate a user's entitlement."""

    client = await get_db_client()

    result = await client.execute(
        """
        INSERT INTO entitlements (
            user_id,
            feature,
            active,
            expires_at
        )
        VALUES (?, ?, 1, ?)
        ON CONFLICT(user_id, feature)
        DO UPDATE SET
            active = 1,
            expires_at = excluded.expires_at,
            updated_at = CURRENT_TIMESTAMP
        RETURNING
            id,
            user_id,
            feature,
            active,
            expires_at,
            created_at,
            updated_at
        """,
        [user_id, feature, expires_at],
    )

    row = result.rows[0]

    return {
        "id": row[0],
        "user_id": row[1],
        "feature": row[2],
        "active": bool(row[3]),
        "expires_at": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


async def get_entitlement(
    user_id: int,
    feature: str,
) -> Optional[dict]:
    """Get a user's entitlement for a feature."""

    client = await get_db_client()

    result = await client.execute(
        """
        SELECT
            id,
            user_id,
            feature,
            active,
            expires_at,
            created_at,
            updated_at
        FROM entitlements
        WHERE user_id = ?
          AND feature = ?
        """,
        [user_id, feature],
    )

    if not result.rows:
        return None

    row = result.rows[0]

    return {
        "id": row[0],
        "user_id": row[1],
        "feature": row[2],
        "active": bool(row[3]),
        "expires_at": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


async def revoke_entitlement(
    user_id: int,
    feature: str,
) -> bool:
    """Revoke a user's entitlement."""

    client = await get_db_client()

    result = await client.execute(
        """
        UPDATE entitlements
        SET
            active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
          AND feature = ?
        """,
        [user_id, feature],
    )

    return result.rows_affected > 0