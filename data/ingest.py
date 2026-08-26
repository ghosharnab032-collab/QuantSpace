"""
data/ingest.py
--------------
Ingestion coordinator for the quantitative market-data pipeline.

Responsibilities:
    1. Load source-specific market data.
    2. Normalize raw records.
    3. Per-ticker OHLCV validation.
    4. Verify that every ticker already exists in `assets`.
    5. Insert immutable price rows into `price_daily` (chunked).
    6. Record rejected rows (chunked).
    7. Record the ingestion run in `data_runs`.

Database:
    Uses the real libsql_client synchronous API (ResultSet or DB-API Cursor).

Important architecture rules:
    - asset_loader.py owns the assets table.
    - ingest.py does NOT create placeholder assets.
    - Missing assets fail loudly.
    - price_daily is treated as immutable.
    - Existing (ticker, trade_date, source) rows are skipped.
"""

from __future__ import annotations

import argparse
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data.loaders import (
    load_csv,
    load_nse_bhavcopy,
    load_nse,
)
from data.normalization import normalize_records
from data.validation import validate_ohlcv_series, rejected_keys
from database.connections import get_connection


VALID_SOURCES = {
    "nse_bhavcopy",
    "csv_export",
    "nse_api",
}


# ============================================================================
# DRIVER COMPATIBILITY
# ============================================================================

def _fetch_rows(result: Any) -> list[Any]:
    """Normalize libsql_client ResultSet vs DB-API 2.0 Cursor."""
    if hasattr(result, "rows"):
        return result.rows
    if hasattr(result, "fetchall"):
        return result.fetchall()
    return list(result)


def _rows_affected(result: Any) -> int:
    """Normalize libsql_client ResultSet.rows_affected vs Cursor.rowcount."""
    if hasattr(result, "rows_affected"):
        return result.rows_affected
    if hasattr(result, "rowcount"):
        return result.rowcount
    return 0


# ============================================================================
# TIME / RUN ID
# ============================================================================

def _generate_run_id() -> str:
    """Generate a sortable, human-readable ingestion run ID."""
    now = datetime.now(timezone.utc)
    return f"run_{now.strftime('%Y%m%d_%H%M%S_%f')}"


def _iso_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# HEARTBEAT
# ============================================================================

def _start_heartbeat(interval: float = 5.0) -> tuple[Any, threading.Thread]:
    """Print a lightweight heartbeat during database work."""
    stop_event = threading.Event()

    def beat() -> None:
        while not stop_event.wait(interval):
            print(
                f"[heartbeat] {datetime.now(timezone.utc).strftime('%H:%M:%S')} ingest still running",
                flush=True,
            )

    thread = threading.Thread(target=beat, name="ingest-heartbeat", daemon=True)
    thread.start()
    return stop_event, thread


# ============================================================================
# SOURCE DISPATCH
# ============================================================================

def _load_source(
    file_path: str | Path,
    source: str,
) -> list[dict[str, Any]]:
    """Dispatch the file to the correct source-specific loader."""
    if source == "nse_bhavcopy":
        return load_nse_bhavcopy(file_path)
    if source == "csv_export":
        return load_csv(file_path)
    raise ValueError(
        f"Unsupported ingestion source: {source!r}. "
        f"Supported sources: {sorted(VALID_SOURCES)}"
    )


# ============================================================================
# RUN AUDIT
# ============================================================================

def _create_run(
    conn: Any,
    run_id: str,
    source: str,
) -> None:
    """Create the initial data_runs record."""
    conn.execute(
        """
        INSERT INTO data_runs (
            run_id,
            started_at,
            source,
            tickers_processed,
            rows_inserted,
            rows_rejected,
            rows_warned
        )
        VALUES (?, ?, ?, 0, 0, 0, 0)
        """,
        (run_id, _iso_now(), source),
    )


def _finish_run(
    conn: Any,
    run_id: str,
    *,
    tickers_processed: int,
    rows_inserted: int,
    rows_rejected: int,
    rows_warned: int,
    error_message: str | None = None,
) -> None:
    """Finalize a data_runs record."""
    conn.execute(
        """
        UPDATE data_runs
        SET
            completed_at = ?,
            tickers_processed = ?,
            rows_inserted = ?,
            rows_rejected = ?,
            rows_warned = ?,
            error_message = ?
        WHERE run_id = ?
        """,
        (
            _iso_now(),
            tickers_processed,
            rows_inserted,
            rows_rejected,
            rows_warned,
            error_message,
            run_id,
        ),
    )


