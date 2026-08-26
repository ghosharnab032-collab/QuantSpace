"""
data/dividend_yield_data.py
---------------------------
Sample dividend-yield dataset for testing and development.

Contains sample NSE ticker observations from 2024–2027.
All values are approximate and for testing purposes only.

Usage:
    from data.dividend_yield_data import get_sample_data, export_to_csv

    # Get as list of dicts
    rows = get_sample_data()

    # Export to CSV for loading via dividend_yield.py
    export_to_csv("dividend_yields_sample.csv")
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


# ============================================================================
# SAMPLE DATA
# ============================================================================

_SAMPLE_ROWS: list[dict[str, Any]] = [
    {"ticker": "RELIANCE",   "effective_date": "2024-01-15", "dividend_yield": 0.52,  "source": "nse"},
    {"ticker": "RELIANCE",   "effective_date": "2024-07-15", "dividend_yield": 0.55,  "source": "nse"},
    {"ticker": "TCS",        "effective_date": "2024-01-20", "dividend_yield": 1.25,  "source": "nse"},
    {"ticker": "TCS",        "effective_date": "2024-07-20", "dividend_yield": 1.35,  "source": "nse"},
    {"ticker": "INFY",       "effective_date": "2024-01-25", "dividend_yield": 2.15,  "source": "nse"},
    {"ticker": "INFY",       "effective_date": "2024-07-25", "dividend_yield": 2.42,  "source": "nse"},
    {"ticker": "HDFCBANK",   "effective_date": "2024-02-01", "dividend_yield": 1.05,  "source": "nse"},
    {"ticker": "HDFCBANK",   "effective_date": "2024-08-01", "dividend_yield": 1.12,  "source": "nse"},
    {"ticker": "ICICIBANK",  "effective_date": "2024-02-10", "dividend_yield": 0.85,  "source": "nse"},
    {"ticker": "ICICIBANK",  "effective_date": "2024-08-10", "dividend_yield": 0.92,  "source": "nse"},
    {"ticker": "SBIN",       "effective_date": "2024-03-01", "dividend_yield": 1.85,  "source": "nse"},
    {"ticker": "SBIN",       "effective_date": "2024-09-01", "dividend_yield": 1.95,  "source": "nse"},
    {"ticker": "HINDUNILVR", "effective_date": "2024-03-15", "dividend_yield": 1.42,  "source": "nse"},
    {"ticker": "HINDUNILVR", "effective_date": "2024-09-15", "dividend_yield": 1.48,  "source": "nse"},
    {"ticker": "ITC",        "effective_date": "2024-04-01", "dividend_yield": 2.85,  "source": "nse"},
    {"ticker": "ITC",        "effective_date": "2024-10-01", "dividend_yield": 2.95,  "source": "nse"},
    {"ticker": "KOTAKBANK",  "effective_date": "2024-04-10", "dividend_yield": 0.08,  "source": "nse"},
    {"ticker": "KOTAKBANK",  "effective_date": "2024-10-10", "dividend_yield": 0.10,  "source": "nse"},
    {"ticker": "BHARTIARTL", "effective_date": "2024-05-01", "dividend_yield": 0.55,  "source": "nse"},
    {"ticker": "BHARTIARTL", "effective_date": "2024-11-01", "dividend_yield": 0.58,  "source": "nse"},
    {"ticker": "AXISBANK",   "effective_date": "2024-05-15", "dividend_yield": 0.12,  "source": "nse"},
    {"ticker": "AXISBANK",   "effective_date": "2024-11-15", "dividend_yield": 0.15,  "source": "nse"},
    {"ticker": "ASIANPAINT", "effective_date": "2024-06-01", "dividend_yield": 1.05,  "source": "nse"},
    {"ticker": "ASIANPAINT", "effective_date": "2024-12-01", "dividend_yield": 1.12,  "source": "nse"},
    {"ticker": "MARUTI",     "effective_date": "2024-06-15", "dividend_yield": 0.95,  "source": "nse"},
    {"ticker": "MARUTI",     "effective_date": "2024-12-15", "dividend_yield": 1.02,  "source": "nse"},
    {"ticker": "TATAMOTORS", "effective_date": "2024-07-01", "dividend_yield": 0.35,  "source": "nse"},
    {"ticker": "TATAMOTORS", "effective_date": "2025-01-01", "dividend_yield": 0.42,  "source": "nse"},
    {"ticker": "SUNPHARMA",  "effective_date": "2024-07-15", "dividend_yield": 0.72,  "source": "nse"},
    {"ticker": "SUNPHARMA",  "effective_date": "2025-01-15", "dividend_yield": 0.78,  "source": "nse"},
    {"ticker": "NESTLEIND",  "effective_date": "2024-08-01", "dividend_yield": 1.55,  "source": "nse"},
    {"ticker": "NESTLEIND",  "effective_date": "2025-02-01", "dividend_yield": 1.62,  "source": "nse"},
    {"ticker": "WIPRO",      "effective_date": "2024-08-15", "dividend_yield": 1.95,  "source": "nse"},
    {"ticker": "WIPRO",      "effective_date": "2025-02-15", "dividend_yield": 2.05,  "source": "nse"},
    {"ticker": "POWERGRID",  "effective_date": "2024-09-01", "dividend_yield": 4.25,  "source": "nse"},
    {"ticker": "POWERGRID",  "effective_date": "2025-03-01", "dividend_yield": 4.35,  "source": "nse"},
    {"ticker": "NTPC",       "effective_date": "2024-09-15", "dividend_yield": 3.85,  "source": "nse"},
    {"ticker": "NTPC",       "effective_date": "2025-03-15", "dividend_yield": 3.92,  "source": "nse"},
    {"ticker": "COALINDIA",  "effective_date": "2024-10-01", "dividend_yield": 5.85,  "source": "nse"},
    {"ticker": "COALINDIA",  "effective_date": "2025-04-01", "dividend_yield": 6.10,  "source": "nse"},
    {"ticker": "ONGC",       "effective_date": "2024-10-15", "dividend_yield": 4.55,  "source": "nse"},
    {"ticker": "ONGC",       "effective_date": "2025-04-15", "dividend_yield": 4.72,  "source": "nse"},
    {"ticker": "ADANIENT",   "effective_date": "2024-11-01", "dividend_yield": 0.05,  "source": "nse"},
    {"ticker": "ADANIENT",   "effective_date": "2025-05-01", "dividend_yield": 0.06,  "source": "nse"},
    {"ticker": "HCLTECH",    "effective_date": "2024-11-15", "dividend_yield": 2.85,  "source": "nse"},
    {"ticker": "HCLTECH",    "effective_date": "2025-05-15", "dividend_yield": 2.95,  "source": "nse"},
    {"ticker": "ULTRACEMCO", "effective_date": "2024-12-01", "dividend_yield": 0.45,  "source": "nse"},
    {"ticker": "ULTRACEMCO", "effective_date": "2025-06-01", "dividend_yield": 0.48,  "source": "nse"},
    {"ticker": "TITAN",      "effective_date": "2024-12-15", "dividend_yield": 0.25,  "source": "nse"},
    {"ticker": "TITAN",      "effective_date": "2025-06-15", "dividend_yield": 0.28,  "source": "nse"},
    {"ticker": "BAJFINANCE", "effective_date": "2025-01-01", "dividend_yield": 0.15,  "source": "nse"},
    {"ticker": "BAJFINANCE", "effective_date": "2025-07-01", "dividend_yield": 0.18,  "source": "nse"},
    {"ticker": "LT",         "effective_date": "2025-02-01", "dividend_yield": 0.95,  "source": "nse"},
    {"ticker": "LT",         "effective_date": "2025-08-01", "dividend_yield": 1.02,  "source": "nse"},
    {"ticker": "M&M",        "effective_date": "2025-03-01", "dividend_yield": 0.65,  "source": "nse"},
    {"ticker": "M&M",        "effective_date": "2025-09-01", "dividend_yield": 0.72,  "source": "nse"},
    {"ticker": "TECHM",      "effective_date": "2025-04-01", "dividend_yield": 2.15,  "source": "nse"},
    {"ticker": "TECHM",      "effective_date": "2025-10-01", "dividend_yield": 2.25,  "source": "nse"},
    {"ticker": "DRREDDY",    "effective_date": "2025-05-01", "dividend_yield": 0.82,  "source": "nse"},
    {"ticker": "DRREDDY",    "effective_date": "2025-11-01", "dividend_yield": 0.88,  "source": "nse"},
    {"ticker": "BRITANNIA",  "effective_date": "2025-06-01", "dividend_yield": 1.35,  "source": "nse"},
    {"ticker": "BRITANNIA",  "effective_date": "2025-12-01", "dividend_yield": 1.42,  "source": "nse"},
    {"ticker": "CIPLA",      "effective_date": "2025-07-01", "dividend_yield": 0.55,  "source": "nse"},
    {"ticker": "CIPLA",      "effective_date": "2026-01-01", "dividend_yield": 0.58,  "source": "nse"},
    {"ticker": "JSWSTEEL",   "effective_date": "2025-08-01", "dividend_yield": 0.35,  "source": "nse"},
    {"ticker": "JSWSTEEL",   "effective_date": "2026-02-01", "dividend_yield": 0.38,  "source": "nse"},
    {"ticker": "GRASIM",     "effective_date": "2025-09-01", "dividend_yield": 0.42,  "source": "nse"},
    {"ticker": "GRASIM",     "effective_date": "2026-03-01", "dividend_yield": 0.45,  "source": "nse"},
    {"ticker": "TATACONSUM", "effective_date": "2025-10-01", "dividend_yield": 0.75,  "source": "nse"},
    {"ticker": "TATACONSUM", "effective_date": "2026-04-01", "dividend_yield": 0.78,  "source": "nse"},
    {"ticker": "EICHERMOT",  "effective_date": "2025-11-01", "dividend_yield": 0.55,  "source": "nse"},
    {"ticker": "EICHERMOT",  "effective_date": "2026-05-01", "dividend_yield": 0.58,  "source": "nse"},
    {"ticker": "APOLLOHOSP", "effective_date": "2025-12-01", "dividend_yield": 0.15,  "source": "nse"},
    {"ticker": "APOLLOHOSP", "effective_date": "2026-06-01", "dividend_yield": 0.18,  "source": "nse"},
    {"ticker": "HEROMOTOCO", "effective_date": "2026-01-01", "dividend_yield": 2.85,  "source": "nse"},
    {"ticker": "HEROMOTOCO", "effective_date": "2026-07-01", "dividend_yield": 2.95,  "source": "nse"},
    {"ticker": "BPCL",       "effective_date": "2026-02-01", "dividend_yield": 5.25,  "source": "nse"},
    {"ticker": "BPCL",       "effective_date": "2026-08-01", "dividend_yield": 5.45,  "source": "nse"},
    {"ticker": "INDUSINDBK", "effective_date": "2026-03-01", "dividend_yield": 0.65,  "source": "nse"},
    {"ticker": "INDUSINDBK", "effective_date": "2026-09-01", "dividend_yield": 0.68,  "source": "nse"},
    {"ticker": "DIVISLAB",   "effective_date": "2026-04-01", "dividend_yield": 0.45,  "source": "nse"},
    {"ticker": "DIVISLAB",   "effective_date": "2026-10-01", "dividend_yield": 0.48,  "source": "nse"},
    {"ticker": "BAJAJFINSV", "effective_date": "2026-05-01", "dividend_yield": 0.08,  "source": "nse"},
    {"ticker": "BAJAJFINSV", "effective_date": "2026-11-01", "dividend_yield": 0.10,  "source": "nse"},
    {"ticker": "SHRIRAMFIN", "effective_date": "2026-06-01", "dividend_yield": 1.25,  "source": "nse"},
    {"ticker": "SHRIRAMFIN", "effective_date": "2026-12-01", "dividend_yield": 1.32,  "source": "nse"},
    {"ticker": "ZOMATO",     "effective_date": "2026-07-01", "dividend_yield": 0.00,  "source": "nse"},
    {"ticker": "ZOMATO",     "effective_date": "2027-01-01", "dividend_yield": 0.00,  "source": "nse"},
    {"ticker": "PAYTM",      "effective_date": "2026-08-01", "dividend_yield": 0.00,  "source": "nse"},
    {"ticker": "PAYTM",      "effective_date": "2027-02-01", "dividend_yield": 0.00,  "source": "nse"},
]


# ============================================================================
# ACCESSORS
# ============================================================================

def get_sample_data() -> list[dict[str, Any]]:
    """Return the full sample dataset as a list of dicts."""
    return [dict(row) for row in _SAMPLE_ROWS]


def get_tickers() -> list[str]:
    """Return all unique tickers in the sample dataset."""
    return sorted({row["ticker"] for row in _SAMPLE_ROWS})


def get_by_ticker(ticker: str) -> list[dict[str, Any]]:
    """Return all observations for a specific ticker."""
    t = ticker.strip().upper()
    return [dict(row) for row in _SAMPLE_ROWS if row["ticker"] == t]


def get_yield_range() -> tuple[float, float]:
    """Return (min_yield, max_yield) across the entire dataset."""
    yields = [row["dividend_yield"] for row in _SAMPLE_ROWS]
    return min(yields), max(yields)


def get_date_range() -> tuple[str, str]:
    """Return (earliest_date, latest_date) in the dataset."""
    dates = [row["effective_date"] for row in _SAMPLE_ROWS]
    return min(dates), max(dates)


# ============================================================================
# EXPORT
# ============================================================================

def export_to_csv(path: str | Path) -> None:
    """Write the sample data to a CSV file."""
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "effective_date", "dividend_yield", "source"])
        writer.writeheader()
        writer.writerows(_SAMPLE_ROWS)
    print(f"Exported {len(_SAMPLE_ROWS)} rows to {path}")


def export_to_db(conn: Any, chunk_size: int = 250) -> int:
    """
    Insert sample data directly into the database.

    Requires dividend_yield_series.ensure_schema() to have been called first.
    """
    from data.dividend_yield_data import (
        ensure_schema,
        upsert_dividend_yields,
        load_dividend_yield_csv,
    )

    ensure_schema(conn)
    good, errors = load_dividend_yield_csv(_SAMPLE_ROWS)

    if errors:
        print(f"Warning: {len(errors)} rows failed validation")
        for e in errors[:5]:
            print(f"  {e.reason}: {e.raw}")

    affected = upsert_dividend_yields(conn, good)
    print(f"Inserted/updated {affected} rows into dividend_yields")
    return affected


# ============================================================================
# STATS
# ============================================================================

def print_summary() -> None:
    """Print a quick summary of the sample dataset."""
    tickers = get_tickers()
    min_y, max_y = get_yield_range()
    min_d, max_d = get_date_range()

    print("=" * 50)
    print("Dividend Yield Sample Data — Summary")
    print("=" * 50)
    print(f"Total rows:     {len(_SAMPLE_ROWS)}")
    print(f"Unique tickers: {len(tickers)}")
    print(f"Date range:     {min_d} → {max_d}")
    print(f"Yield range:    {min_y:.2f}% → {max_y:.2f}%")
    print(f"Tickers:        {', '.join(tickers[:10])}, ...")
    print("=" * 50)


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sample dividend-yield dataset utility."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # summary
    subparsers.add_parser("summary", help="Print dataset summary.")

    # export-csv
    p_csv = subparsers.add_parser("export-csv", help="Export to CSV file.")
    p_csv.add_argument("path", type=str, help="Output CSV file path.")

    # export-db
    p_db = subparsers.add_parser("export-db", help="Insert directly into Turso DB.")
    p_db.add_argument("--chunk-size", type=int, default=250)

    # list-tickers
    subparsers.add_parser("list-tickers", help="List all tickers.")

    # get-ticker
    p_get = subparsers.add_parser("get-ticker", help="Show data for one ticker.")
    p_get.add_argument("ticker", type=str, help="Ticker symbol.")

    args = parser.parse_args()

    if args.command == "summary":
        print_summary()

    elif args.command == "export-csv":
        export_to_csv(args.path)

    elif args.command == "export-db":
        from database.connections import get_connection
        conn = get_connection()
        try:
            export_to_db(conn, chunk_size=args.chunk_size)
        finally:
            conn.close()

    elif args.command == "list-tickers":
        for t in get_tickers():
            print(t)

    elif args.command == "get-ticker":
        rows = get_by_ticker(args.ticker)
        if rows:
            print(f"date,dividend_yield,source")
            for r in rows:
                print(f"{r['effective_date']},{r['dividend_yield']:.2f},{r['source']}")
        else:
            print(f"No data for ticker: {args.ticker}")


if __name__ == "__main__":
    main()