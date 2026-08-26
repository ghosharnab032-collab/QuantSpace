"""
scripts/populate_nifty50.py

Backfill historical NSE OHLCV data for the current NIFTY 50
constituents using the project's existing historical_backfill pipeline.

Run from the project root:

    python .\scripts\populate_nifty50.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root (razorpay/) to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date

from data.historical_backfill import backfill_ticker
from database.connections import get_connection


# NSE symbols. Do NOT append ".NS".
NIFTY50: tuple[str, ...] = (
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
    "ASIANPAINT",
    "AXISBANK",
    "BAJAJ-AUTO",
    "BAJAJFINSV",
    "BAJFINANCE",
    "BEL",
    "BHARTIARTL",
    "CIPLA",
    "COALINDIA",
    "DRREDDY",
    "EICHERMOT",
    "ETERNAL",
    "GRASIM",
    "HCLTECH",
    "HDFCBANK",
    "HDFCLIFE",
    "HINDALCO",
    "HINDUNILVR",
    "ICICIBANK",
    "INDIGO",
    "INFY",
    "ITC",
    "JIOFIN",
    "JSWSTEEL",
    "KOTAKBANK",
    "LT",
    "M&M",
    "MARUTI",
    "MAXHEALTH",
    "NESTLEIND",
    "NTPC",
    "ONGC",
    "POWERGRID",
    "RELIANCE",
    "SBILIFE",
    "SBIN",
    "SHRIRAMFIN",
    "SUNPHARMA",
    "TATACONSUM",
    "TATASTEEL",
    "TCS",
    "TECHM",
    "TITAN",
    "TMPV",
    "TRENT",
    "ULTRACEMCO",
    "WIPRO",
)

START_DATE = "2021-01-01"
END_DATE = date.today().isoformat()


def get_existing_assets() -> set[str]:
    """Return ticker symbols already present in the assets table."""

    conn = get_connection()

    try:
        rows = conn.execute(
            "SELECT ticker FROM assets"
        ).fetchall()
    finally:
        conn.close()

    return {
        str(row[0]).strip().upper()
        for row in rows
        if row and row[0] is not None
    }


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
    print("NIFTY 50 HISTORICAL DATA POPULATION")
    print("=" * 72)
    print(f"Constituents : {len(NIFTY50)}")
    print(f"Start date   : {START_DATE}")
    print(f"End date     : {END_DATE}")
    print()

    if len(NIFTY50) != 50:
        raise RuntimeError(
            f"Expected exactly 50 NIFTY 50 symbols, got {len(NIFTY50)}."
        )

    if len(set(NIFTY50)) != 50:
        raise RuntimeError("NIFTY50 list contains duplicate symbols.")

    existing = get_existing_assets()

    missing = [
        ticker for ticker in NIFTY50
        if ticker not in existing
    ]

    print(f"Assets present: {50 - len(missing)}/50")

    if missing:
        print()
        print("These NIFTY 50 symbols are missing from assets:")
        for ticker in missing:
            print(f"  {ticker}")
        print()
        print(
            "Nothing was inserted. Add the missing assets first, "
            "then rerun this script."
        )
        raise SystemExit(1)

    print("All 50 assets are present.")
    print()

    successful: list[str] = []
    failed: list[tuple[str, str]] = []

    for number, ticker in enumerate(NIFTY50, start=1):
        print()
        print("-" * 72)
        print(f"[{number:02d}/50] {ticker}")

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
    print("NIFTY 50 BACKFILL COMPLETE")
    print("=" * 72)
    print(f"Successful: {len(successful)}/50")
    print(f"Failed    : {len(failed)}/50")

    if failed:
        print()
        print("FAILED TICKERS")
        print("-" * 72)
        for ticker, message in failed:
            print(f"{ticker}: {message}")

    print()
    print("FINAL PRICE ROW COUNTS")
    print("-" * 72)
    for ticker in NIFTY50:
        print(f"{ticker:<15} {count_prices(ticker):>6}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()