# ============================================================================
# ASSET VERIFICATION
# ============================================================================

def _get_existing_assets(
    conn: Any,
    tickers: set[str],
) -> set[str]:
    """
    Return the subset of supplied tickers that already exist in assets.
    A single query is used rather than one query per ticker.
    """
    if not tickers:
        return set()
    placeholders = ", ".join("?" for _ in tickers)
    result = conn.execute(
        f"""
        SELECT ticker
        FROM assets
        WHERE ticker IN ({placeholders})
        """,
        tuple(sorted(tickers)),
    )
    return {str(row[0]).upper() for row in _fetch_rows(result)}


def _require_assets(
    conn: Any,
    records: list[Any],
) -> set[str]:
    """
    Verify that every ticker in the batch exists in assets.
    This is intentionally a hard failure. ingest.py never creates
    incomplete asset metadata.
    """
    tickers = {str(record.ticker).upper() for record in records}
    existing = _get_existing_assets(conn, tickers)
    missing = sorted(tickers - existing)
    if missing:
        preview = ", ".join(missing[:20])
        if len(missing) > 20:
            preview += f", ... (+{len(missing) - 20} more)"
        raise ValueError(
            "Market-data ingestion requires "
            "all tickers to exist in the `assets` "
            "table first. Missing ticker(s): "
            f"{preview}. "
            "Run asset_loader.py before ingesting "
            "price data."
        )
    return existing


# ============================================================================
# PRICE INSERTION (CHUNKED)
# ============================================================================

