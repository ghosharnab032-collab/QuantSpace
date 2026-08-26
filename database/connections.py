"""Turso/libSQL connection layer.

This is the only module that owns Turso connection details.

Application code should import get_connection() from this module instead
of importing libsql directly.

Required environment variables:
    TURSO_DATABASE_URL
    TURSO_AUTH_TOKEN

Credentials must never be hardcoded, printed, logged, or committed.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Sequence

import libsql

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


REQUIRED_ENV_VARS = (
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
)


class MissingCredentialsError(RuntimeError):
    """Raised when required Turso environment variables are missing."""


def _load_environment() -> None:
    """Load .env if python-dotenv is installed.

    Environment variables already set in the shell take precedence.
    """

    if load_dotenv is not None:
        load_dotenv()


def get_connection():
    """Create and return a synchronous connection to Turso.

    The caller is responsible for closing the connection.
    """

    _load_environment()

    missing = [
        name
        for name in REQUIRED_ENV_VARS
        if not os.environ.get(name)
    ]

    if missing:
        raise MissingCredentialsError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Set them in the environment or .env file."
        )

    database_url = os.environ["TURSO_DATABASE_URL"]
    auth_token = os.environ["TURSO_AUTH_TOKEN"]

    return libsql.connect(
        database=database_url,
        auth_token=auth_token,
    )


def execute(
    connection: Any,
    sql: str,
    args: Optional[Sequence[Any]] = None,
):
    """Execute SQL through the connection abstraction."""

    if args is None:
        return connection.execute(sql)

    return connection.execute(sql, args)


def rows_as_dicts(result: Any) -> list[dict[str, Any]]:
    """Convert a libsql result into ordinary dictionaries."""

    columns = [column[0] for column in result.description]

    return [
        dict(zip(columns, row))
        for row in result.fetchall()
    ]