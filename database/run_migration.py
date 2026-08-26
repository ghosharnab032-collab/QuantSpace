"""Apply the quant market-data schema to Turso and verify it."""

from __future__ import annotations

import sys
from pathlib import Path

from database.connections import (
    MissingCredentialsError,
    get_connection,
)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

EXPECTED_TABLES = {
    "assets",
    "price_daily",
    "corporate_actions",
    "data_runs",
    "rejected_rows",
    "dividend_yields",
}

EXPECTED_INDEXES = {
    "idx_price_daily_ticker_date",
    "idx_corporate_actions_ticker_date",
    "idx_rejected_rows_run",
    "idx_dividend_yields_ticker_date",
}


def split_statements(sql_text: str) -> list[str]:
    """Split this schema file into individual SQL statements."""

    lines = [
        line
        for line in sql_text.splitlines()
        if not line.strip().startswith("--")
    ]

    cleaned = "\n".join(lines)

    return [
        statement.strip()
        for statement in cleaned.split(";")
        if statement.strip()
    ]


def get_existing_objects(conn) -> set[str]:
    """Return existing table/index names."""

    result = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type IN ('table', 'index')
        """
    )

    if hasattr(result, "fetchall"):
        rows = result.fetchall()
    elif hasattr(result, "rows"):
        rows = result.rows
    else:
        rows = list(result)

    return {
        str(row[0])
        for row in rows
    }


def apply_migration() -> None:
    try:
        conn = get_connection()
    except MissingCredentialsError as exc:
        print(
            f"Cannot connect to Turso: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        print(f"Reading schema from: {SCHEMA_PATH}")

        if not SCHEMA_PATH.exists():
            print(
                f"Schema file not found: {SCHEMA_PATH}",
                file=sys.stderr,
            )
            sys.exit(1)

        sql_text = SCHEMA_PATH.read_text(
            encoding="utf-8"
        )

        statements = split_statements(sql_text)

        print(
            f"Applying {len(statements)} schema statements..."
        )

        for statement in statements:
            conn.execute(statement)

        # These indexes are required by the quant data layer.
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_price_daily_ticker_date
            ON price_daily(ticker, trade_date)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_rejected_rows_run
            ON rejected_rows(run_id)
            """
        )

        conn.commit()

        print("Schema applied successfully.")

        # ----------------------------------------------------------
        # Verify
        # ----------------------------------------------------------

        existing = get_existing_objects(conn)

        print()
        print("=== DATABASE VERIFICATION ===")

        tables_found = EXPECTED_TABLES & existing
        indexes_found = EXPECTED_INDEXES & existing

        print(
            f"Tables:  {len(tables_found)}/{len(EXPECTED_TABLES)}"
        )

        for table in sorted(EXPECTED_TABLES):
            status = "OK" if table in existing else "MISSING"
            print(f"  [{status}] {table}")

        print(
            f"Indexes: {len(indexes_found)}/{len(EXPECTED_INDEXES)}"
        )

        for index in sorted(EXPECTED_INDEXES):
            status = "OK" if index in existing else "MISSING"
            print(f"  [{status}] {index}")

        missing_tables = EXPECTED_TABLES - existing
        missing_indexes = EXPECTED_INDEXES - existing

        if missing_tables or missing_indexes:
            print()
            print("MIGRATION INCOMPLETE.")

            if missing_tables:
                print(
                    "Missing tables:",
                    sorted(missing_tables),
                )

            if missing_indexes:
                print(
                    "Missing indexes:",
                    sorted(missing_indexes),
                )

            sys.exit(1)

        # ----------------------------------------------------------
        # Check price_daily row count
        # ----------------------------------------------------------

        result = conn.execute(
            "SELECT COUNT(*) FROM price_daily"
        )

        if hasattr(result, "fetchone"):
            row = result.fetchone()
            count = row[0]
        elif hasattr(result, "rows"):
            count = result.rows[0][0]
        else:
            count = list(result)[0][0]

        print()
        print(
            f"price_daily rows currently in database: {count}"
        )

        print()
        print(
            "Migration verified successfully."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    apply_migration()