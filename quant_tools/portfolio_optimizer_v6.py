"""Small, data-driven ETF portfolio backtester.

CSV format:
    date,NIFTYBEES,GOLDBEES,LIQUIDBEES

Each remaining column must contain a closing price.

Example:
    python portfolio_backtester_v2.py prices.csv --transaction-cost-bps 10

Use adjusted/total-return data where available; this script does not convert
price returns into total returns.

Expected returns are estimated as the annualized arithmetic mean of monthly
returns, not compounded returns.

The backtest uses trailing data, monthly rebalancing, a long-only maximum
Sharpe allocation, position limits, and turnover-based transaction costs.

Requires: numpy, scipy
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
from scipy.optimize import minimize


PERIODS_PER_YEAR = 12
MIN_MONTHS_REQUIRED = 25
TOLERANCE = 1e-8


def load_monthly_returns(path: Path) -> tuple[list[str], np.ndarray]:
    """Load a wide price CSV and return month-end percentage returns."""
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not path.is_file():
        raise ValueError(f"CSV path is not a file: {path}")

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not reader.fieldnames:
        raise ValueError("CSV has no header.")

    fields = [field.strip() if field else "" for field in reader.fieldnames]

    if "date" not in fields:
        raise ValueError(
            "CSV needs a 'date' column and at least one price column."
        )

    assets = [field for field in fields if field != "date"]
    if len(assets) < 2:
        raise ValueError("CSV needs prices for at least two assets.")

    if any(not asset for asset in assets):
        raise ValueError("Asset names cannot be empty.")
    if len(set(assets)) != len(assets):
        raise ValueError("CSV contains duplicate asset names.")

    def parse_date(row: dict[str, str]) -> date:
        raw = row.get("date", "").strip()
        try:
            return date.fromisoformat(raw)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid date: {raw!r}.") from error

    parsed_rows = [(parse_date(row), row) for row in rows]
    parsed_rows.sort(key=lambda item: item[0])

    prices_by_month: dict[tuple[int, int], np.ndarray] = {}
    seen_dates: set[date] = set()

    for current_date, row in parsed_rows:
        if current_date in seen_dates:
            raise ValueError(
                f"Duplicate date: {current_date.isoformat()}."
            )
        seen_dates.add(current_date)

        prices = []
        for asset in assets:
            raw_price = row.get(asset, "")
            try:
                price = float(raw_price)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid price for {asset} on "
                    f"{current_date.isoformat()}."
                ) from error

            if not np.isfinite(price) or price <= 0:
                raise ValueError(
                    f"Invalid price for {asset} on "
                    f"{current_date.isoformat()}: {raw_price!r}."
                )
            prices.append(price)

        # If daily data is supplied, the last observation in the month
        # becomes that month's closing price.
        prices_by_month[
            (current_date.year, current_date.month)
        ] = np.asarray(prices, dtype=float)

    if not prices_by_month:
        raise ValueError("CSV contains no data rows.")

    months = sorted(prices_by_month)

    for previous, current in zip(months, months[1:]):
        expected = (
            previous[0] + int(previous[1] == 12),
            previous[1] % 12 + 1,
        )
        if current != expected:
            raise ValueError(
                f"Missing calendar month between "
                f"{previous[0]}-{previous[1]:02d} and "
                f"{current[0]}-{current[1]:02d}."
            )

    if len(months) < MIN_MONTHS_REQUIRED:
        raise ValueError(
            f"Provide at least {MIN_MONTHS_REQUIRED} months of prices."
        )

    monthly_prices = np.asarray(
        [prices_by_month[month] for month in months],
        dtype=float,
    )

    monthly_returns = (
        monthly_prices[1:] / monthly_prices[:-1] - 1.0
    )

    if not np.isfinite(monthly_returns).all():
        raise ValueError(
            "Calculated monthly returns contain non-finite values."
        )

    return assets, monthly_returns


def max_sharpe(
    returns: np.ndarray,
    risk_free_rate: float,
    max_weight: float,
) -> np.ndarray:
    """Find a long-only maximum-Sharpe allocation."""
    returns = np.asarray(returns, dtype=float)

    if returns.ndim != 2:
        raise ValueError("returns must be a 2D array.")

    observations, n_assets = returns.shape

    if observations < 2:
        raise ValueError("returns must contain at least two observations.")
    if n_assets < 2:
        raise ValueError("returns must contain at least two assets.")
    if not np.isfinite(returns).all():
        raise ValueError("returns must contain only finite values.")
    if not np.isfinite([risk_free_rate, max_weight]).all():
        raise ValueError("Optimizer inputs must be finite.")
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1].")
    if n_assets * max_weight < 1 - TOLERANCE:
        raise ValueError(
            "max_weight is too small to form a fully invested portfolio."
        )

    annual_returns = returns.mean(axis=0) * PERIODS_PER_YEAR
    annual_covariance = np.atleast_2d(
        np.asarray(
            np.cov(returns, rowvar=False) * PERIODS_PER_YEAR,
            dtype=float,
        )
    )

    if annual_covariance.shape != (n_assets, n_assets):
        raise ValueError("Unable to construct a valid covariance matrix.")
    if not np.isfinite(annual_covariance).all():
        raise ValueError("Covariance matrix contains non-finite values.")

    def negative_sharpe(weights: np.ndarray) -> float:
        variance = float(weights @ annual_covariance @ weights)
        volatility = float(np.sqrt(max(variance, 0.0)))
        portfolio_return = float(weights @ annual_returns)

        if volatility <= TOLERANCE:
            # When volatility → 0, Sharpe → ±∞. Since we minimise,
            # return -∞ to attract the optimiser if return > rf,
            # else +∞ to repel it.
            return -1e6 if portfolio_return > risk_free_rate else 1e6

        return -(portfolio_return - risk_free_rate) / volatility

    result = minimize(
        negative_sharpe,
        x0=np.full(n_assets, 1.0 / n_assets),
        method="SLSQP",
        bounds=[(0.0, max_weight)] * n_assets,
        constraints={
            "type": "eq",
            "fun": lambda weights: float(weights.sum() - 1.0),
        },
        options={"ftol": 1e-10, "maxiter": 1000},
    )

    if not result.success:
        raise RuntimeError(f"Allocation failed: {result.message}")

    weights = np.asarray(result.x, dtype=float)

    if not np.isfinite(weights).all():
        raise RuntimeError("Optimizer returned non-finite weights.")
    if np.any(weights < -TOLERANCE):
        raise RuntimeError("Optimizer returned a negative portfolio weight.")
    if np.any(weights > max_weight + TOLERANCE):
        raise RuntimeError(
            "Optimizer exceeded the maximum weight constraint."
        )
    if not np.isclose(weights.sum(), 1.0, atol=TOLERANCE):
        raise RuntimeError(
            "Optimizer returned weights that do not sum to 1."
        )

    # Remove insignificant numerical noise from SLSQP.
    weights[np.abs(weights) < TOLERANCE] = 0.0
    weights[np.abs(weights - max_weight) < TOLERANCE] = max_weight

    # Trust SLSQP's equality constraint; if it still doesn't sum to 1,
    # the problem is numerically ill-conditioned and we should fail loudly.
    if not np.isclose(weights.sum(), 1.0, atol=TOLERANCE):
        raise RuntimeError(
            "Optimizer returned weights that do not sum to 1. "
            "The covariance matrix may be singular or nearly singular."
        )

    return weights


def metrics(
    returns: np.ndarray,
    risk_free_rate: float,
) -> dict[str, float]:
    """Calculate CAGR, volatility, maximum drawdown, and Sharpe ratio."""
    returns = np.asarray(returns, dtype=float).reshape(-1)

    if returns.size < 2:
        raise ValueError("At least two returns are required for metrics.")
    if not np.isfinite(returns).all():
        raise ValueError("Returns must contain only finite values.")
    if not np.isfinite(risk_free_rate):
        raise ValueError("risk_free_rate must be finite.")
    if np.any(returns <= -1.0):
        raise ValueError("Returns cannot be less than or equal to -100%.")

    growth = np.cumprod(1.0 + returns)
    years = returns.size / PERIODS_PER_YEAR

    cagr = float(growth[-1] ** (1.0 / years) - 1.0)
    volatility = float(
        returns.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
    )

    peak = np.maximum.accumulate(growth)
    max_drawdown = float(np.min(growth / peak - 1.0))

    if volatility > TOLERANCE:
        sharpe = float(
            (
                returns.mean() * PERIODS_PER_YEAR
                - risk_free_rate
            ) / volatility
        )
    else:
        sharpe = 0.0

    return {
        "cagr": cagr,
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
    }


def backtest(
    returns: np.ndarray,
    risk_free_rate: float = 0.068,
    max_weight: float = 0.60,
    transaction_cost_bps: float = 10,
    lookback_months: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Rebalance to a trailing-data maximum-Sharpe portfolio each month.

    Parameters are estimated using returns strictly before the month being
    traded, preventing look-ahead bias.
    """
    returns = np.asarray(returns, dtype=float)

    if returns.ndim != 2:
        raise ValueError("returns must be a 2D array.")
    if not np.isfinite(returns).all():
        raise ValueError("returns must contain only finite values.")
    if not np.isfinite(
        [risk_free_rate, max_weight, transaction_cost_bps]
    ).all():
        raise ValueError("Backtest inputs must be finite.")
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1].")
    if transaction_cost_bps < 0:
        raise ValueError(
            "transaction_cost_bps cannot be negative."
        )
    if lookback_months < 2:
        raise ValueError("lookback_months must be at least 2.")
    if returns.shape[0] <= lookback_months:
        raise ValueError(
            "Need more returns than the lookback window."
        )
    if returns.shape[1] < 2:
        raise ValueError("At least two assets are required.")

    weights = np.zeros(returns.shape[1], dtype=float)
    strategy_returns: list[float] = []
    final_weights = weights.copy()
    cost_rate = transaction_cost_bps / 10_000.0

    for month in range(lookback_months, len(returns)):
        trailing_returns = returns[
            month - lookback_months : month
        ]

        final_weights = max_sharpe(
            trailing_returns,
            risk_free_rate,
            max_weight,
        )

        turnover = float(
            np.abs(final_weights - weights).sum()
        )

        gross_return = float(
            final_weights @ returns[month]
        )
        transaction_cost = turnover * cost_rate
        net_return = gross_return - transaction_cost

        strategy_returns.append(net_return)
        weights = final_weights.copy()

    return np.asarray(strategy_returns), final_weights.copy()


