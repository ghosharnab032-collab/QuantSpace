"""Application database connection and initialization."""

from __future__ import annotations

from typing import Optional

import libsql_client

from server.config import settings
from server.db.schema import SCHEMA_STATEMENTS


_db_client: Optional[object] = None


async def get_db_client():
    """Return the shared application database client."""
    global _db_client

    if _db_client is None:
        _db_client = libsql_client.create_client(
            url=settings.database_url,
            auth_token=settings.database_auth_token or None,
        )

    return _db_client


async def close_db_client() -> None:
    """Close the application database client."""
    global _db_client

    if _db_client is not None:
        await _db_client.close()
        _db_client = None


async def init_db() -> None:
    """Create application tables."""
    client = await get_db_client()

    for statement in SCHEMA_STATEMENTS:
        await client.execute(statement)


async def check_db_connection() -> bool:
    """Check whether the database is reachable."""
    try:
        client = await get_db_client()
        result = await client.execute("SELECT 1")
        return bool(result.rows)
    except Exception:
        return False