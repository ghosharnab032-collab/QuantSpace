"""
Application-facing read layer for the quant toolkit.

All Turso connection details remain in database.connections.
"""

from __future__ import annotations

from typing import Any

from database.connections import get_connection


def _row_to_dict(result, row):
    """Convert a libsql tuple row into a dictionary."""
    if row is None:
        return None

    columns = [column[0] for column in result.description]
    return dict(zip(columns, row))


def _rows_to_dicts(result):
    """Convert all libsql tuple rows into dictionaries."""
    columns = [column[0] for column in result.description]
    return [
        dict(zip(columns, row))
        for row in result.fetchall()
    ]


def _price_rows(result):
    """Convert price rows and numeric fields to Python types."""
    rows = _rows_to_dicts(result)

    for row in rows:
        for field in ("open", "high", "low", "close"):
            if row[field] is not None:
                row[field] = float(row[field])

        if row["volume"] is not None:
            row["volume"] = int(row["volume"])

    return rows


def get_asset(ticker: str):
    ticker = ticker.strip().upper()

    if not ticker:
        raise ValueError("ticker must not be empty")

    conn = get_connection()

    try:
        result = conn.execute(
            """
            SELECT
                ticker,
                name,
                exchange,
                instrument_type,
                isin,
                sector,
                industry,
                face_value,
                first_listed,
                last_traded,
                benchmark_index,
                tax_type
            FROM assets
            WHERE ticker = ?
            """,
            (ticker,),
        )

        row = result.fetchone()

        return _row_to_dict(result, row)

    finally:
        conn.close()


def get_universe(instrument_type=None):
    query = """
        SELECT
            ticker,
            name,
            exchange,
            instrument_type,
            isin,
            sector,
            industry,
            face_value,
            first_listed,
            last_traded,
            benchmark_index,
            tax_type
        FROM assets
    """

    params = ()

    if instrument_type:
        query += " WHERE instrument_type = ?"
        params = (instrument_type.strip().upper(),)

    query += " ORDER BY ticker"

    conn = get_connection()

    try:
        result = conn.execute(query, params)
        return _rows_to_dicts(result)

    finally:
        conn.close()


def get_prices(ticker, start_date=None, end_date=None):
    ticker = ticker.strip().upper()

    query = """
        SELECT
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
        FROM price_daily
        WHERE ticker = ?
    """

    params = [ticker]

    if start_date:
        query += " AND trade_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND trade_date <= ?"
        params.append(end_date)

    query += " ORDER BY trade_date"

    conn = get_connection()

    try:
        result = conn.execute(query, tuple(params))
        return _price_rows(result)

    finally:
        conn.close()


def get_latest_price(ticker):
    ticker = ticker.strip().upper()

    conn = get_connection()

    try:
        result = conn.execute(
            """
            SELECT
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
            FROM price_daily
            WHERE ticker = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (ticker,),
        )

        row = result.fetchone()

        if row is None:
            return None

        columns = [column[0] for column in result.description]
        data = dict(zip(columns, row))

        for field in ("open", "high", "low", "close"):
            if data[field] is not None:
                data[field] = float(data[field])

        if data["volume"] is not None:
            data["volume"] = int(data["volume"])

        return data

    finally:
        conn.close()


def get_prices_bulk(tickers, start_date=None, end_date=None):
    tickers = sorted({
        ticker.strip().upper()
        for ticker in tickers
        if ticker and ticker.strip()
    })

    if not tickers:
        return []

    placeholders = ",".join("?" for _ in tickers)

    query = f"""
        SELECT
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
        FROM price_daily
        WHERE ticker IN ({placeholders})
    """

    params = list(tickers)

    if start_date:
        query += " AND trade_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND trade_date <= ?"
        params.append(end_date)

    query += " ORDER BY ticker, trade_date"

    conn = get_connection()

    try:
        result = conn.execute(query, tuple(params))
        return _price_rows(result)

    finally:
        conn.close()


def get_corporate_actions(
    ticker,
    start_date=None,
    end_date=None,
):
    ticker = ticker.strip().upper()

    query = """
        SELECT
            ticker,
            ex_date,
            action_type,
            ratio,
            value,
            description,
            source,
            recorded_at
        FROM corporate_actions
        WHERE ticker = ?
    """

    params = [ticker]

    if start_date:
        query += " AND ex_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND ex_date <= ?"
        params.append(end_date)

    query += " ORDER BY ex_date"

    conn = get_connection()

    try:
        result = conn.execute(query, tuple(params))
        return _rows_to_dicts(result)

    finally:
        conn.close()


def get_data_run(run_id):
    run_id = run_id.strip()

    conn = get_connection()

    try:
        result = conn.execute(
            """
            SELECT
                run_id,
                started_at,
                completed_at,
                source,
                tickers_processed,
                rows_inserted,
                rows_rejected,
                rows_warned,
                error_message
            FROM data_runs
            WHERE run_id = ?
            """,
            (run_id,),
        )

        row = result.fetchone()

        return _row_to_dict(result, row)

    finally:
        conn.close()