"""
Read-only historical query utilities for the quant data layer.

This module sits on top of data_access.py and trading_calendar.py.
It does not write to the database and does not introduce a new database
connection abstraction.

Core utilities:
- get_price_history
- get_available_date_range
- get_common_trading_dates
- get_missing_dates
- get_latest_available_price
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Sequence

from .data_access import (
    get_latest_price,
    get_prices,
    get_prices_bulk,
)
from .trading_calendar import TradingCalendar, get_calendar


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(
        f"Expected date, datetime, or ISO date string; got {type(value).__name__}."
    )


def get_price_history(
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[dict]:
    """Return price rows for one ticker in inclusive date order."""

    start_date = _to_date(start)
    end_date = _to_date(end)

    if start_date > end_date:
        raise ValueError("start must be <= end")

    rows = get_prices(
        ticker,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    return sorted(rows, key=lambda row: _to_date(row["trade_date"]))


def get_available_date_range(
    ticker: str,
) -> tuple[date, date] | None:
    """Return earliest and latest available price dates for a ticker."""

    rows = get_prices(ticker)

    if not rows:
        return None

    dates = [_to_date(row["trade_date"]) for row in rows]
    return min(dates), max(dates)


def get_common_trading_dates(
    tickers: Sequence[str],
    start: date | datetime | str,
    end: date | datetime | str,
) -> list[date]:
    """Return dates for which every requested ticker has price data."""

    if not tickers:
        return []

    start_date = _to_date(start)
    end_date = _to_date(end)

    if start_date > end_date:
        raise ValueError("start must be <= end")

    rows = get_prices_bulk(
        list(tickers),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    dates_by_ticker: dict[str, set[date]] = {
        ticker: set() for ticker in tickers
    }

    for row in rows:
        ticker = str(row["ticker"])
        if ticker in dates_by_ticker:
            dates_by_ticker[ticker].add(_to_date(row["trade_date"]))

    if any(not dates for dates in dates_by_ticker.values()):
        return []

    common = set.intersection(*dates_by_ticker.values())
    return sorted(common)


def get_missing_dates(
    ticker: str,
    start: date | datetime | str,
    end: date | datetime | str,
    *,
    calendar: TradingCalendar | None = None,
) -> list[date]:
    """Return expected NSE trading sessions with no price row for ticker."""

    start_date = _to_date(start)
    end_date = _to_date(end)

    if start_date > end_date:
        raise ValueError("start must be <= end")

    cal = calendar or get_calendar()

    expected = set(cal.get_trading_days(start_date, end_date))
    actual = {
        _to_date(row["trade_date"])
        for row in get_prices(
            ticker,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
    }

    return sorted(expected - actual)


def get_latest_available_price(
    ticker: str,
    as_of: date | datetime | str | None = None,
) -> dict | None:
    """Return the latest price on or before as_of.

    With no as_of date, this is the latest stored price.
    """

    if as_of is None:
        return get_latest_price(ticker)

    valuation_date = _to_date(as_of)

    rows = get_prices(
        ticker,
        end_date=valuation_date.isoformat(),
    )

    if not rows:
        return None

    return max(
        rows,
        key=lambda row: _to_date(row["trade_date"]),
    )


def self_check() -> None:
    """Smoke-test the historical query utilities against live project data."""

    ticker = "RELIANCE"

    # 1. Available date range.
    date_range = get_available_date_range(ticker)
    assert date_range is not None

    start, end = date_range
    assert start <= end
    print("1. Available date range: OK")

    # 2. Historical query.
    rows = get_price_history(ticker, start, end)
    assert rows

    dates = [_to_date(row["trade_date"]) for row in rows]
    assert dates == sorted(dates)
    print("2. Price history query + ordering: OK")

    # 3. Latest price.
    latest = get_latest_available_price(ticker)
    assert latest is not None
    assert _to_date(latest["trade_date"]) == end
    print("3. Latest available price: OK")

    # 4. As-of lookup never returns a future row.
    latest_as_of = get_latest_available_price(ticker, start)
    assert latest_as_of is not None
    assert _to_date(latest_as_of["trade_date"]) <= start
    print("4. As-of price does not look into the future: OK")

    # 5. Common dates.
    common = get_common_trading_dates(
        ["RELIANCE", "TCS"],
        start,
        end,
    )
    assert common == sorted(common)
    print("5. Common trading dates: OK")

    # 6. Missing dates use NSE trading calendar.
    missing = get_missing_dates(ticker, start, end)
    assert missing == sorted(missing)

    cal = get_calendar()
    assert all(cal.is_trading_day(day) for day in missing)
    print("6. Missing dates use NSE trading calendar: OK")

    # 7. Invalid date range.
    try:
        get_price_history(
            ticker,
            date(2026, 8, 20),
            date(2026, 8, 19),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("reversed date range should raise")

    print("7. Invalid date range rejected: OK")

    # 8. Unknown ticker.
    unknown = "__TEST_UNKNOWN_TICKER__"
    assert get_available_date_range(unknown) is None
    assert get_latest_available_price(unknown) is None
    print("8. Unknown ticker handled cleanly: OK")

    print("\nself-check passed")

if __name__ == "__main__":
    self_check()



