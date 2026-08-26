"""Market-data application service."""

from __future__ import annotations

from datetime import date
from typing import Any

from database.connections import get_connection


def get_historical_prices(
    ticker: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Return historical OHLCV data for one ticker."""

    ticker = ticker.strip().upper()

    if not ticker:
        raise ValueError("Ticker cannot be empty.")

    conditions = ["ticker = ?"]
    params: list[Any] = [ticker]

    if start is not None:
        date.fromisoformat(start)
        conditions.append("trade_date >= ?")
        params.append(start)

    if end is not None:
        date.fromisoformat(end)
        conditions.append("trade_date <= ?")
        params.append(end)

    query = f"""
        SELECT
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            source
        FROM price_daily
        WHERE {" AND ".join(conditions)}
        ORDER BY trade_date ASC
    """

    conn = get_connection()

    try:
        result = conn.execute(query, tuple(params))

        rows = result.fetchall()

        data = [
            {
                "date": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": int(row[5]) if row[5] is not None else None,
                "source": row[6],
            }
            for row in rows
        ]

        return {
            "ticker": ticker,
            "count": len(data),
            "start": data[0]["date"] if data else None,
            "end": data[-1]["date"] if data else None,
            "data": data,
        }

    finally:
        conn.close()