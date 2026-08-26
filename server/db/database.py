"""Application database connection and initialization."""

from __future__ import annotations

import asyncio
from typing import Optional

import libsql

from server.config import settings
from server.db.schema import SCHEMA_STATEMENTS


class AsyncLibSQLResult:
    """Async-compatible result wrapper for a synchronous libsql cursor."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.rows = cursor.fetchall()


class AsyncLibSQLClient:
    """Async-compatible wrapper around the synchronous libsql client."""

    def __init__(self, connection):
        self._connection = connection

    async def execute(self, sql: str, args=None) -> AsyncLibSQLResult:
        """Execute SQL without blocking the async event loop."""

        def run():
            if args is None:
                return self._connection.execute(sql)

            return self._connection.execute(sql, args)

        cursor = await asyncio.to_thread(run)

        return AsyncLibSQLResult(cursor)

    async def close(self) -> None:
        """Close the underlying database connection."""
        await asyncio.to_thread(self._connection.close)


_db_client: Optional[AsyncLibSQLClient] = None


def _get_database_url() -> str:
    """Return the configured Turso/libSQL database URL."""
    return settings.database_url.strip()


async def get_db_client() -> AsyncLibSQLClient:
    """Return the shared application database client."""
    global _db_client

    if _db_client is None:
        connection = libsql.connect(
            database=_get_database_url(),
            auth_token=settings.database_auth_token or None,
        )

        _db_client = AsyncLibSQLClient(connection)

    return _db_client


async def close_db_client() -> None:
    """Close the application database client."""
    global _db_client

    if _db_client is not None:
        await _db_client.close()
        _db_client = None


async def init_db() -> None:
    """Create application tables if they do not already exist."""
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