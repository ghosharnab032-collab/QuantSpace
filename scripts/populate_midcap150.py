"""
scripts/populate_midcap150.py

Backfill historical NSE OHLCV data for the current NIFTY Midcap 150
constituents using the project's existing historical_backfill pipeline.

Run from the project root:

    python scripts/populate_midcap150.py

The constituent universe is hardcoded, matching the approach used by
scripts/populate_nifty50.py.

NSE symbols are used directly. Do NOT append ".NS".

The three legacy constituent symbols below are mapped to the canonical
tickers already present in this project's assets table:

    L&TFH    -> LTF
    MINDAIND -> UNOMINDA
    SRTRANSFIN -> SHRIRAMFIN

GUJGASLTD is intentionally retained as GUJGASLTD. If it is absent from
the assets table, the script stops without modifying price data.
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


# Current NIFTY Midcap 150 constituents.
# Canonicalized to the ticker names used by this project's assets table.
MIDCAP150: tuple[str, ...] = (
    "3MINDIA",
    "AARTIIND",
    "AAVAS",
    "ABB",
    "ABBOTINDIA",
    "ATGL",
    "ABCAPITAL",
    "ABFRL",
    "AFFLE",
    "AIAENG",
    "AJANTPHARM",
    "APLLTD",
    "ALKEM",
    "ALKYLAMINE",
    "APLAPOLLO",
    "APOLLOTYRE",
    "ASHOKLEY",
    "ASTRAL",
    "ATUL",
    "AUBANK",
    "AUROPHARMA",
    "BALKRISIND",
    "BANKINDIA",
    "BATAINDIA",
    "BAYERCROP",
    "BEL",
    "BHARATFORG",
    "BHEL",
    "BLUEDART",
    "CANBK",
    "CGPOWER",
    "CLEAN",
    "COFORGE",
    "CONCOR",
    "COROMANDEL",
    "CRISIL",
    "CROMPTON",
    "CUMMINSIND",
    "DALBHARAT",
    "DEEPAKNTR",
    "DIXON",
    "LALPATHLAB",
    "EMAMILTD",
    "ENDURANCE",
    "ESCORTS",
    "EXIDEIND",
    "FEDERALBNK",
    "FORTIS",
    "GICRE",
    "GLAXO",
    "GLENMARK",
    "GODREJIND",
    "GODREJPROP",
    "GRINDWELL",
    "FLUOROCHEM",
    "GUJGASLTD",
    "GSPL",
    "HAPPSTMNDS",
    "HATSUN",
    "HAL",
    "HINDPETRO",
    "HINDZINC",
    "HONAUT",
    "ISEC",
    "IDBI",
    "IDFCFIRSTB",
    "INDIAMART",
    "INDIANB",
    "IEX",
    "INDHOTEL",
    "IRCTC",
    "IRFC",
    "IGL",
    "IPCALAB",
    "JKCEMENT",
    "JINDALSTEL",
    "JSWENERGY",
    "KAJARIACER",
    "KANSAINER",
    "LTF",
    "LTTS",
    "LAURUSLABS",
    "LICHSGFIN",
    "LINDEINDIA",
    "LODHA",
    "M&MFIN",
    "MANAPPURAM",
    "MFSL",
    "MAXHEALTH",
    "METROPOLIS",
    "UNOMINDA",
    "MPHASIS",
    "MRF",
    "NATCOPHARM",
    "NATIONALUM",
    "NAVINFLUOR",
    "NHPC",
    "NAM-INDIA",
    "NUVOCO",
    "OBEROIRLTY",
    "OIL",
    "OFSS",
    "PAGEIND",
    "POLICYBZR",
    "PERSISTENT",
    "PETRONET",
    "PFIZER",
    "PHOENIXLTD",
    "POLYCAB",
    "PFC",
    "PRESTIGE",
    "RAJESHEXPO",
    "RECLTD",
    "RELAXO",
    "SANOFI",
    "SCHAEFFLER",
    "SHRIRAMFIN",
    "SKFINDIA",
    "SOLARINDS",
    "SONACOMS",
    "STARHEALTH",
    "SUMICHEM",
    "SUNTV",
    "SUNDARMFIN",
    "SUNDRMFAST",
    "SUPREMEIND",
    "SYNGENE",
    "TATACHEM",
    "TATACOMM",
    "TATAELXSI",
    "TATAPOWER",
    "TTML",
    "NIACL",
    "RAMCOCEM",
    "THERMAX",
    "TORNTPOWER",
    "TRENT",
    "TRIDENT",
    "TIINDIA",
    "TVSMOTOR",
    "UNIONBANK",
    "UBL",
    "VBL",
    "VINATIORGA",
    "IDEA",
    "VOLTAS",
    "WHIRLPOOL",
    "YESBANK",
    "ZEEL",
    "ZFCVINDIA",
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
    print("NIFTY MIDCAP 150 HISTORICAL DATA POPULATION")
    print("=" * 72)
    print(f"Constituents : {len(MIDCAP150)}")
    print(f"Start date   : {START_DATE}")
    print(f"End date     : {END_DATE}")
    print()

    # Safety checks.
    if len(MIDCAP150) != 150:
        raise RuntimeError(
            f"Expected exactly 150 NIFTY Midcap 150 symbols, "
            f"got {len(MIDCAP150)}."
        )

    if len(set(MIDCAP150)) != 150:
        raise RuntimeError(
            "NIFTY Midcap 150 list contains duplicate symbols."
        )

    existing = get_existing_assets()

    missing = [
        ticker
        for ticker in MIDCAP150
        if ticker not in existing
    ]

    print(f"Assets present: {150 - len(missing)}/150")

    if missing:
        print()
        print("These NIFTY Midcap 150 symbols are missing from assets:")
        print("-" * 72)

        for ticker in missing:
            print(f"  {ticker}")

        print()
        print(
            "Nothing was inserted. Add the missing assets first, "
            "then rerun this script."
        )

        raise SystemExit(1)

    print("All 150 assets are present.")
    print()

    successful: list[str] = []
    failed: list[tuple[str, str]] = []

    for number, ticker in enumerate(MIDCAP150, start=1):
        print()
        print("-" * 72)
        print(f"[{number:03d}/150] {ticker}")

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
    print("NIFTY MIDCAP 150 BACKFILL COMPLETE")
    print("=" * 72)
    print(f"Successful: {len(successful)}/150")
    print(f"Failed    : {len(failed)}/150")

    if failed:
        print()
        print("FAILED TICKERS")
        print("-" * 72)

        for ticker, message in failed:
            print(f"{ticker}: {message}")

    print()
    print("FINAL PRICE ROW COUNTS")
    print("-" * 72)

    for ticker in MIDCAP150:
        print(f"{ticker:<15} {count_prices(ticker):>6}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()