def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the backtest and return a JSON-serializable report."""
    assets, returns = load_monthly_returns(args.csv)

    strategy, weights = backtest(
        returns,
        risk_free_rate=args.risk_free_rate,
        max_weight=args.max_weight,
        transaction_cost_bps=args.transaction_cost_bps,
        lookback_months=args.lookback_months,
    )

    benchmark = returns[args.lookback_months :].mean(axis=1)

    return {
        "assets": assets,
        "final_weights": dict(
            zip(assets, map(float, weights))
        ),
        "transaction_cost_bps": args.transaction_cost_bps,
        "lookback_months": args.lookback_months,
        "risk_free_rate": args.risk_free_rate,
        "initial_allocation": (
            "Starts in cash; the first allocation pays turnover cost."
        ),
        "max_sharpe_net_of_costs": metrics(
            strategy,
            args.risk_free_rate,
        ),
        "gross_equal_weight_benchmark": metrics(
            benchmark,
            args.risk_free_rate,
        ),
    }


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments."""
    values = np.asarray(
        [
            args.risk_free_rate,
            args.max_weight,
            args.transaction_cost_bps,
        ],
        dtype=float,
    )

    if not np.isfinite(values).all():
        raise ValueError("Numeric arguments must be finite.")
    if not 0 < args.max_weight <= 1:
        raise ValueError("--max-weight must be in (0, 1].")
    if args.transaction_cost_bps < 0:
        raise ValueError(
            "--transaction-cost-bps cannot be negative."
        )
    if args.lookback_months < 2:
        raise ValueError(
            "--lookback-months must be at least 2."
        )


