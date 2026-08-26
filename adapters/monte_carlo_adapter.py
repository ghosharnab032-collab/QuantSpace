"""Adapter between the Monte Carlo engine and quant data layer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.unified_quant_data import get_prices
from quant_tools.monte_carlo_v3 import (
    MonteCarloInputs,
    MonteCarloSimulator,
)


def load_price_matrix(
    tickers: list[str],
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Load historical closing prices for multiple tickers."""

    if not tickers:
        raise ValueError(
            "At least one ticker is required."
        )

    normalized_tickers = [
        str(ticker).strip().upper()
        for ticker in tickers
    ]

    if any(not ticker for ticker in normalized_tickers):
        raise ValueError(
            "Ticker symbols cannot be empty."
        )

    # Remove duplicate tickers while preserving order.
    normalized_tickers = list(
        dict.fromkeys(normalized_tickers)
    )

    price_series: dict[str, pd.Series] = {}

    for ticker in normalized_tickers:

        # Unified Quant Data Interface:
        #
        # get_prices(
        #     ticker,
        #     start=None,
        #     end=None,
        # )
        #
        # returns:
        #
        # [
        #     {
        #         "ticker": "...",
        #         "trade_date": "...",
        #         "open": ...,
        #         "high": ...,
        #         "low": ...,
        #         "close": ...,
        #         "volume": ...,
        #     },
        #     ...
        # ]

        rows = get_prices(
            ticker,
            start=start,
            end=end,
        )

        if not rows:
            raise ValueError(
                f"No price data found for {ticker}."
            )

        # Convert canonical rows into a DataFrame.
        frame = pd.DataFrame(rows)

        required_columns = {
            "trade_date",
            "close",
        }

        missing_columns = (
            required_columns
            - set(frame.columns)
        )

        if missing_columns:
            raise ValueError(
                f"Price data for {ticker} is missing "
                f"required columns: "
                f"{sorted(missing_columns)}"
            )

        # Normalize dates.
        frame["trade_date"] = pd.to_datetime(
            frame["trade_date"],
            errors="coerce",
        )

        # Normalize prices.
        frame["close"] = pd.to_numeric(
            frame["close"],
            errors="coerce",
        )

        frame = (
            frame
            .dropna(
                subset=[
                    "trade_date",
                    "close",
                ]
            )
            .sort_values("trade_date")
        )

        if frame.empty:
            raise ValueError(
                f"No valid closing prices found for {ticker}."
            )

        # Remove duplicate dates.
        frame = (
            frame
            .drop_duplicates(
                subset=["trade_date"],
                keep="first",
            )
        )

        series = (
            frame
            .set_index("trade_date")["close"]
            .astype(float)
        )

        series.name = ticker

        price_series[ticker] = series

    # Combine all tickers on common trading dates.
    prices = pd.concat(
        price_series.values(),
        axis=1,
        join="inner",
    )

    prices = (
        prices
        .sort_index()
        .dropna()
    )

    if prices.empty:
        raise ValueError(
            "No overlapping historical price data "
            "available for the requested tickers."
        )

    return prices


def _calculate_inputs(
    prices: pd.DataFrame,
    *,
    weights: list[float] | None,
    initial_wealth: float,
    years: float,
    n_simulations: int,
    strategy: str,
    annual_drag: float,
) -> MonteCarloInputs:
    """Convert historical prices into Monte Carlo parameters."""

    if len(prices) < 2:
        raise ValueError(
            "At least two historical price observations "
            "are required."
        )

    returns = (
        prices
        .pct_change()
        .dropna()
    )

    if returns.empty:
        raise ValueError(
            "Unable to calculate historical returns."
        )

    expected_returns = (
        returns.mean() * 252
    ).to_numpy(dtype=float)

    volatilities = (
        returns.std(ddof=1) * np.sqrt(252)
    ).to_numpy(dtype=float)

    correlation_matrix = (
        returns
        .corr()
        .to_numpy(dtype=float)
    )

    # Protect against NaN correlations caused by
    # constant or nearly constant price series.
    correlation_matrix = np.nan_to_num(
        correlation_matrix,
        nan=0.0,
    )

    np.fill_diagonal(
        correlation_matrix,
        1.0,
    )

    resolved_weights = None

    if weights is not None:

        resolved_weights = np.asarray(
            weights,
            dtype=float,
        )

        if len(resolved_weights) != len(
            prices.columns
        ):
            raise ValueError(
                "weights length must match "
                "the number of tickers."
            )

        if np.any(resolved_weights < 0):
            raise ValueError(
                "weights must be non-negative."
            )

        if not np.isclose(
            resolved_weights.sum(),
            1.0,
            atol=1e-6,
        ):
            raise ValueError(
                "weights must sum to 1."
            )

    return MonteCarloInputs(
        initial_wealth=initial_wealth,
        expected_returns=expected_returns,
        volatilities=volatilities,
        correlation_matrix=correlation_matrix,
        years=years,
        steps_per_year=252,
        n_simulations=n_simulations,
        weights=resolved_weights,
        strategy=strategy,
        annual_drag=annual_drag,
    )


def build_inputs(
    prices: pd.DataFrame,
    *,
    weights: list[float] | None,
    initial_wealth: float,
    years: float,
    n_simulations: int,
    strategy: str,
    annual_drag: float,
) -> MonteCarloInputs:
    """Build inputs for the Monte Carlo engine."""

    if prices.empty:
        raise ValueError(
            "Price matrix cannot be empty."
        )

    return _calculate_inputs(
        prices,
        weights=weights,
        initial_wealth=initial_wealth,
        years=years,
        n_simulations=n_simulations,
        strategy=strategy,
        annual_drag=annual_drag,
    )


def run_monte_carlo(
    inputs: MonteCarloInputs,
    *,
    n_sims: int,
    n_days: int,
    initial_capital: float,
):
    """Run the Monte Carlo simulator."""

    simulator = MonteCarloSimulator(inputs)

    return simulator.simulate()