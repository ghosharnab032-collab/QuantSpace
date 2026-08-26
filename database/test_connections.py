"""Simple connectivity test for the Turso database."""

from __future__ import annotations

from connections import MissingCredentialsError, get_connection


def main() -> None:
    try:
        connection = get_connection()
    except MissingCredentialsError as exc:
        print(f"ERROR: {exc}")
        return

    try:
        result = connection.execute("SELECT 1 AS ok")
        row = result.fetchone()

        if row is None or row[0] != 1:
            print("ERROR: Turso returned an unexpected response.")
            return

        print("Turso connection: OK")

        result = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        )

        tables = [row[0] for row in result.fetchall()]

        print("Tables currently in database:")
        if tables:
            for table in tables:
                print(f"  - {table}")
        else:
            print("  (none)")

    except Exception as exc:
        print(f"ERROR: Database query failed: {type(exc).__name__}: {exc}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()