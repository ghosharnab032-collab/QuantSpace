"""Portfolio optimizer application service."""

from __future__ import annotations

from datetime import date

import numpy as np
from fastapi import HTTPException

from database.connections import get_connection

from quant_tools.portfolio_optimizer_v6 import (
    backtest,
    metrics,
)


def load_monthly_returns_from_db(
    tickers: list[str],
    start: date | None = None,
    end: date | None = None,
) -> tuple[list[str], np.ndarray]:
    """
    Load canonical daily prices from price_daily and convert them
    into aligned monthly returns.

    The database is the application's canonical market-data source.
    """

    tickers = [
        ticker.strip().upper()
        for ticker in tickers
    ]

    if len(tickers) < 2:
        raise ValueError(
            "At least two tickers are required."
        )

    if len(set(tickers)) != len(tickers):
        raise ValueError(
            "Duplicate tickers are not allowed."
        )

    placeholders = ",".join(
        "?" for _ in tickers
    )

    sql = f"""
        SELECT
            ticker,
            trade_date,
            close
        FROM (
            SELECT
                ticker,
                trade_date,
                close,
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
            WHERE ticker IN ({placeholders})
    """

    params: list[object] = list(tickers)

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
        ORDER BY trade_date ASC
    """

    conn = get_connection()

    try:
        rows = conn.execute(
            sql,
            tuple(params),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise ValueError(
            "No historical market data found."
        )

    # --------------------------------------------------------
    # Build month-end prices
    # --------------------------------------------------------

    monthly_prices: dict[
        tuple[int, int],
        dict[str, float],
    ] = {}

    for row in rows:
        ticker = str(row[0]).upper()
        trade_date = str(row[1])
        close = float(row[2])

        if not np.isfinite(close) or close <= 0:
            continue

        year = int(trade_date[:4])
        month = int(trade_date[5:7])

        key = (year, month)

        if key not in monthly_prices:
            monthly_prices[key] = {}

        # Rows are ordered chronologically.
        # Therefore later observations replace earlier ones,
        # giving us the last available trading price of the month.
        monthly_prices[key][ticker] = close

    months = sorted(monthly_prices)

    if not months:
        raise ValueError(
            "No valid monthly prices were found."
        )

    # --------------------------------------------------------
    # Require every requested asset in every month.
    # --------------------------------------------------------

    complete_months = [
        month
        for month in months
        if all(
            ticker in monthly_prices[month]
            for ticker in tickers
        )
    ]

    if len(complete_months) < 25:
        raise ValueError(
            "At least 25 complete months of aligned "
            "data are required."
        )

    prices = np.asarray(
        [
            [
                monthly_prices[month][ticker]
                for ticker in tickers
            ]
            for month in complete_months
        ],
        dtype=float,
    )

    if not np.isfinite(prices).all():
        raise ValueError(
            "Monthly prices contain non-finite values."
        )

    if np.any(prices <= 0):
        raise ValueError(
            "Monthly prices must be positive."
        )

    # --------------------------------------------------------
    # Monthly returns
    # --------------------------------------------------------

    returns = (
        prices[1:] / prices[:-1]
    ) - 1.0

    if not np.isfinite(returns).all():
        raise ValueError(
            "Calculated monthly returns contain "
            "non-finite values."
        )

    return tickers, returns


def optimize_portfolio(
    *,
    tickers: list[str],
    risk_free_rate: float = 0.068,
    max_weight: float = 0.60,
    transaction_cost_bps: float = 10.0,
    lookback_months: int = 24,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """
    Run the existing rolling maximum-Sharpe optimizer
    against the canonical database market data.
    """

    if not np.isfinite(
        [
            risk_free_rate,
            max_weight,
            transaction_cost_bps,
        ]
    ).all():
        raise ValueError(
            "Optimizer parameters must be finite."
        )

    if not 0 < max_weight <= 1:
        raise ValueError(
            "max_weight must be between 0 and 1."
        )

    if transaction_cost_bps < 0:
        raise ValueError(
            "transaction_cost_bps cannot be negative."
        )

    if lookback_months < 2:
        raise ValueError(
            "lookback_months must be at least 2."
        )

    if start and end and start > end:
        raise ValueError(
            "start cannot be after end."
        )

    assets, returns = load_monthly_returns_from_db(
        tickers,
        start=start,
        end=end,
    )

    if returns.shape[0] <= lookback_months:
        raise ValueError(
            f"Need more than {lookback_months} "
            "monthly return observations."
        )

    # --------------------------------------------------------
    # Existing optimizer
    # --------------------------------------------------------

    strategy_returns, final_weights = backtest(
        returns,
        risk_free_rate=risk_free_rate,
        max_weight=max_weight,
        transaction_cost_bps=transaction_cost_bps,
        lookback_months=lookback_months,
    )

    # Equal-weight benchmark over the same backtest period.
    benchmark_returns = returns[
        lookback_months:
    ].mean(axis=1)

    optimizer_metrics = metrics(
        strategy_returns,
        risk_free_rate,
    )

    benchmark_metrics = metrics(
        benchmark_returns,
        risk_free_rate,
    )

    weights = {
        ticker: float(weight)
        for ticker, weight in zip(
            assets,
            final_weights,
        )
    }

    return {
        "assets": assets,

        "parameters": {
            "risk_free_rate": risk_free_rate,
            "max_weight": max_weight,
            "transaction_cost_bps": transaction_cost_bps,
            "lookback_months": lookback_months,
        },

        "final_weights": weights,

        "optimizer": {
            "cagr": optimizer_metrics["cagr"],
            "volatility": optimizer_metrics["volatility"],
            "sharpe": optimizer_metrics["sharpe"],
            "max_drawdown": optimizer_metrics["max_drawdown"],
        },

        "benchmark": {
            "cagr": benchmark_metrics["cagr"],
            "volatility": benchmark_metrics["volatility"],
            "sharpe": benchmark_metrics["sharpe"],
            "max_drawdown": benchmark_metrics["max_drawdown"],
        },

        "observations": {
            "monthly_returns": int(returns.shape[0]),
            "backtest_months": int(
                strategy_returns.shape[0]
            ),
        },
    }