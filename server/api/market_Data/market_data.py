"""Market-data API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from database.connections import get_connection, rows_as_dicts


router = APIRouter(
    prefix="/market-data",
    tags=["market-data"],
)


# ============================================================
# ASSET METADATA
# ============================================================

@router.get("/assets/{ticker}")
async def get_asset(ticker: str):
    """Return metadata for a ticker."""

    ticker = ticker.strip().upper()

    if not ticker:
        raise HTTPException(
            status_code=400,
            detail="Ticker cannot be empty.",
        )

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

        rows = rows_as_dicts(result)

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Asset {ticker} not found.",
            )

        return rows[0]

    finally:
        conn.close()


# ============================================================
# HISTORICAL PRICES
# ============================================================

@router.get("/{ticker}/history")
async def get_historical_prices(
    ticker: str,
    start: date | None = None,
    end: date | None = None,
):
    """
    Return canonical historical daily OHLCV data.

    When multiple sources contain the same trading date,
    nse_api is preferred over nse_bhavcopy.

    Example:

        /api/v1/market-data/RELIANCE/history
            ?start=2026-01-01
            &end=2026-08-19
    """

    ticker = ticker.strip().upper()

    if not ticker:
        raise HTTPException(
            status_code=400,
            detail="Ticker cannot be empty.",
        )

    if start and end and start > end:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after end date.",
        )

    conn = get_connection()

    try:
        sql = """
            SELECT
                ticker,
                trade_date AS date,
                open,
                high,
                low,
                close,
                volume,
                source
            FROM (
                SELECT
                    id,
                    ticker,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,

                    ROW_NUMBER() OVER (
                        PARTITION BY ticker, trade_date
                        ORDER BY
                            CASE
                                WHEN source = 'nse_api' THEN 1
                                WHEN source = 'nse_bhavcopy' THEN 2
                                ELSE 3
                            END,
                            id ASC
                    ) AS rn

                FROM price_daily

                WHERE ticker = ?
        """

        params: list[object] = [ticker]

        if start:
            sql += """
                AND trade_date >= ?
            """
            params.append(start.isoformat())

        if end:
            sql += """
                AND trade_date <= ?
            """
            params.append(end.isoformat())

        sql += """
            )
            WHERE rn = 1
            ORDER BY date ASC
        """

        result = conn.execute(
            sql,
            tuple(params),
        )

        rows = rows_as_dicts(result)

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {ticker}.",
            )

        return {
            "ticker": ticker,
            "count": len(rows),
            "start": rows[0]["date"],
            "end": rows[-1]["date"],
            "data": rows,
        }

    finally:
        conn.close()