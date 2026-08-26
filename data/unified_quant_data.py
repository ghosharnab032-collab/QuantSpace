"""
data/unified_quant_data.py
--------------------------
Unified Quant Data Interface — application-facing API.

Thin wrapper over existing data modules. No business logic here.

Sections:
    1. Market data access
    2. Reference data (risk-free rate, dividend yield)
    3. Asset metadata & classification
    4. Calendar & time utilities
    5. Data quality & validation helpers
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from .data_access import (
    get_asset,
    get_prices as _get_prices,
    get_prices_bulk,
    get_universe as _get_universe,
)
from .data_quality import check_price_rows
from .dividend_yield_series import (
    get_dividend_yield as _get_dividend_yield,
    get_dividend_yields as _get_dividend_yields,
    get_dividend_yield_history as _get_dividend_yield_history,
)
from .historical_queries import (
    get_available_date_range,
    get_common_trading_dates as _get_common_trading_dates,
    get_latest_available_price as _get_latest_available_price,
    get_missing_dates as _get_missing_dates,
)
from .risk_free_rate import RiskFreeRate, rate_as_of
from .trading_calendar import get_calendar
from database.connections import get_connection


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(
        f"Expected date, datetime, or ISO date string; "
        f"got {type(value).__name__}."
    )


# ---------------------------------------------------------------------------
# 1. Market Data Access
# ---------------------------------------------------------------------------

def get_prices(
    ticker: str,
    start: date | datetime | str | None = None,
    end: date | datetime | str | None = None,
):
    """Return OHLCV rows for a ticker in the requested date range."""
    start_date = _to_date(start).isoformat() if start is not None else None
    end_date = _to_date(end).isoformat() if end is not None else None
    return _get_prices(ticker, start_date=start_date, end_date=end_date)


def get_returns(
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
    freq: str = "daily",
    return_type: str = "simple",
):
    """
    Return a DataFrame of returns.
    Only daily frequency is supported.
    return_type: "simple" or "log".
    """
    if freq.lower() != "daily":
        raise ValueError("Only freq='daily' is currently supported.")
    if return_type not in {"simple", "log"}:
        raise ValueError("return_type must be 'simple' or 'log'.")

    import numpy as np
    import pandas as pd

    rows = get_prices(ticker, start, end)
    if not rows:
        return pd.DataFrame(columns=["return"])

    frame = pd.DataFrame(rows)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values("trade_date").set_index("trade_date")
    close = pd.to_numeric(frame["close"], errors="coerce")

    if return_type == "simple":
        values = close.pct_change()
    else:
        values = np.log(close / close.shift(1))

    return pd.DataFrame({"return": values})


def get_universe():
    """Return all available assets."""
    return _get_universe()


def get_common_dates(
    tickers: Sequence[str],
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[date]:
    """Return dates for which every requested ticker has price data."""
    return _get_common_trading_dates(tickers, start, end)


def get_latest_prices(
    tickers: Sequence[str],
    as_of_date: date | datetime | str | None = None,
) -> list[dict]:
    """
    Return the latest available price for each ticker.
    When as_of_date is supplied, no price after that date is returned.
    """
    valuation_date = _to_date(as_of_date) if as_of_date is not None else None
    results = []
    for ticker in tickers:
        row = _get_latest_available_price(ticker, valuation_date)
        if row is not None:
            results.append(row)
    return results


def get_price_matrix(
    tickers: Sequence[str],
    start: date | datetime | str,
    end: date | datetime | str,
):
    """Return a DataFrame of close prices indexed by date."""
    import pandas as pd

    rows = get_prices_bulk(
        tickers,
        start_date=_to_date(start).isoformat(),
        end_date=_to_date(end).isoformat(),
    )
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    matrix = frame.pivot(index="trade_date", columns="ticker", values="close")
    return matrix.sort_index()


# ---------------------------------------------------------------------------
# 2. Reference Data
# ---------------------------------------------------------------------------

def get_risk_free_rate(
    valuation_date: date | datetime | str,
    rates: Sequence[RiskFreeRate],
) -> RiskFreeRate:
    """Return the applicable risk-free rate as of valuation_date."""
    return rate_as_of(rates, _to_date(valuation_date))


def get_risk_free_curve(
    dates: Sequence[date | datetime | str],
    rates: Sequence[RiskFreeRate],
) -> list[RiskFreeRate]:
    """Return the applicable rate for each requested date."""
    return [get_risk_free_rate(day, rates) for day in dates]


def get_dividend_yield(
    ticker: str,
    valuation_date: date | datetime | str,
) -> float | None:
    """Return ticker-specific dividend yield as of valuation_date."""
    conn = get_connection()
    try:
        return _get_dividend_yield(conn, ticker, _to_date(valuation_date))
    finally:
        conn.close()


def get_dividend_yields(
    tickers: Sequence[str],
    valuation_date: date | datetime | str,
) -> dict[str, float | None]:
    """Return dividend yields for all requested tickers."""
    conn = get_connection()
    try:
        return _get_dividend_yields(conn, tickers, _to_date(valuation_date))
    finally:
        conn.close()


def get_dividend_yield_history(
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[dict]:
    """Return dividend-yield history for a ticker in [start, end]."""
    conn = get_connection()
    try:
        return _get_dividend_yield_history(
            conn, ticker, _to_date(start), _to_date(end)
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Asset Metadata & Classification
# ---------------------------------------------------------------------------

def get_asset_info(ticker: str):
    """Return application-facing asset metadata."""
    return get_asset(ticker)


def get_assets_by_sector(sector: str) -> list[dict]:
    """Return assets belonging to a sector."""
    target = sector.strip().casefold()
    return [
        asset
        for asset in get_universe()
        if (asset.get("sector") or "").strip().casefold() == target
    ]


def get_assets_by_instrument_type(instrument_type: str) -> list[dict]:
    """Return assets matching an instrument type."""
    target = instrument_type.strip().upper()
    return [
        asset
        for asset in get_universe()
        if (asset.get("instrument_type") or "").strip().upper() == target
    ]


def get_tax_type(ticker: str):
    """Return the tax classification stored for an asset."""
    asset = get_asset_info(ticker)
    return asset.get("tax_type") if asset else None


def get_benchmark_index(ticker: str):
    """Return the benchmark index stored for an asset."""
    asset = get_asset_info(ticker)
    return asset.get("benchmark_index") if asset else None


# ---------------------------------------------------------------------------
# 4. Calendar & Time Utilities
# ---------------------------------------------------------------------------

def is_trading_day(day: date | datetime | str) -> bool:
    return get_calendar().is_trading_day(_to_date(day))


def get_next_trading_day(day: date | datetime | str) -> date:
    return get_calendar().next_trading_day(_to_date(day))


def get_previous_trading_day(day: date | datetime | str) -> date:
    return get_calendar().previous_trading_day(_to_date(day))


def get_trading_days_between(
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[date]:
    return get_calendar().get_trading_days(_to_date(start), _to_date(end))


def count_trading_days(
    start: date | datetime | str,
    end: date | datetime | str,
) -> int:
    return len(get_trading_days_between(start, end))


def align_to_trading_calendar(
    dates: Sequence[date | datetime | str],
    direction: str = "forward",
) -> list[date]:
    """
    Align dates that are not trading sessions.
    direction: "forward" -> next trading day, "backward" -> previous.
    """
    if direction not in {"forward", "backward"}:
        raise ValueError("direction must be 'forward' or 'backward'.")

    cal = get_calendar()
    aligned = []
    for value in dates:
        day = _to_date(value)
        if cal.is_trading_day(day):
            aligned.append(day)
        elif direction == "forward":
            aligned.append(cal.next_trading_day(day))
        else:
            aligned.append(cal.previous_trading_day(day))
    return aligned


# ---------------------------------------------------------------------------
# 5. Data Quality & Validation Helpers
# ---------------------------------------------------------------------------

def check_quality(
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
):
    """Run data-quality checks for a ticker/date range."""
    rows = get_prices(ticker, start=start, end=end)
    return check_price_rows(
        rows,
        ticker=ticker,
        start=_to_date(start),
        end=_to_date(end),
        calendar=get_calendar(),
    )


def get_missing_dates(
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[date]:
    """Return expected NSE sessions missing from price_daily."""
    return _get_missing_dates(
        ticker,
        start,
        end,
        calendar=get_calendar(),
    )


def has_sufficient_history(ticker: str, min_days: int = 252) -> bool:
    """Return True when at least min_days price rows are available."""
    if min_days < 1:
        raise ValueError("min_days must be >= 1.")
    return len(get_prices(ticker)) >= min_days


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def self_check() -> None:
    """Focused interface smoke test using existing project data."""

    ticker = "RELIANCE"
    date_range = get_available_date_range(ticker)

    assert date_range is not None
    start, end = date_range

    # 1. Market data.
    prices = get_prices(ticker, start, end)
    assert prices
    assert {"open", "high", "low", "close", "volume"} <= set(prices[0])
    print("1. Market data access: OK")

    returns = get_returns(ticker, start, end)
    assert "return" in returns.columns
    print("2. Returns DataFrame: OK")

    universe = get_universe()
    assert universe
    print("3. Universe: OK")

    common = get_common_dates(["RELIANCE", "TCS"], start, end)
    assert common == sorted(common)
    print("4. Common dates: OK")

    latest = get_latest_prices(["RELIANCE"], end)
    assert latest
    assert _to_date(latest[0]["trade_date"]) <= end
    print("5. Latest prices: OK")

    matrix = get_price_matrix(["RELIANCE", "TCS"], start, end)
    assert matrix is not None
    print("6. Price matrix: OK")

    # 2. Reference data.
    sample_rates = [
        RiskFreeRate(date(2026, 1, 1), Decimal("6.5"))
    ]
    assert get_risk_free_rate(date(2026, 1, 2), sample_rates).rate == Decimal("6.5")
    print("7. Risk-free rate: OK")

    # 3. Dividend yield (DB-backed).
    dy = get_dividend_yield(ticker, end)
    assert dy is None or isinstance(dy, (int, float, Decimal))
    print(f"8. Dividend yield: OK (value={dy})")

    dys = get_dividend_yields([ticker, "TCS"], end)
    assert isinstance(dys, dict)
    assert ticker in dys
    print("9. Dividend yields cross-section: OK")

    dy_hist = get_dividend_yield_history(ticker, start, end)
    assert isinstance(dy_hist, list)
    print("10. Dividend yield history: OK")

    # 4. Asset metadata.
    asset = get_asset_info(ticker)
    assert asset is not None
    assert asset["ticker"] == ticker
    print("11. Asset metadata: OK")

    # 5. Calendar.
    assert is_trading_day(date(2026, 8, 19))
    assert not is_trading_day(date(2026, 8, 22))
    assert get_next_trading_day(date(2026, 8, 22)) > date(2026, 8, 22)
    assert get_previous_trading_day(date(2026, 8, 22)) < date(2026, 8, 22)
    assert count_trading_days(date(2026, 8, 19), date(2026, 8, 19)) == 1
    print("12. Calendar utilities: OK")

    # 6. Quality.
    missing = get_missing_dates(ticker, start, end)
    assert missing == sorted(missing)
    assert has_sufficient_history(ticker, min_days=1)
    print("13. Data quality helpers: OK")

    print()
    print("Unified Quant Data Interface self-check passed")


if __name__ == "__main__":
    self_check()