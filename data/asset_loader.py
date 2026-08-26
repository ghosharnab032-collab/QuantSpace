"""
data/asset_loader.py
--------------------
Load NSE CM security-master metadata into the Turso `assets` table.

NSE's SctySrs is mapped into the project's canonical instrument_type
values. Unsupported series are reported and skipped rather than being
silently misclassified.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import time
import threading
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from database.connections import get_connection


# ============================================================================
# NSE SERIES -> PROJECT INSTRUMENT TYPE
# ============================================================================

INSTRUMENT_MAP = {
    "EQ": "EQ",
    "BE": "EQ",
    "BZ": "EQ",
    "ETF": "ETF",
    "RE": "REIT",
    "IV": "INVIT",
    "GS": "GSEC",
    "GB": "GSEC",
    "SG": "SGB",
}

FIN_INSTRUMENT_TYPE_MAP = {
    "STK": "EQ",
    "EQUITY": "EQ",
    "EQ": "EQ",
    "ETF": "ETF",
    "REIT": "REIT",
    "INVIT": "INVIT",
    "SGB": "SGB",
    "SOVEREIGN GOLD BOND": "SGB",
    "GSEC": "GSEC",
    "GOVERNMENT SECURITY": "GSEC",
    "GOVERNMENT SECURITIES": "GSEC",
}


# ============================================================================
# DRIVER COMPATIBILITY
# ============================================================================

def _rows_affected(result: Any) -> int:
    """Normalize libsql_client ResultSet.rows_affected vs Cursor.rowcount."""
    if hasattr(result, "rows_affected"):
        return result.rows_affected
    if hasattr(result, "rowcount"):
        return result.rowcount
    return 0


# ============================================================================
# HELPERS
# ============================================================================

def _clean(value: object) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _map_instrument_type(
    fin_instrm_type: object,
    series: object,
) -> str | None:
    """
    Map NSE FinInstrmTp first, then fall back to SctySrs.
    """
    fin_type = _clean(fin_instrm_type)
    if fin_type:
        mapped = FIN_INSTRUMENT_TYPE_MAP.get(fin_type.upper())
        if mapped is not None:
            return mapped

    series_value = _clean(series)
    if series_value:
        return INSTRUMENT_MAP.get(series_value.upper())

    return None


# ============================================================================
# CSV LOADING
# ============================================================================

def load_nse_security_master(
    filepath: str | Path,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """
    Load NSE CM security master.

    Returns:
        valid assets,
        counts of unsupported NSE security series.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Security master not found: {filepath}")

    assets: list[dict[str, Any]] = []
    skipped_series: Counter[str] = Counter()

    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("Security master has no header.")

        required = {"TckrSymb", "FinInstrmNm", "SctySrs"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(
                "Security master is missing required column(s): "
                + ", ".join(sorted(missing))
            )

        for raw in reader:
            ticker = _clean(raw.get("TckrSymb"))
            if not ticker:
                continue
            ticker = ticker.upper()

            name = _clean(raw.get("FinInstrmNm"))
            if not name:
                continue

            series = (_clean(raw.get("SctySrs")) or "").upper()
            instrument_type = _map_instrument_type(
                raw.get("FinInstrmTp"), series
            )

            if instrument_type is None:
                skipped_series[series] += 1
                continue

            assets.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "exchange": "NSE",
                    "instrument_type": instrument_type,
                    "isin": _clean(raw.get("ISIN")),
                    "sector": None,
                    "industry": None,
                    "face_value": _clean(raw.get("ParVal")),
                    "first_listed": _clean(raw.get("ListgDt")),
                    "last_traded": None,
                    "benchmark_index": None,
                    "tax_type": None,
                }
            )

    return assets, skipped_series


# ============================================================================
# BHAVCOPY FILTERING
# ============================================================================

def _normalize_bhavcopy_header(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace("_", "")
        .replace(" ", "")
        .replace("-", "")
    )


