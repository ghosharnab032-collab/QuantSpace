"""Thin adapter between `data.unified_quant_data` and `quant_tools.india_backtester_v2`.

Responsibilities:
  1. Fetch price data via the unified data layer.
  2. Normalise column names and set a DatetimeIndex.
  3. Delegate signal generation and backtest execution to the existing v2 backtester.

No backtesting mathematics, transaction-cost logic, signal logic, or execution
logic lives here.
"""

from __future__ import annotations

import pandas as pd

from data.unified_quant_data import get_prices
from quant_tools.india_backtester import (
    IndiaBacktester,
    IndiaEquityDeliveryCost,
    moving_average_signal,
    BacktestResult,
)


def load_backtester_data(
    ticker: str,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Load daily OHLCV data from the unified quant layer for the backtester.

    The returned DataFrame preserves *all* OHLCV columns so the unified market-
    data representation is not unnecessarily narrowed, even though the current
    backtester only requires ``open`` and ``close`` at execution time.

    Parameters
    ----------
    ticker:
        Instrument identifier recognised by ``unified_quant_data``.
    start, end:
        Optional inclusive date bounds.  Strings are parsed by pandas.

    Returns
    -------
    pd.DataFrame
        DatetimeIndex named ``date``, columns in order:
        ``open``, ``high``, ``low``, ``close``, ``volume``.
    """
    # 1. Fetch raw data from the unified data layer
    raw = get_prices(ticker, start=start, end=end)

    # 2. Normalise to a DataFrame
    frame = pd.DataFrame(raw)

    # 3. Normalise column names → lower-case, stripped, snake_case
    frame = frame.rename(
        columns={
            col: str(col).strip().lower().replace(" ", "_")
            for col in frame.columns
        }
    )

    # 4. Ensure a DatetimeIndex named "date"
    #    unified_quant_data uses "trade_date"; fall back to "date" or existing index.
    if "trade_date" in frame.columns:
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="raise")
        frame = frame.set_index("trade_date").sort_index()
    elif "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        frame = frame.set_index("date").sort_index()
    elif not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index, errors="raise")
        frame = frame.sort_index()
    frame.index.name = "date"

    # 5. Ensure required OHLCV columns exist; coerce numeric
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in frame.columns:
            raise ValueError(
                f"Unified data for {ticker!r} is missing required column {col!r}. "
                f"Available: {sorted(frame.columns)}"
            )
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    if frame[required].isna().any().any():
        raise ValueError(
            f"Unified data for {ticker!r} contains non-numeric or missing OHLCV values."
        )

    # 6. Return only the canonical columns in a stable order
    return frame[required]


def run_moving_average_backtest(
    data: pd.DataFrame,
    *,
    fast: int = 20,
    slow: int = 50,
    initial_capital: float = 100_000,
    risk_free_rate: float = 0.068,
    costs: IndiaEquityDeliveryCost | None = None,
) -> BacktestResult:
    """Run a moving-average crossover backtest by delegating to the v2 engine.

    Parameters
    ----------
    data:
        DataFrame with ``open``, ``high``, ``low``, ``close`` (and optionally
        ``volume``).  Must have a DatetimeIndex.
    fast, slow:
        Look-back windows for the moving-average signal.  Passed through to
        ``moving_average_signal``.
    initial_capital:
        Starting portfolio value.
    risk_free_rate:
        Annualised risk-free rate for Sharpe calculation.
    costs:
        Optional ``IndiaEquityDeliveryCost`` instance.  Defaults to the standard
        delivery-equity cost schedule when ``None``.

    Returns
    -------
    BacktestResult
        Result object produced by ``IndiaBacktester.run``.
    """
    # 1. Signal generation — delegated entirely to the existing v2 function
    signal = moving_average_signal(data["close"], fast=fast, slow=slow)

    # 2. Backtest execution — delegated entirely to the existing v2 class
    backtester = IndiaBacktester(
        data=data,
        initial_capital=initial_capital,
        risk_free_rate=risk_free_rate,
        costs=costs,
    )
    return backtester.run(signal)


def _self_check() -> None:
    """Validate the adapter end-to-end using mocked unified data."""
    from unittest.mock import patch
    import sys
    import numpy as np

    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    rng = np.random.default_rng(42)

    base = 100 + rng.normal(0, 0.5, 60).cumsum()
    open_p = base + rng.normal(0, 0.3, 60)
    close_p = base + rng.normal(0, 0.3, 60)
    high_p = np.maximum(open_p, close_p) + rng.random(60) * 1.5
    low_p = np.minimum(open_p, close_p) - rng.random(60) * 1.5

    mock_df = pd.DataFrame(
        {
            "trade_date": dates,
            "open": open_p.round(2),
            "high": high_p.round(2),
            "low": low_p.round(2),
            "close": close_p.round(2),
            "volume": rng.integers(
                1_000_000,
                10_000_000,
                size=60,
            ),
        }
    )

    # Verify the test fixture itself.
    assert not mock_df.empty
    assert len(mock_df) == 60
    assert list(mock_df.columns) == [
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    # When running `python -m adapters.backtester_adapter`, the module is loaded
    # both as `__main__` and as `adapters.backtester_adapter`.  We must patch
    # the *running* module object (`sys.modules[__name__]`) so that the
    # `get_prices` imported at module top-level is actually replaced.
    with patch.object(
        sys.modules[__name__],
        "get_prices",
        return_value=mock_df.copy(),
    ) as mocked_get_prices:

        data = load_backtester_data(
            "RELIANCE",
            start="2025-01-01",
            end="2025-03-31",
        )

        mocked_get_prices.assert_called_once_with(
            "RELIANCE",
            start="2025-01-01",
            end="2025-03-31",
        )

        assert isinstance(data.index, pd.DatetimeIndex)
        assert data.index.name == "date"

        assert list(data.columns) == [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        assert len(data) == 60

        print(
            f"  load_backtester_data: OK "
            f"({len(data)} rows, columns: {list(data.columns)})"
        )

        result = run_moving_average_backtest(
            data,
            fast=10,
            slow=20,
        )

        assert isinstance(result, BacktestResult)
        assert result.gross_equity is not None
        assert result.net_equity is not None

        print(
            f"  run_moving_average_backtest: OK "
            f"(trades={result.trades}, "
            f"return={result.total_return:.2%}, "
            f"sharpe={result.sharpe:.2f})"
        )


if __name__ == "__main__":
    print("Running adapter self-check...")
    _self_check()
    print("self-check passed")