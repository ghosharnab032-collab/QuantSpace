"""data/historical_backfill.py
---------------------------
Backfill historical NSE equity data using NseIndiaApi.

Pipeline:
    NSE API
      -> normalize_records()
      -> validate_ohlcv_series()
      -> price_daily

The requested ticker is the canonical asset identity used for database
insertion. Historical/source rows are normalized for OHLCV data, but the
price_daily foreign key must always reference the requested asset.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from data.loaders import load_nse
from data.normalization import normalize_records
from data.validation import validate_ohlcv_series, rejected_keys
from database.connections import get_connection


def generate_run_id() -> str:
    """Create a unique validation/ingestion run ID."""
    now = datetime.now(timezone.utc)
    return f"backfill_{now.strftime('%Y%m%d_%H%M%S_%f')}"


def result_rows_affected(result: Any) -> int:
    """Support both SQLite-style rowcount and Turso-style rows_affected."""
    if hasattr(result, "rows_affected"):
        return int(result.rows_affected)

    if hasattr(result, "rowcount"):
        return int(result.rowcount)

    return 0


def backfill_ticker(
    ticker: str,
    start: str,
    end: str,
) -> None:
    """Fetch, validate, and insert historical data for one canonical ticker."""

    # Keep the caller's ticker as the canonical database identity.
    ticker = ticker.strip().upper()

    if not ticker:
        raise ValueError("ticker cannot be empty.")

    run_id = generate_run_id()

    print()
    print(f"=== {ticker} ===")
    print(f"Range: {start} -> {end}")
    print(f"Run ID: {run_id}")

    # ---------------------------------------------------------------
    # 1. FETCH
    # ---------------------------------------------------------------

    raw = load_nse(
        ticker,
        start,
        end,
    )

    print(f"Fetched: {len(raw)} rows")

    if not raw:
        print("No data returned.")
        return

    # ---------------------------------------------------------------
    # 2. NORMALIZE
    #
    # normalize_records() returns:
    #
    #     (normalized_rows, normalization_rejected)
    # ---------------------------------------------------------------

    normalized, normalization_rejected = normalize_records(raw)

    print(f"Normalized: {len(normalized)} rows")
    print(
        f"Normalization rejected: "
        f"{len(normalization_rejected)} rows"
    )

    if not normalized:
        print("No valid normalized rows to validate.")
        return

    # ---------------------------------------------------------------
    # 3. VALIDATE
    #
    # Validation is performed on the normalized source rows. The
    # database identity remains the canonical ticker supplied to this
    # function.
    # ---------------------------------------------------------------

    grouped: dict[str, list[Any]] = defaultdict(list)

    for row in normalized:
        grouped[str(row.ticker).strip().upper()].append(row)

    failed_keys: set[tuple[str, Any]] = set()
    warning_count = 0

    for grouped_ticker, rows in grouped.items():
        reports = validate_ohlcv_series(
            rows,
            run_id=run_id,
        )

        for report in reports:
            if report.status.value == "WARN":
                warning_count += 1

        failed_keys.update(
            rejected_keys(reports)
        )

    valid_rows = [
        row
        for row in normalized
        if (
            str(row.ticker).strip().upper(),
            row.trade_date,
        ) not in failed_keys
    ]

    validation_rejected = (
        len(normalized) - len(valid_rows)
    )

    print(f"Validated: {len(valid_rows)} rows")
    print(
        f"Validation rejected: "
        f"{validation_rejected} rows"
    )
    print(f"Warnings: {warning_count}")

    if not valid_rows:
        print("No valid rows to insert.")
        return

    # ---------------------------------------------------------------
    # 4. INSERT
    # ---------------------------------------------------------------

    conn = get_connection()

    try:
        # Confirm that the canonical asset already exists.
        asset_result = conn.execute(
            """
            SELECT ticker
            FROM assets
            WHERE ticker = ?
            """,
            (ticker,),
        )

        if hasattr(asset_result, "rows"):
            asset_rows = asset_result.rows
        else:
            asset_rows = asset_result.fetchall()

        if not asset_rows:
            raise ValueError(
                f"{ticker} does not exist in assets table."
            )

        inserted = 0
        skipped = 0

        for row in valid_rows:
            # IMPORTANT:
            # Always use the canonical requested ticker for the FK.
            # Do not use row.ticker here because the source may contain
            # a historical/alternate security identity.
            result = conn.execute(
                """
                INSERT OR IGNORE INTO price_daily (
                    ticker,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,
                    source_file,
                    ingested_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    ticker,
                    str(row.trade_date),
                    str(row.open),
                    str(row.high),
                    str(row.low),
                    str(row.close),
                    row.volume,
                    "nse_api",
                    None,
                ),
            )

            affected = result_rows_affected(result)

            if affected:
                inserted += affected
            else:
                skipped += 1

        conn.commit()

    finally:
        conn.close()

    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")

    total_rejected = (
        len(normalization_rejected)
        + validation_rejected
    )

    print(f"Total rejected: {total_rejected}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill NSE historical OHLCV data."
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="NSE ticker symbols.",
    )

    parser.add_argument(
        "--start",
        required=True,
        help="Start date YYYY-MM-DD.",
    )

    parser.add_argument(
        "--end",
        required=True,
        help="End date YYYY-MM-DD.",
    )

    args = parser.parse_args()

    for ticker in args.tickers:
        backfill_ticker(
            ticker,
            args.start,
            args.end,
        )

    print()
    print("Backfill complete.")


if __name__ == "__main__":
    main()