def load_bhavcopy_tickers(
    filepath: str | Path,
) -> set[str]:
    """
    Read ticker symbols from an NSE Bhavcopy CSV or CSV ZIP.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Bhavcopy not found: {filepath}")

    def read_csv_stream(stream) -> set[str]:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("Bhavcopy has no header.")

        normalized_headers = {
            _normalize_bhavcopy_header(name): name
            for name in reader.fieldnames
            if name is not None
        }

        ticker_column = None
        for candidate in ("tckrsymb", "symbol", "ticker", "tradingsymbol", "securitysymbol"):
            if candidate in normalized_headers:
                ticker_column = normalized_headers[candidate]
                break

        if ticker_column is None:
            raise ValueError(
                "Could not find a ticker/symbol column in Bhavcopy. "
                f"Columns: {reader.fieldnames}"
            )

        tickers: set[str] = set()
        for row in reader:
            ticker = _clean(row.get(ticker_column))
            if ticker:
                tickers.add(ticker.upper())
        return tickers

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as archive:
            csv_names = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv") and not name.endswith("/")
            ]
            if not csv_names:
                raise ValueError("Bhavcopy ZIP contains no CSV file.")

            csv_name = max(csv_names, key=lambda name: archive.getinfo(name).file_size)

            with archive.open(csv_name, "r") as binary_stream:
                import io
                text_stream = io.TextIOWrapper(
                    binary_stream, encoding="utf-8-sig", newline=""
                )
                try:
                    return read_csv_stream(text_stream)
                finally:
                    text_stream.detach()

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return read_csv_stream(file)


def filter_assets_to_bhavcopy(
    assets: list[dict[str, Any]],
    bhavcopy_tickers: set[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    """
    Keep only assets that occur in the Bhavcopy ticker universe.

    Returns:
        matched assets,
        Bhavcopy tickers not represented by a supported asset.
    """
    asset_by_ticker = {
        asset["ticker"].upper(): asset
        for asset in assets
    }

    matched = [
        asset_by_ticker[ticker]
        for ticker in sorted(bhavcopy_tickers)
        if ticker in asset_by_ticker
    ]

    missing = bhavcopy_tickers - set(asset_by_ticker)
    return matched, missing


# ============================================================================
# HEARTBEAT
# ============================================================================

def _start_heartbeat(interval: float = 5.0) -> tuple[Any, threading.Thread]:
    """Print a lightweight heartbeat during database work."""
    stop_event = threading.Event()

    def beat() -> None:
        while not stop_event.wait(interval):
            print("[heartbeat] asset_loader still running", flush=True)

    thread = threading.Thread(
        target=beat, name="asset-loader-heartbeat", daemon=True
    )
    thread.start()
    return stop_event, thread


# ============================================================================
# DATABASE
# ============================================================================

def _insert_assets(
    conn: Any,
    assets: list[dict[str, Any]],
    *,
    batch_size: int = 250,
    delay: float = 0.5,
) -> int:
    """Insert assets using independent small transactions."""
    if not assets:
        return 0
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    query = """
        INSERT INTO assets (
            ticker, name, exchange, instrument_type, isin, sector,
            industry, face_value, first_listed, last_traded,
            benchmark_index, tax_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            name = excluded.name,
            exchange = excluded.exchange,
            instrument_type = excluded.instrument_type,
            isin = excluded.isin,
            face_value = excluded.face_value,
            first_listed = excluded.first_listed
    """

    total = 0
    for start in range(0, len(assets), batch_size):
        batch = assets[start:start + batch_size]
        payload = [
            (
                a["ticker"], a["name"], a["exchange"], a["instrument_type"],
                a["isin"], a["sector"], a["industry"], a["face_value"],
                a["first_listed"], a["last_traded"], a["benchmark_index"],
                a["tax_type"],
            )
            for a in batch
        ]

        conn.execute("BEGIN")
        try:
            result = conn.executemany(query, payload)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        total += int(_rows_affected(result))
        processed = min(start + len(batch), len(assets))
        print(f"Asset batch committed: {processed}/{len(assets)}", flush=True)

        if delay and processed < len(assets):
            time.sleep(delay)

    return total


# ============================================================================
# ORCHESTRATION
# ============================================================================

def load_assets(
    filepath: str | Path,
    *,
    bhavcopy: str | Path | None = None,
    batch_size: int = 250,
    delay: float = 0.5,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Load NSE security master, optionally filter to Bhavcopy universe,
    and upsert into the assets table.
    """
    assets, skipped_series = load_nse_security_master(filepath)

    if not assets:
        raise ValueError("No supported assets were found in the security master.")

    # Deduplicate: one row per ticker, highest-priority instrument type wins.
    instrument_priority = {
        "EQ": 0,
        "ETF": 1,
        "REIT": 2,
        "INVIT": 3,
        "SGB": 4,
        "GSEC": 5,
    }

    unique_assets: dict[str, dict[str, Any]] = {}
    for asset in assets:
        ticker = asset["ticker"]
        existing = unique_assets.get(ticker)
        if existing is None:
            unique_assets[ticker] = asset
            continue

        current_priority = instrument_priority.get(
            asset["instrument_type"], 99
        )
        existing_priority = instrument_priority.get(
            existing["instrument_type"], 99
        )
        if current_priority < existing_priority:
            unique_assets[ticker] = asset

    assets = list(unique_assets.values())

    # Optional Bhavcopy filter
    missing_bhavcopy_tickers: set[str] = set()
    if bhavcopy is not None:
        bhavcopy_tickers = load_bhavcopy_tickers(bhavcopy)
        assets, missing_bhavcopy_tickers = filter_assets_to_bhavcopy(
            assets, bhavcopy_tickers
        )
        print(f"Filtered to {len(assets)} assets matching Bhavcopy universe.")
        print(f"Unsupported Bhavcopy tickers: {len(missing_bhavcopy_tickers)}")

    if dry_run:
        print(f"\nDRY RUN -- would upsert {len(assets)} assets.")
        for asset in assets[:10]:
            t = asset["ticker"]
            n = asset["name"]
            it = asset["instrument_type"]
            print(f"  {t}: {n} ({it})")
        if len(assets) > 10:
            print(f"  ... and {len(assets) - 10} more")
        return {
            "assets": assets,
            "skipped_series": skipped_series,
            "missing_bhavcopy_tickers": missing_bhavcopy_tickers,
            "rows_affected": 0,
        }

    conn = get_connection()
    heartbeat_stop, heartbeat_thread = _start_heartbeat()

    try:
        rows_affected = _insert_assets(
            conn,
            assets,
            batch_size=batch_size,
            delay=delay,
        )
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1.0)
        conn.close()

    print()
    print(f"Rows affected: {rows_affected}")
    print("Asset loading complete.")

    return {
        "assets": assets,
        "skipped_series": skipped_series,
        "missing_bhavcopy_tickers": missing_bhavcopy_tickers,
        "rows_affected": rows_affected,
    }


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load NSE security master into Turso assets table."
    )
    parser.add_argument(
        "file",
        type=str,
        help="Path to gzipped NSE CM security master CSV.",
    )
    parser.add_argument(
        "--bhavcopy",
        type=str,
        default=None,
        help="Path to Bhavcopy ZIP/CSV to filter assets to tradeable universe.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Assets per insert chunk (default: 250).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to sleep between chunks (default: 0.5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report without touching the database.",
    )
    args = parser.parse_args()

    load_assets(
        args.file,
        bhavcopy=args.bhavcopy,
        batch_size=args.batch_size,
        delay=args.delay,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()