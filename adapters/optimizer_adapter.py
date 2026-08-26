"""Thin adapter between ``data.unified_quant_data`` and the
existing portfolio optimizer.

Responsibilities:
  1. Fetch close-price data through the unified quant data layer.
  2. Convert daily prices into the monthly-return matrix expected by the
     existing optimizer.
  3. Delegate portfolio optimization/backtesting mathematics to
     ``quant_tools.portfolio_optimizer_v6``.

No portfolio optimization mathematics, covariance construction, Sharpe
calculation, transaction-cost logic, or allocation constraints live here.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import numpy as np
import pandas as pd

from data.unified_quant_data import get_price_matrix
from quant_tools.portfolio_optimizer_v6 import (
    backtest,
    metrics,
)


def load_optimizer_prices(
    tickers: list[str] | tuple[str, ...],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    """Load daily close prices through the unified quant data interface.

    Returns a DataFrame indexed by trading date with one column per ticker.
    """
    if not tickers:
        raise ValueError("At least two tickers are required.")

    normalized = [str(ticker).strip().upper() for ticker in tickers]

    if len(normalized) < 2:
        raise ValueError("At least two tickers are required.")

    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate tickers are not allowed.")

    frame = get_price_matrix(normalized, start, end)

    if frame is None:
        raise ValueError("Unified data returned no price matrix.")

    frame = pd.DataFrame(frame).copy()

    if frame.empty:
        raise ValueError(
            f"No price data available for {normalized} "
            f"between {start} and {end}."
        )

    frame.index = pd.to_datetime(frame.index, errors="raise")
    frame = frame.sort_index()
    frame.index.name = "date"

    # The unified price matrix is expected to contain one close-price
    # column per requested ticker.
    missing = [
        ticker for ticker in normalized
        if ticker not in frame.columns
    ]

    if missing:
        raise ValueError(
            f"Unified price matrix is missing ticker columns: {missing}. "
            f"Available: {list(frame.columns)}"
        )

    frame = frame[normalized]

    for ticker in normalized:
        frame[ticker] = pd.to_numeric(
            frame[ticker],
            errors="coerce",
        )

    if frame.isna().any().any():
        raise ValueError(
            "Unified price matrix contains missing or non-numeric prices."
        )

    if (frame <= 0).any().any():
        raise ValueError(
            "Unified price matrix contains non-positive prices."
        )

    return frame


def to_monthly_returns(prices: pd.DataFrame) -> np.ndarray:
    """Convert a daily close-price matrix into monthly returns.

    This is an adapter transformation only. The optimizer's allocation and
    portfolio-return mathematics remain in ``portfolio_optimizer_v6``.
    """
    frame = pd.DataFrame(prices).copy()

    if frame.empty:
        raise ValueError("prices cannot be empty.")

    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(
            frame.index,
            errors="raise",
        )

    frame = frame.sort_index()

    if frame.shape[1] < 2:
        raise ValueError("At least two assets are required.")

    if frame.isna().any().any():
        raise ValueError(
            "prices contain missing values; cannot construct monthly returns."
        )

    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError(
            "prices contain non-finite values."
        )

    if (frame <= 0).any().any():
        raise ValueError(
            "prices contain non-positive values."
        )

    # Match the optimizer's intended convention:
    # the last available observation in each calendar month is the
    # month-end closing price.
    monthly_prices = frame.resample("ME").last().dropna(how="any")

    if len(monthly_prices) < 2:
        raise ValueError(
            "At least two monthly observations are required."
        )

    monthly_returns = monthly_prices.pct_change().dropna()

    values = monthly_returns.to_numpy(dtype=float)

    if values.shape[0] < 2:
        raise ValueError(
            "At least two monthly returns are required."
        )

    if not np.isfinite(values).all():
        raise ValueError(
            "Calculated monthly returns contain non-finite values."
        )

    if np.any(values <= -1.0):
        raise ValueError(
            "Calculated monthly returns cannot be less than or equal to -100%."
        )

    return values


def run_portfolio_backtest(
    tickers: list[str] | tuple[str, ...],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    risk_free_rate: float = 0.068,
    max_weight: float = 0.60,
    transaction_cost_bps: float = 10,
    lookback_months: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the existing portfolio backtester using unified price data."""
    prices = load_optimizer_prices(tickers, start, end)
    returns = to_monthly_returns(prices)

    return backtest(
        returns,
        risk_free_rate=risk_free_rate,
        max_weight=max_weight,
        transaction_cost_bps=transaction_cost_bps,
        lookback_months=lookback_months,
    )


