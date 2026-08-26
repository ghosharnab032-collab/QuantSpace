"""scripts/backfill_unresolved.py

Retry the currently unresolved tickers across the NIFTY 50,
NIFTY Next 50, NIFTY Midcap 150, and NIFTY Smallcap 250.

Run from the project root:

    python scripts/backfill_unresolved.py

This script only retries unresolved tickers. It uses the corrected
historical_backfill pipeline and is safe to rerun because that pipeline
uses INSERT OR IGNORE.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_backfill import backfill_ticker
from database.connections import get_connection


UNRESOLVED: tuple[str, ...] = (
    "ETERNAL",
    "JIOFIN",
    "SHRIRAMFIN",
    "TMPV",
    "ATGL",
    "LTF",
    "UNOMINDA",
    "ZFCVINDIA",
    "ACUTAAS",
    "ABREL",
    "AEGISLOG",
    "ARE&M",
    "ANGELONE",
    "CIEINDIA",
    "CEMPRO",
    "COHANCE",
    "FINCABLES",
    "HBLENGINE",
    "JSWDULUX",
    "JUBLPHARMA",
    "JWL",
    "KPIL",
    "LTFOODS",
    "NAVA",
    "PCBL",
    "PVRINOX",
    "POONAWALLA",
    "RHIM",
    "SAMMAANCAP",
    "SWANCORP",
    "TITAGARH",
    "TARIL",
    "WELSPUNLIV",
    "ADANIENSOL",
    "MOTHERSON",
    "UNITDSPR",
    "ZYDUSLIFE",
)

START_DATE = "2021-01-01"
END_DATE = date.today().isoformat()


def count_prices(ticker: str) -> int:
    """Return stored daily price rows for one ticker."""

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM price_daily
            WHERE ticker = ?
            """,
            (ticker,),
        ).fetchone()
    finally:
        conn.close()

    return int(row[0]) if row else 0


def main() -> None:
    print("=" * 72)
    print("UNRESOLVED NIFTY INDEX TICKER BACKFILL")
    print("=" * 72)
    print(f"Tickers     : {len(UNRESOLVED)}")
    print(f"Start date  : {START_DATE}")
    print(f"End date    : {END_DATE}")
    print()

    if len(UNRESOLVED) != len(set(UNRESOLVED)):
        raise RuntimeError("Unresolved ticker list contains duplicates.")

    successful: list[str] = []
    failed: list[tuple[str, str]] = []

    for number, ticker in enumerate(UNRESOLVED, start=1):
        print()
        print("-" * 72)
        print(f"[{number:02d}/{len(UNRESOLVED)}] {ticker}")

        before = count_prices(ticker)
        print(f"Rows before: {before}")

        try:
            backfill_ticker(
                ticker=ticker,
                start=START_DATE,
                end=END_DATE,
            )

            after = count_prices(ticker)

            print(f"Rows after : {after}")
            print(f"Rows added : {after - before}")

            successful.append(ticker)

        except Exception as exc:
            message = str(exc)
            print(f"FAILED: {message}")
            failed.append((ticker, message))

    print()
    print("=" * 72)
    print("UNRESOLVED TICKER BACKFILL COMPLETE")
    print("=" * 72)
    print(f"Successful: {len(successful)}/{len(UNRESOLVED)}")
    print(f"Failed    : {len(failed)}/{len(UNRESOLVED)}")

    if failed:
        print()
        print("STILL FAILED")
        print("-" * 72)

        for ticker, message in failed:
            print(f"{ticker}: {message}")

    print()
    print("FINAL PRICE ROW COUNTS")
    print("-" * 72)

    for ticker in UNRESOLVED:
        print(f"{ticker:<15} {count_prices(ticker):>6}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
