"""
DataFrame adapter for quant engines.

Converts records from data.data_access into the pandas DataFrame
format expected by the backtester and other quant modules.
"""

from __future__ import annotations

import pandas as pd

from data.data_access import get_prices


REQUIRED_COLUMNS = {"open", "high", "low", "close"}
OPTIONAL_COLUMNS = {"volume"}


def prices_to_dataframe(
    rows: list[dict],
    *,
    require_volume: bool = False,
) -> pd.DataFrame:
    """
    Convert data_access price records into a quant-ready DataFrame.

    Output:
        DatetimeIndex named 'date'
        Columns:
            open, high, low, close
            volume (if present)

    Raises:
        ValueError for missing columns, invalid dates, duplicate dates,
        invalid numeric values, or inconsistent OHLC data.
    """
    if not rows:
        raise ValueError("No price data supplied.")

    frame = pd.DataFrame(rows)

    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(
            f"Price data missing required columns: {sorted(missing)}"
        )

    if "trade_date" not in frame.columns:
        raise ValueError("Price data must contain 'trade_date'.")

    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"],
        errors="raise",
    )

    numeric_columns = ["open", "high", "low", "close"]

    if "volume" in frame.columns:
        numeric_columns.append("volume")
    elif require_volume:
        raise ValueError("Price data does not contain 'volume'.")

    for column in numeric_columns:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="raise",
        )

    if frame["trade_date"].duplicated().any():
        raise ValueError("Price data contains duplicate trading dates.")

    if (frame[numeric_columns] <= 0).any().any():
        # Volume may legitimately be zero, so handle it separately.
        price_columns = ["open", "high", "low", "close"]

        if (frame[price_columns] <= 0).any().any():
            raise ValueError("OHLC prices must be positive.")

        if "volume" in frame.columns and (frame["volume"] < 0).any():
            raise ValueError("Volume cannot be negative.")

    if (
        (frame["high"] < frame[["open", "close"]].max(axis=1))
        | (frame["low"] > frame[["open", "close"]].min(axis=1))
    ).any():
        raise ValueError("OHLC values are inconsistent.")

    frame = frame.sort_values("trade_date")

    frame = frame.set_index("trade_date")
    frame.index.name = "date"

    columns = ["open", "high", "low", "close"]

    if "volume" in frame.columns:
        columns.append("volume")

    return frame[columns]


def get_price_dataframe(
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    require_volume: bool = False,
) -> pd.DataFrame:
    """
    Fetch prices through the data-access layer and return a DataFrame.

    The adapter does not access Turso directly.
    """
    rows = get_prices(
        ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return prices_to_dataframe(
        rows,
        require_volume=require_volume,
    )