def self_check() -> None:
    """Run lightweight internal correctness checks."""
    returns = np.array(
        [
            [0.01, 0.02],
            [0.02, 0.01],
            [-0.01, 0.00],
        ],
        dtype=float,
    )

    allocation = max_sharpe(
        returns,
        risk_free_rate=0.0,
        max_weight=0.75,
    )

    assert np.isclose(allocation.sum(), 1.0)
    assert np.all(allocation >= -TOLERANCE)
    assert np.all(allocation <= 0.75 + TOLERANCE)

    repeated_returns = np.tile(returns, (10, 1))

    strategy, final_weights = backtest(
        repeated_returns,
        risk_free_rate=0.0,
        max_weight=0.75,
        transaction_cost_bps=10,
        lookback_months=3,
    )

    assert len(strategy) == 27
    assert np.isfinite(strategy).all()
    assert np.isclose(final_weights.sum(), 1.0)

    result = metrics(strategy, risk_free_rate=0.0)

    assert set(result) == {
        "cagr",
        "volatility",
        "max_drawdown",
        "sharpe",
    }
    assert all(np.isfinite(value) for value in result.values())

    print("self-check passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "csv",
        type=Path,
        nargs="?",
        help="wide daily/monthly price CSV",
    )
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.068,
        help="annual risk-free rate as a decimal",
    )
    parser.add_argument(
        "--max-weight",
        type=float,
        default=0.60,
        help="maximum allocation to any one asset",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=10,
        help="estimated cost applied to portfolio turnover",
    )
    parser.add_argument(
        "--lookback-months",
        type=int,
        default=24,
        help="trailing months used for optimization",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="run internal correctness checks",
    )

    args = parser.parse_args()

    if args.self_check:
        self_check()
    elif args.csv:
        validate_args(args)
        print(json.dumps(run(args), indent=2))
    else:
        parser.error("provide a CSV or use --self-check")