def _insert_prices_chunked(
    conn: Any,
    records: list[Any],
    source: str,
    source_file: str,
    chunk_size: int = 250,
    delay: float = 0.0,
) -> int:
    """
    Insert immutable price rows in small, committed chunks.

    Existing rows with the same:
        ticker + trade_date + source
    are ignored rather than overwritten.
    """
    if not records:
        return 0

    query = """
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
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    ingested_at = _iso_now()
    total_inserted = 0

    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        payload = [
            (
                record.ticker,
                str(record.trade_date),
                str(record.open),
                str(record.high),
                str(record.low),
                str(record.close),
                int(record.volume) if record.volume is not None else None,
                source,
                source_file,
                ingested_at,
            )
            for record in chunk
        ]

        result = conn.executemany(query, payload)
        total_inserted += _rows_affected(result)
        processed = min(i + len(chunk), len(records))
        print(
            f"  Price chunk committed: {processed}/{len(records)} "
            f"(inserted {total_inserted})",
            flush=True,
        )

        if delay and processed < len(records):
            time.sleep(delay)

    return total_inserted


# ============================================================================
# REJECTED ROWS (CHUNKED)
# ============================================================================

def _insert_rejected_rows_chunked(
    conn: Any,
    run_id: str,
    rejected_records: list[Any],
    source: str,
    chunk_size: int = 250,
    delay: float = 0.0,
) -> int:
    """Insert normalization/validation failures into rejected_rows."""
    if not rejected_records:
        return 0

    query = """
    INSERT INTO rejected_rows (
        run_id,
        ticker,
        trade_date,
        source,
        reason,
        raw_payload,
        rejected_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    total = 0
    for i in range(0, len(rejected_records), chunk_size):
        chunk = rejected_records[i : i + chunk_size]
        payload = []

        for item in chunk:
            raw = getattr(item, "raw", None)
            if raw is None:
                raw = getattr(item, "raw_payload", None)
            reason = getattr(item, "reason", None)
            if reason is None:
                reason = getattr(item, "error", "Validation failure")

            ticker = None
            trade_date = None
            if isinstance(raw, dict):
                ticker = raw.get("ticker") or raw.get("symbol")
                trade_date_value = raw.get("trade_date") or raw.get("date")
                if trade_date_value is not None:
                    trade_date = str(trade_date_value)

            payload.append(
                (
                    run_id,
                    ticker,
                    trade_date,
                    source,
                    str(reason),
                    str(raw),
                    _iso_now(),
                )
            )

        result = conn.executemany(query, payload)
        total += _rows_affected(result)
        processed = min(i + len(chunk), len(rejected_records))
        print(
            f"  Rejected chunk committed: {processed}/{len(rejected_records)}",
            flush=True,
        )

        if delay and processed < len(rejected_records):
            time.sleep(delay)

    return total



# ============================================================================
# NSE API INGESTION
# ============================================================================

def ingest_nse_history(
    ticker: str,
    start: str,
    end: str,
    conn: Any,
    price_chunk_size: int = 250,
    rejected_chunk_size: int = 250,
    delay: float = 0.0,
) -> dict[str, Any]:
    """Ingest historical NSE API data through the normal pipeline."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty.")

    source = "nse_api"
    run_id = _generate_run_id()
    rows_loaded = rows_normalized = rows_validated = 0
    rows_inserted = rows_skipped = rows_rejected = warnings_count = 0

    _create_run(conn, run_id, source)
    conn.commit()
    heartbeat_stop, heartbeat_thread = _start_heartbeat()

    try:
        raw_records = load_nse(ticker, start, end)
        rows_loaded = len(raw_records)
        print(f"Loaded {rows_loaded} NSE records.")

        normalized_records, norm_rejected = normalize_records(raw_records)
        rows_normalized = len(normalized_records)
        print(
            f"Normalized {rows_normalized} records; "
            f"{len(norm_rejected)} rejected."
        )

        grouped: dict[str, list[Any]] = defaultdict(list)
        for record in normalized_records:
            grouped[str(record.ticker).upper()].append(record)

        failed_keys: set[tuple[str, Any]] = set()
        for grouped_ticker in sorted(grouped):
            reports = validate_ohlcv_series(
                grouped[grouped_ticker],
                run_id=run_id,
            )
            warnings_count += sum(
                1 for report in reports
                if report.status.value == "WARN"
            )
            failed_keys.update(rejected_keys(reports))

        valid_records = [
            record for record in normalized_records
            if (
                str(record.ticker).upper(),
                record.trade_date,
            ) not in failed_keys
        ]
        validation_rejected = [
            record for record in normalized_records
            if (
                str(record.ticker).upper(),
                record.trade_date,
            ) in failed_keys
        ]

        all_rejected = list(norm_rejected) + validation_rejected
        rows_validated = len(valid_records)
        rows_rejected = len(all_rejected)

        print(
            f"Validated {rows_validated} records; "
            f"{rows_rejected} rejected total."
        )

        conn.execute("BEGIN")
        try:
            _require_assets(conn, valid_records)

            rows_inserted = _insert_prices_chunked(
                conn,
                valid_records,
                source,
                f"{ticker}_{start}_{end}",
                chunk_size=price_chunk_size,
                delay=delay,
            )
            rows_skipped = rows_validated - rows_inserted

            _insert_rejected_rows_chunked(
                conn,
                run_id,
                all_rejected,
                source,
                chunk_size=rejected_chunk_size,
                delay=delay,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        _finish_run(
            conn,
            run_id,
            tickers_processed=1,
            rows_inserted=rows_inserted,
            rows_rejected=rows_rejected,
            rows_warned=warnings_count,
        )
        conn.commit()

        stats = {
            "source": source,
            "ticker": ticker,
            "rows_loaded": rows_loaded,
            "rows_normalized": rows_normalized,
            "rows_validated": rows_validated,
            "rows_inserted": rows_inserted,
            "rows_skipped": rows_skipped,
            "rows_rejected": rows_rejected,
            "warnings": warnings_count,
            "run_id": run_id,
        }

        print()
        print("=== NSE HISTORICAL INGESTION ===")
        print(f"Ticker: {ticker}")
        print(f"Range: {start} -> {end}")
        print(f"Rows loaded: {rows_loaded}")
        print(f"Rows normalized: {rows_normalized}")
        print(f"Rows validated: {rows_validated}")
        print(f"Rows inserted: {rows_inserted}")
        print(f"Rows skipped: {rows_skipped}")
        print(f"Rows rejected: {rows_rejected}")
        print(f"Warnings: {warnings_count}")
        print(f"Run ID: {run_id}")
        print("Ingestion complete.")

        return stats

    except Exception as error:
        _finish_run(
            conn,
            run_id,
            tickers_processed=1,
            rows_inserted=rows_inserted,
            rows_rejected=rows_rejected,
            rows_warned=warnings_count,
            error_message=str(error),
        )
        conn.commit()
        raise
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1.0)


def ingest_nse_history_batch(
    tickers: list[str],
    start: str,
    end: str,
    conn: Any,
    price_chunk_size: int = 250,
    rejected_chunk_size: int = 250,
    delay: float = 0.0,
) -> list[dict[str, Any]]:
    """Ingest several NSE tickers sequentially."""
    return [
        ingest_nse_history(
            ticker,
            start,
            end,
            conn,
            price_chunk_size=price_chunk_size,
            rejected_chunk_size=rejected_chunk_size,
            delay=delay,
        )
        for ticker in tickers
    ]


# ============================================================================
# INGESTION
# ============================================================================

def ingest_file(
    file_path: str | Path,
    conn: Any,
    source: str = "csv_export",
    price_chunk_size: int = 250,
    rejected_chunk_size: int = 250,
    delay: float = 0.0,
) -> dict[str, Any]:
    """
    Execute one complete market-data ingestion run.

    Pipeline:
        loader
          ↓
        normalization
          ↓
        per-ticker validation
          ↓
        asset existence check
          ↓
        immutable price insert (chunked)
          ↓
        rejected-row audit (chunked)
          ↓
        run audit
    """
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Target file not found: {file_path}")
    if source not in VALID_SOURCES:
        raise ValueError(
            f"Invalid source {source!r}. "
            f"Must be one of {sorted(VALID_SOURCES)}"
        )

    run_id = _generate_run_id()

    rows_loaded = 0
    rows_normalized = 0
    rows_validated = 0
    rows_inserted = 0
    rows_skipped = 0
    rows_rejected = 0
    warnings_count = 0
    tickers_count = 0

    # Create the audit row outside the transaction that performs
    # the market-data write so a failed transaction can still have
    # its failure recorded.
    _create_run(conn, run_id, source)
    conn.commit()

    heartbeat_stop, heartbeat_thread = _start_heartbeat()

    try:
        # ------------------------------------------------------------
        # 1. LOAD
        # ------------------------------------------------------------
        raw_records = _load_source(file_path, source)
        rows_loaded = len(raw_records)
        print(f"Loaded {rows_loaded} raw records.")

        # ------------------------------------------------------------
        # 2. NORMALIZE
        # ------------------------------------------------------------
        normalized_records, norm_rejected = normalize_records(raw_records)
        rows_normalized = len(normalized_records)
        print(f"Normalized {rows_normalized} records; {len(norm_rejected)} rejected.")

        # ------------------------------------------------------------
        # 3. VALIDATE (per-ticker)
        # ------------------------------------------------------------
        grouped: dict[str, list[Any]] = defaultdict(list)
        for record in normalized_records:
            grouped[str(record.ticker).upper()].append(record)

        failed_keys: set[tuple[str, Any]] = set()
        validation_reports: list[Any] = []
        warnings_count = 0

        for ticker in sorted(grouped):
            reports = validate_ohlcv_series(
                grouped[ticker],
                run_id=run_id,
            )
            validation_reports.extend(reports)
            warnings_count += sum(
                1 for report in reports if report.status.value == "WARN"
            )
            failed_keys.update(rejected_keys(reports))

        valid_records = [
            record
            for record in normalized_records
            if (str(record.ticker).upper(), record.trade_date) not in failed_keys
        ]

        validation_rejected = [
            record
            for record in normalized_records
            if (str(record.ticker).upper(), record.trade_date) in failed_keys
        ]

        all_rejected = list(norm_rejected) + validation_rejected
        rows_validated = len(valid_records)
        rows_rejected = len(all_rejected)
        print(f"Validated {rows_validated} records; {rows_rejected} rejected total.")

        tickers = {str(record.ticker).upper() for record in valid_records}
        tickers_count = len(tickers)

        # ------------------------------------------------------------
        # 4. START MARKET-DATA TRANSACTION
        # ------------------------------------------------------------
        conn.execute("BEGIN")

        try:
            # --------------------------------------------------------
            # 5. REQUIRE ASSET METADATA
            # --------------------------------------------------------
            _require_assets(conn, valid_records)

            # --------------------------------------------------------
            # 6. INSERT IMMUTABLE PRICES (chunked, but inside tx)
            # --------------------------------------------------------
            # Note: we commit the outer transaction AFTER all chunks.
            # If you prefer per-chunk commits, move the commit inside
            # _insert_prices_chunked and remove the outer BEGIN/COMMIT.
            rows_inserted = _insert_prices_chunked(
                conn,
                valid_records,
                source,
                file_path.name,
                chunk_size=price_chunk_size,
                delay=delay,
            )

            rows_skipped = rows_validated - rows_inserted

            # --------------------------------------------------------
            # 7. STORE REJECTED ROWS (chunked)
            # --------------------------------------------------------
            _insert_rejected_rows_chunked(
                conn,
                run_id,
                all_rejected,
                source,
                chunk_size=rejected_chunk_size,
                delay=delay,
            )

            # --------------------------------------------------------
            # 8. COMMIT MARKET-DATA TRANSACTION
            # --------------------------------------------------------
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        # ------------------------------------------------------------
        # 9. FINALIZE RUN
        # ------------------------------------------------------------
        _finish_run(
            conn,
            run_id,
            tickers_processed=tickers_count,
            rows_inserted=rows_inserted,
            rows_rejected=rows_rejected,
            rows_warned=warnings_count,
        )

    except Exception as e:
        _finish_run(
            conn,
            run_id,
            tickers_processed=tickers_count,
            rows_inserted=rows_inserted,
            rows_rejected=rows_rejected,
            rows_warned=warnings_count,
            error_message=str(e),
        )
        raise

    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1.0)

    return {
        "source": source,
        "tickers": tickers_count,
        "rows_loaded": rows_loaded,
        "rows_normalized": rows_normalized,
        "rows_validated": rows_validated,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "rows_rejected": rows_rejected,
        "warnings": warnings_count,
        "run_id": run_id,
    }


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest market OHLCV data into Turso."
    )
    parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Path to CSV or NSE UDiFF Bhavcopy ZIP.",
    )
    parser.add_argument(
        "--nse",
        nargs="+",
        help="NSE ticker(s) to fetch from the historical API.",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Historical API start date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="Historical API end date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="csv_export",
        choices=sorted(VALID_SOURCES),
        help="Data source.",
    )
    parser.add_argument(
        "--price-chunk-size",
        type=int,
        default=250,
        help="Rows per price insert chunk (default: 250).",
    )
    parser.add_argument(
        "--rejected-chunk-size",
        type=int,
        default=250,
        help="Rows per rejected-row insert chunk (default: 250).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to sleep between chunks (default: 0).",
    )
    args = parser.parse_args()

    if args.nse:
        if not args.start or not args.end:
            parser.error("--nse requires both --start and --end.")
        if args.file:
            parser.error("Do not provide a file path together with --nse.")

        conn = get_connection()
        try:
            results = ingest_nse_history_batch(
                args.nse,
                args.start,
                args.end,
                conn,
                price_chunk_size=args.price_chunk_size,
                rejected_chunk_size=args.rejected_chunk_size,
                delay=args.delay,
            )
            print()
            print("=== NSE API BATCH INGESTION ===")
            print(f"Tickers requested: {len(args.nse)}")
            print(
                "Rows inserted:",
                sum(item["rows_inserted"] for item in results),
            )
            print(
                "Rows skipped:",
                sum(item["rows_skipped"] for item in results),
            )
            print(
                "Rows rejected:",
                sum(item["rows_rejected"] for item in results),
            )
            print("Ingestion complete.")
        finally:
            conn.close()
        return

    if not args.file:
        parser.error("Provide a file path or use --nse.")

    conn = get_connection()
    try:
        stats = ingest_file(
            args.file,
            conn,
            source=args.source,
            price_chunk_size=args.price_chunk_size,
            rejected_chunk_size=args.rejected_chunk_size,
            delay=args.delay,
        )
        print()
        print("=== INGESTION ===")
        print(f"Source: {stats['source']}")
        print(f"Tickers: {stats['tickers']}")
        print(f"Rows loaded: {stats['rows_loaded']}")
        print(f"Rows normalized: {stats['rows_normalized']}")
        print(f"Rows validated: {stats['rows_validated']}")
        print(f"Rows inserted: {stats['rows_inserted']}")
        print(f"Rows skipped: {stats['rows_skipped']}")
        print(f"Rows rejected: {stats['rows_rejected']}")
        print(f"Warnings: {stats['warnings']}")
        print(f"Run ID: {stats['run_id']}")
        print()
        print("Ingestion complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()