def _self_check() -> None:
    """Validate the adapter and its delegation path using mocked prices."""
    rng = np.random.default_rng(42)

    dates = pd.date_range(
        "2020-01-01",
        periods=36,
        freq="ME",
    )

    # Generate deterministic, positive monthly prices for three assets.
    returns = rng.normal(
        loc=[0.008, 0.010, 0.006],
        scale=[0.025, 0.030, 0.020],
        size=(36, 3),
    )

    prices = 100.0 * np.cumprod(
        1.0 + returns,
        axis=0,
    )

    mock_prices = pd.DataFrame(
        prices,
        index=dates,
        columns=["NIFTYBEES", "GOLDBEES", "LIQUIDBEES"],
    )

    assert not mock_prices.empty
    assert mock_prices.shape == (36, 3)
    assert np.isfinite(mock_prices.to_numpy()).all()
    assert (mock_prices > 0).all().all()

    # Patch the symbol imported into THIS module. This avoids the
    # python -m module-identity issue encountered in the backtester adapter.
    with patch.object(
        sys.modules[__name__],
        "get_price_matrix",
        return_value=mock_prices.copy(),
    ) as mocked_get_price_matrix:

        loaded = load_optimizer_prices(
            ["NIFTYBEES", "GOLDBEES", "LIQUIDBEES"],
            "2020-01-01",
            "2022-12-31",
        )

        mocked_get_price_matrix.assert_called_once_with(
            ["NIFTYBEES", "GOLDBEES", "LIQUIDBEES"],
            "2020-01-01",
            "2022-12-31",
        )

        assert isinstance(loaded.index, pd.DatetimeIndex)
        assert loaded.index.name == "date"
        assert list(loaded.columns) == [
            "NIFTYBEES",
            "GOLDBEES",
            "LIQUIDBEES",
        ]
        assert loaded.shape == (36, 3)

        print(
            "  load_optimizer_prices: OK "
            f"({loaded.shape[0]} rows, {loaded.shape[1]} assets)"
        )

        monthly_returns = to_monthly_returns(loaded)

        assert monthly_returns.shape == (35, 3)
        assert np.isfinite(monthly_returns).all()

        print(
            "  to_monthly_returns: OK "
            f"({monthly_returns.shape[0]} months, "
            f"{monthly_returns.shape[1]} assets)"
        )

        strategy, final_weights = backtest(
            monthly_returns,
            risk_free_rate=0.0,
            max_weight=0.75,
            transaction_cost_bps=10,
            lookback_months=24,
        )

        assert len(strategy) == 11
        assert final_weights.shape == (3,)
        assert np.isfinite(strategy).all()
        assert np.isfinite(final_weights).all()
        assert np.isclose(final_weights.sum(), 1.0)
        assert np.all(final_weights >= -1e-8)
        assert np.all(final_weights <= 0.75 + 1e-8)

        result = metrics(
            strategy,
            risk_free_rate=0.0,
        )

        assert set(result) == {
            "cagr",
            "volatility",
            "max_drawdown",
            "sharpe",
        }
        assert all(
            np.isfinite(value)
            for value in result.values()
        )

        print(
            "  portfolio backtest delegation: OK "
            f"(months={len(strategy)}, "
            f"final_weight_sum={final_weights.sum():.6f})"
        )


if __name__ == "__main__":
    print("Running optimizer adapter self-check...")
    _self_check()
    print("self-check passed")