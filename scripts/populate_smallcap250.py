"""scripts/populate_smallcap250.py

Backfill historical NSE OHLCV data for the current NIFTY Smallcap 250
constituents using the project's existing historical_backfill pipeline.

Run from the project root:

    python scripts/populate_smallcap250.py

The constituent universe is hardcoded, matching the project's NIFTY 50
and NIFTY Midcap 150 population scripts.

NSE symbols are used directly. Do NOT append ".NS".
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


SMALLCAP250: tuple[str, ...] = (
    "SONACOMS",
    "KARURVYSYA",
    "NAVINFLUOR",
    "DELHIVERY",
    "PIRAMALFIN",
    "ATHERENERG",
    "CDSL",
    "RBLBANK",
    "WELCORP",
    "KIMS",
    "ACMESOLAR",
    "AADHARHFC",
    "AARTIIND",
    "AAVAS",
    "ACE",
    "ACUTAAS",
    "ABFRL",
    "ABLBL",
    "ABREL",
    "ABSLAMC",
    "CPPLUS",
    "AEGISLOG",
    "AEGISVOPAK",
    "AFCONS",
    "AFFLE",
    "ABDL",
    "ARE&M",
    "AMBER",
    "ANANDRATHI",
    "ANANTRAJ",
    "ANGELONE",
    "ANURAS",
    "APTUS",
    "ASAHIINDIA",
    "ASTERDM",
    "ATUL",
    "BEML",
    "BLS",
    "BALRAMCHIN",
    "BANDHANBNK",
    "BATAINDIA",
    "BAYERCROP",
    "BELRISE",
    "BIKAJI",
    "BSOFT",
    "BLUEDART",
    "BLUEJET",
    "BBTC",
    "FIRSTCRY",
    "BRIGADE",
    "MAPMYINDIA",
    "CCL",
    "CESC",
    "CIEINDIA",
    "CANFINHOME",
    "CANHLIFE",
    "CAPLIPOINT",
    "CGCL",
    "CARBORUNIV",
    "CARTRADE",
    "CASTROLIND",
    "CEATLTD",
    "CEMPRO",
    "CENTRALBK",
    "CHALET",
    "CHAMBLFERT",
    "CHENNPETRO",
    "CHOICEIN",
    "CHOLAHLDNG",
    "CUB",
    "CLEAN",
    "COHANCE",
    "CAMS",
    "CONCORDBIO",
    "CRAFTSMAN",
    "CREDITACC",
    "CROMPTON",
    "CYIENT",
    "DCMSHRIRAM",
    "DOMS",
    "DATAPATTNS",
    "DEEPAKFERT",
    "DEEPAKNTR",
    "DEVYANI",
    "LALPATHLAB",
    "EIDPARRY",
    "EIHOTEL",
    "ELECON",
    "ELGIEQUIP",
    "EMAMILTD",
    "EMCURE",
    "EMMVEE",
    "ENGINERSIN",
    "ERIS",
    "FACT",
    "FINCABLES",
    "FSL",
    "FIVESTAR",
    "FORCEMOT",
    "GABRIEL",
    "GALLANTT",
    "GRSE",
    "GILLETTE",
    "GLAND",
    "GODIGIT",
    "GPIL",
    "GRANULES",
    "GRAPHITE",
    "GRAVITA",
    "GESHIP",
    "GMDCLTD",
    "HEG",
    "HBLENGINE",
    "HFCL",
    "HSCL",
    "HINDCOPPER",
    "HOMEFIRST",
    "HONASA",
    "IDBI",
    "IFCI",
    "IIFL",
    "IRB",
    "IRCON",
    "ITI",
    "INDGN",
    "INDIACEM",
    "INDIAMART",
    "IEX",
    "IOB",
    "IGL",
    "INOXWIND",
    "INTELLECT",
    "IGIL",
    "IKS",
    "JBMA",
    "JKTYRE",
    "JMFINANCIL",
    "JSWCEMENT",
    "JSWDULUX",
    "JAINREC",
    "JPPOWER",
    "J&KBANK",
    "JINDALSAW",
    "JUBLINGREA",
    "JUBLPHARMA",
    "JWL",
    "JYOTICNC",
    "KAJARIACER",
    "KPIL",
    "KAYNES",
    "KEC",
    "KFINTECH",
    "KIRLOSENG",
    "LTFOODS",
    "LATENTVIEW",
    "THELEELA",
    "LEMONTREE",
    "MMTC",
    "MGL",
    "MANAPPURAM",
    "MRPL",
    "MEESHO",
    "MINDACORP",
    "MSUMI",
    "NATCOPHARM",
    "NBCC",
    "NCC",
    "NSLNISP",
    "NH",
    "NAVA",
    "NETWEB",
    "NEULANDLAB",
    "NEWGEN",
    "NIVABUPA",
    "NUVAMA",
    "NUVOCO",
    "OLAELEC",
    "OLECTRA",
    "ONESOURCE",
    "PCBL",
    "PGEL",
    "PNBHOUSING",
    "PTCIL",
    "PVRINOX",
    "PARADEEP",
    "PFIZER",
    "PWL",
    "PINELABS",
    "PPLPHARMA",
    "POLYMED",
    "POONAWALLA",
    "PFOCUS",
    "RRKABEL",
    "RHIM",
    "RITES",
    "RAILTEL",
    "RAINBOW",
    "RKFORGE",
    "REDINGTON",
    "RPOWER",
    "SBFC",
    "SAGILITY",
    "SAILIFE",
    "SAMMAANCAP",
    "SAPPHIRE",
    "SARDAEN",
    "SAREGAMA",
    "SCHNEIDER",
    "SCI",
    "SHYAMMETL",
    "SIGNATURE",
    "SOBHA",
    "SONATSOFTW",
    "STARHEALTH",
    "SUMICHEM",
    "SUNTV",
    "SPLPETRO",
    "SWANCORP",
    "SYNGENE",
    "SYRMA",
    "TBOTEK",
    "TATACHEM",
    "TATATECH",
    "TTML",
    "TECHNOE",
    "TEGA",
    "TEJASNET",
    "TENNIND",
    "RAMCOCEM",
    "TIMKEN",
    "TITAGARH",
    "TARIL",
    "TRAVELFOOD",
    "TRIDENT",
    "TRITURBINE",
    "UCOBANK",
    "UTIAMC",
    "URBANCO",
    "USHAMART",
    "VTL",
    "VIJAYA",
    "WELSPUNLIV",
    "WHIRLPOOL",
    "WOCKPHARMA",
    "ZFCVINDIA",
    "ZEEL",
    "ZENTEC",
    "ZENSARTECH",
    "ZYDUSWELL",
    "ECLERX",
)

START_DATE = "2021-01-01"
END_DATE = date.today().isoformat()


def get_existing_assets() -> set[str]:
    """Return ticker symbols already present in the assets table."""

    conn = get_connection()

    try:
        rows = conn.execute("SELECT ticker FROM assets").fetchall()
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
            "SELECT COUNT(*) FROM price_daily WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    finally:
        conn.close()

    return int(row[0]) if row else 0


def main() -> None:
    print("=" * 72)
    print("NIFTY SMALLCAP 250 HISTORICAL DATA POPULATION")
    print("=" * 72)
    print(f"Constituents : {len(SMALLCAP250)}")
    print(f"Start date   : {START_DATE}")
    print(f"End date     : {END_DATE}")
    print()

    if len(SMALLCAP250) != 250:
        raise RuntimeError(
            f"Expected exactly 250 NIFTY Smallcap 250 symbols, "
            f"got {len(SMALLCAP250)}."
        )

    if len(set(SMALLCAP250)) != 250:
        raise RuntimeError(
            "NIFTY Smallcap 250 list contains duplicate symbols."
        )

    existing = get_existing_assets()

    missing = [
        ticker
        for ticker in SMALLCAP250
        if ticker not in existing
    ]

    print(f"Assets present: {250 - len(missing)}/250")

    if missing:
        print()
        print("These NIFTY Smallcap 250 symbols are missing from assets:")
        print("-" * 72)

        for ticker in missing:
            print(f"  {ticker}")

        print()
        print(
            "Nothing was inserted. Add the missing assets first, "
            "then rerun this script."
        )

        raise SystemExit(1)

    print("All 250 assets are present.")
    print()

    successful: list[str] = []
    failed: list[tuple[str, str]] = []

    for number, ticker in enumerate(SMALLCAP250, start=1):
        print()
        print("-" * 72)
        print(f"[{number:03d}/250] {ticker}")

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
    print("NIFTY SMALLCAP 250 BACKFILL COMPLETE")
    print("=" * 72)
    print(f"Successful: {len(successful)}/250")
    print(f"Failed    : {len(failed)}/250")

    if failed:
        print()
        print("FAILED TICKERS")
        print("-" * 72)

        for ticker, message in failed:
            print(f"{ticker}: {message}")

    print()
    print("FINAL PRICE ROW COUNTS")
    print("-" * 72)

    for ticker in SMALLCAP250:
        print(f"{ticker:<15} {count_prices(ticker):>6}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
