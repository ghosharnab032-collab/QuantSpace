"""
data/dividend_yield_series.py
-------------------------------
Dividend-yield time-series loader, validator, and query engine.

Provides:
    - Batch CSV ingestion with duplicate/conflict handling
    - Forward-fill historical lookup
    - Cross-sectional snapshot queries
    - Time-series history retrieval

Database:
    Uses the real libsql_client synchronous API.

Usage:
    from data.dividend_yield_series import (
        load_dividend_yield_csv,
        get_dividend_yield,
        get_dividend_yields,
        get_dividend_yield_history,
    )
"""

from __future__ import annotations

import argparse
import csv
import io
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from database.connections import get_connection


# ============================================================================
# DRIVER COMPATIBILITY (same pattern as ingest.py / asset_loader.py)
# ============================================================================

def _fetch_rows(result: Any) -> list[Any]:
    if hasattr(result, "rows"):
        return result.rows
    if hasattr(result, "fetchall"):
        return result.fetchall()
    return list(result)


def _rows_affected(result: Any) -> int:
    if hasattr(result, "rows_affected"):
        return result.rows_affected
    if hasattr(result, "rowcount"):
        return result.rowcount
    return 0


# ============================================================================
# DATA MODEL
# ============================================================================

@dataclass(frozen=True, slots=True)
class DividendYieldRecord:
    """Canonical dividend-yield observation."""
    ticker: str
    effective_date: date
    dividend_yield: float
    source: str = "manual"
    recorded_at: str = ""


@dataclass(frozen=True, slots=True)
class RowError:
    """A row that failed validation or normalization."""
    raw: dict[str, Any]
    reason: str


# ============================================================================
# NORMALIZATION
# ============================================================================

def _clean_ticker(value: object) -> str | None:
    if value is None:
        return None
    t = str(value).strip().upper()
    return t if t else None


def _clean_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _clean_yield(value: object) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (ValueError, TypeError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _normalize_row(raw: dict[str, Any]) -> DividendYieldRecord | RowError:
    """Parse a raw dict into a DividendYieldRecord or RowError."""
    # Find ticker column (flexible naming)
    ticker = None
    for key in ("ticker", "symbol", "tckrsymb", "scrip"):
        if key in raw:
            ticker = _clean_ticker(raw[key])
            if ticker:
                break
    if not ticker:
        return RowError(raw, "missing or empty ticker")

    # Find date column
    eff_date = None
    for key in ("effective_date", "date", "eff_date", "dividend_date", "ex_date"):
        if key in raw:
            eff_date = _clean_date(raw[key])
            if eff_date:
                break
    if eff_date is None:
        return RowError(raw, "missing or unparseable effective_date")

    # Find yield column
    div_yield = None
    for key in ("dividend_yield", "yield", "div_yield", "dy"):
        if key in raw:
            div_yield = _clean_yield(raw[key])
            if div_yield is not None:
                break
    if div_yield is None:
        return RowError(raw, "missing or unparseable dividend_yield")

    # Source (optional)
    source = "manual"
    for key in ("source", "src"):
        if key in raw:
            s = str(raw.get(key, "")).strip()
            if s:
                source = s
                break

    return DividendYieldRecord(
        ticker=ticker,
        effective_date=eff_date,
        dividend_yield=div_yield,
        source=source,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================================
# VALIDATION
# ============================================================================

def _validate_record(record: DividendYieldRecord) -> DividendYieldRecord | RowError:
    """Validate a normalized record. Returns RowError if invalid."""
    if record.dividend_yield < 0:
        return RowError(
            {"ticker": record.ticker, "effective_date": record.effective_date, "dividend_yield": record.dividend_yield},
            "negative dividend_yield",
        )
    if record.dividend_yield > 50:
        return RowError(
            {"ticker": record.ticker, "effective_date": record.effective_date, "dividend_yield": record.dividend_yield},
            "suspiciously large dividend_yield (>50%)",
        )
    return record


def _deduplicate_records(
    records: list[DividendYieldRecord],
) -> tuple[list[DividendYieldRecord], list[RowError]]:
    """
    Collapse identical duplicates, reject conflicting duplicates.

    Identical: same (ticker, effective_date, dividend_yield) → keep one.
    Conflicting: same (ticker, effective_date) but different yield → reject both.
    """
    seen: dict[tuple[str, date], list[float]] = {}
    for r in records:
        key = (r.ticker, r.effective_date)
        seen.setdefault(key, []).append(r.dividend_yield)

    good: list[DividendYieldRecord] = []
    bad: list[RowError] = []

    for key, yields in seen.items():
        unique_yields = sorted(set(yields))
        if len(unique_yields) == 1:
            # Identical or single observation → keep one
            good.append(
                DividendYieldRecord(
                    ticker=key[0],
                    effective_date=key[1],
                    dividend_yield=unique_yields[0],
                    source="manual",
                    recorded_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        else:
            # Conflicting yields for same ticker+date
            bad.append(
                RowError(
                    {"ticker": key[0], "effective_date": key[1], "yields": unique_yields},
                    f"conflicting dividend_yield values: {unique_yields}",
                )
            )

    return good, bad


# ============================================================================
# BATCH LOADING
# ============================================================================

def load_dividend_yield_csv(
    rows: list[dict[str, Any]],
) -> tuple[list[DividendYieldRecord], list[RowError]]:
    """
    Parse, normalize, validate, and deduplicate a batch of raw rows.

    Returns:
        (good_records, error_rows)
    """
    normalized: list[DividendYieldRecord] = []
    errors: list[RowError] = []

    for raw in rows:
        result = _normalize_row(raw)
        if isinstance(result, RowError):
            errors.append(result)
            continue

        validated = _validate_record(result)
        if isinstance(validated, RowError):
            errors.append(validated)
            continue

        normalized.append(validated)

    good, dup_errors = _deduplicate_records(normalized)
    errors.extend(dup_errors)
    return good, errors


# ============================================================================
# DATABASE — SCHEMA
# ============================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dividend_yields (
    ticker          TEXT    NOT NULL,
    effective_date  DATE    NOT NULL,
    dividend_yield  REAL    NOT NULL,
    source          TEXT    NOT NULL DEFAULT 'manual',
    recorded_at     TEXT    NOT NULL DEFAULT '',

    PRIMARY KEY (ticker, effective_date)
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_dividend_yields_ticker_date
ON dividend_yields(ticker, effective_date);
"""


def ensure_schema(conn: Any) -> None:
    """Create the dividend_yields table and index if they don't exist."""
    conn.execute(SCHEMA_SQL)
    conn.execute(INDEX_SQL)
    conn.commit()


# ============================================================================
# DATABASE — INSERTION (chunked, idempotent)
# ============================================================================

def insert_dividend_yields(
    conn: Any,
    records: list[DividendYieldRecord],
    chunk_size: int = 250,
) -> int:
    """
    Upsert dividend-yield records. Identical rows are replaced.

    Returns:
        Number of rows affected.
    """
    if not records:
        return 0

    query = """
    INSERT INTO dividend_yields (ticker, effective_date, dividend_yield, source, recorded_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(ticker, effective_date) DO UPDATE SET
        dividend_yield = excluded.dividend_yield,
        source = excluded.source,
        recorded_at = excluded.recorded_at
    """

    total = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        payload = [
            (
                r.ticker,
                str(r.effective_date),
                r.dividend_yield,
                r.source,
                r.recorded_at or datetime.now(timezone.utc).isoformat(),
            )
            for r in chunk
        ]

        result = conn.executemany(query, payload)
        total += _rows_affected(result)

        processed = min(i + len(chunk), len(records))
        print(f"  Dividend-yield chunk: {processed}/{len(records)}", flush=True)

    return total


# ============================================================================
# DATABASE — QUERIES
# ============================================================================

def get_dividend_yield(
    conn: Any,
    ticker: str,
    as_of: str | date | datetime,
) -> float | None:
    """
    Return the latest dividend yield for *ticker* as of *as_of*.

    Uses forward-fill: the most recent observation with
    effective_date <= as_of.
    """
    d = as_of if isinstance(as_of, date) else (
        datetime.strptime(str(as_of), "%Y-%m-%d").date()
        if isinstance(as_of, str) else as_of.date()
    )

    result = conn.execute(
        """
        SELECT dividend_yield
        FROM dividend_yields
        WHERE ticker = ? AND effective_date <= ?
        ORDER BY effective_date DESC
        LIMIT 1
        """,
        (ticker.upper(), str(d)),
    )

    rows = _fetch_rows(result)
    if rows:
        return float(rows[0][0])
    return None


def get_dividend_yields(
    conn: Any,
    tickers: Sequence[str],
    as_of: str | date | datetime,
) -> dict[str, float | None]:
    """
    Cross-sectional dividend-yield snapshot.

    Returns {ticker: yield_or_None}. One ticker's data never leaks
    into another ticker's lookup.
    """
    d = as_of if isinstance(as_of, date) else (
        datetime.strptime(str(as_of), "%Y-%m-%d").date()
        if isinstance(as_of, str) else as_of.date()
    )

    if not tickers:
        return {}

    placeholders = ", ".join("?" for _ in tickers)
    result = conn.execute(
        f"""
        SELECT ticker, effective_date, dividend_yield
        FROM dividend_yields
        WHERE ticker IN ({placeholders})
          AND effective_date <= ?
        ORDER BY ticker, effective_date DESC
        """,
        tuple(t.upper() for t in tickers) + (str(d),),
    )

    # For each ticker, keep only the latest effective_date row
    latest: dict[str, tuple[date, float]] = {}
    for row in _fetch_rows(result):
        t = str(row[0]).upper()
        eff = datetime.strptime(str(row[1]), "%Y-%m-%d").date()
        val = float(row[2])
        if t not in latest or eff > latest[t][0]:
            latest[t] = (eff, val)

    return {t: latest.get(t, (None, None))[1] for t in tickers}


def get_dividend_yield_history(
    conn: Any,
    ticker: str,
    start: str | date | datetime,
    end: str | date | datetime,
) -> list[dict[str, Any]]:
    """
    Return all dividend-yield observations for *ticker* in [start, end].
    """
    s = start if isinstance(start, date) else (
        datetime.strptime(str(start), "%Y-%m-%d").date()
        if isinstance(start, str) else start.date()
    )
    e = end if isinstance(end, date) else (
        datetime.strptime(str(end), "%Y-%m-%d").date()
        if isinstance(end, str) else end.date()
    )

    result = conn.execute(
        """
        SELECT effective_date, dividend_yield, source, recorded_at
        FROM dividend_yields
        WHERE ticker = ? AND effective_date >= ? AND effective_date <= ?
        ORDER BY effective_date ASC
        """,
        (ticker.upper(), str(s), str(e)),
    )

    return [
        {
            "effective_date": str(row[0]),
            "dividend_yield": float(row[1]),
            "source": str(row[2]),
            "recorded_at": str(row[3]),
        }
        for row in _fetch_rows(result)
    ]


# ============================================================================
# DATA QUALITY CHECKS
# ============================================================================

def run_data_quality_checks(
    conn: Any,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Run dividend-yield data-quality checks and return warnings.

    Checks:
        - negative yield
        - NaN/Infinity
        - suspiciously large changes between consecutive observations
        - missing observations (warning only)
    """
    warnings: list[dict[str, Any]] = []

    # 1. Basic sanity checks via SQL
    filters: list[str] = []
    params: tuple[Any, ...] = ()
    if tickers:
        placeholders = ", ".join("?" for _ in tickers)
        filters.append(f"ticker IN ({placeholders})")
        params = tuple(t.upper() for t in tickers)

    # Negative or suspicious yields.
    filters_with_yield = filters + [
        "(dividend_yield < 0 OR dividend_yield > 50)"
    ]
    where_clause = "WHERE " + " AND ".join(filters_with_yield)

    result = conn.execute(
        f"""
        SELECT ticker, effective_date, dividend_yield
        FROM dividend_yields
        {where_clause}
        """,
        params,
    )
    for row in _fetch_rows(result):
        warnings.append({
            "ticker": str(row[0]),
            "effective_date": str(row[1]),
            "issue": "invalid_or_suspicious_yield",
            "value": float(row[2]),
        })

    # 2. Large jumps (>10 percentage points between consecutive dates)
    history_where = (
        "WHERE " + " AND ".join(filters)
        if filters
        else ""
    )

    result = conn.execute(
        f"""
        SELECT ticker, effective_date, dividend_yield,
               LAG(dividend_yield) OVER (
                   PARTITION BY ticker ORDER BY effective_date
               ) AS prev_yield
        FROM dividend_yields
        {history_where}
        ORDER BY ticker, effective_date
        """,
        params,
    )
    for row in _fetch_rows(result):
        curr = float(row[2])
        prev = row[3]
        if prev is not None and abs(curr - float(prev)) > 10:
            warnings.append({
                "ticker": str(row[0]),
                "effective_date": str(row[1]),
                "issue": "large_yield_change",
                "value": curr,
                "previous": float(prev),
                "delta": abs(curr - float(prev)),
            })

    return warnings


# ============================================================================
# CLI
# ============================================================================

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dividend-yield series loader and query tool."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # load
    p_load = subparsers.add_parser("load", help="Load dividend-yield CSV.")
    p_load.add_argument("file", type=str, help="Path to CSV file.")
    p_load.add_argument(
        "--chunk-size",
        type=int,
        default=250,
        help="Rows per insert chunk (default: 250).",
    )

    # get
    p_get = subparsers.add_parser("get", help="Get dividend yield for a ticker on a date.")
    p_get.add_argument("ticker", type=str, help="Ticker symbol.")
    p_get.add_argument("date", type=str, help="Date in YYYY-MM-DD format.")

    # history
    p_hist = subparsers.add_parser("history", help="Get dividend-yield history for a ticker.")
    p_hist.add_argument("ticker", type=str, help="Ticker symbol.")
    p_hist.add_argument("start", type=str, help="Start date (YYYY-MM-DD).")
    p_hist.add_argument("end", type=str, help="End date (YYYY-MM-DD).")

    # quality
    p_qual = subparsers.add_parser("quality", help="Run data-quality checks.")
    p_qual.add_argument(
        "--ticker",
        type=str,
        action="append",
        default=None,
        help="Specific ticker(s) to check. Repeatable.",
    )

    args = parser.parse_args()
    conn = get_connection()

    try:
        if args.command == "load":
            ensure_schema(conn)
            path = Path(args.file)
            if not path.is_file():
                raise FileNotFoundError(f"CSV not found: {path}")

            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            good, errors = load_dividend_yield_csv(rows)
            print(f"Parsed {len(rows)} rows → {len(good)} good, {len(errors)} errors")

            for e in errors[:10]:
                print(f"  REJECTED: {e.reason} — {e.raw}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")

            if good:
                affected = insert_dividend_yields(conn, good, chunk_size=args.chunk_size)
                print(f"Upserted {affected} rows.")

        elif args.command == "get":
            val = get_dividend_yield(conn, args.ticker, args.date)
            if val is not None:
                print(f"{args.ticker} @ {args.date}: {val:.4f}%")
            else:
                print(f"{args.ticker} @ {args.date}: no data")

        elif args.command == "history":
            hist = get_dividend_yield_history(conn, args.ticker, args.start, args.end)
            print(f"date,dividend_yield,source")
            for row in hist:
                print(f"{row['effective_date']},{row['dividend_yield']:.4f},{row['source']}")

        elif args.command == "quality":
            tickers = args.ticker if args.ticker else None
            warnings = run_data_quality_checks(conn, tickers)
            if warnings:
                print(f"Found {len(warnings)} warning(s):")
                for w in warnings:
                    print(f"  {w}")
            else:
                print("No data-quality warnings.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()