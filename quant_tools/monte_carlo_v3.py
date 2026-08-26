"""Focused Monte Carlo simulator for long-only portfolios.

Uses correlated geometric Brownian-motion paths to compare periodic
rebalancing with buy-and-hold. The fixed annual drag is a simple model of
portfolio-level costs and taxes; it is not a transaction or tax-lot engine.

Requires: numpy
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np


Strategy = Literal["rebalance", "buy_and_hold"]


@dataclass(frozen=True)
class MonteCarloInputs:
    initial_wealth: float
    expected_returns: np.ndarray
    volatilities: np.ndarray
    correlation_matrix: np.ndarray
    years: float
    steps_per_year: int
    n_simulations: int
    weights: Optional[np.ndarray] = None
    strategy: Strategy = "rebalance"
    annual_drag: float = 0.0
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        numbers = [self.initial_wealth, self.years, self.annual_drag]
        if not np.isfinite(numbers).all() or self.initial_wealth <= 0 or self.years <= 0:
            raise ValueError("initial_wealth and years must be finite and positive.")
        if self.steps_per_year <= 0 or self.n_simulations <= 0:
            raise ValueError("steps_per_year and n_simulations must be positive.")
        if not 0 <= self.annual_drag < 1:
            raise ValueError("annual_drag must be in [0, 1).")
        if self.strategy not in {"rebalance", "buy_and_hold"}:
            raise ValueError("strategy must be 'rebalance' or 'buy_and_hold'.")

        n_assets = len(self.expected_returns)
        if n_assets < 1 or self.expected_returns.shape != (n_assets,) or self.volatilities.shape != (n_assets,):
            raise ValueError("expected_returns and volatilities must be non-empty 1D arrays of equal length.")
        if not np.isfinite(self.expected_returns).all() or not np.isfinite(self.volatilities).all():
            raise ValueError("returns and volatilities must be finite.")
        if np.any(self.volatilities < 0):
            raise ValueError("volatilities cannot be negative.")
        if self.correlation_matrix.shape != (n_assets, n_assets):
            raise ValueError("correlation_matrix has the wrong shape.")
        if not np.isfinite(self.correlation_matrix).all() or not np.allclose(self.correlation_matrix, self.correlation_matrix.T):
            raise ValueError("correlation_matrix must be finite and symmetric.")
        if not np.allclose(np.diag(self.correlation_matrix), 1, atol=1e-6) or np.any(np.abs(self.correlation_matrix) > 1):
            raise ValueError("correlation_matrix must have a unit diagonal and values in [-1, 1].")
        if np.linalg.eigvalsh(self.correlation_matrix).min() < -1e-10:
            raise ValueError("correlation_matrix must be positive semidefinite.")
        if self.weights is not None:
            if self.weights.shape != (n_assets,) or not np.isfinite(self.weights).all():
                raise ValueError("weights must be a finite 1D array matching the assets.")
            if np.any(self.weights < 0) or not np.isclose(self.weights.sum(), 1):
                raise ValueError("weights must be non-negative and sum to 1.")


@dataclass(frozen=True)
class MonteCarloResult:
    final_wealth: np.ndarray
    wealth_paths: np.ndarray
    mean_final_wealth: float
    median_final_wealth: float
    percentile_5: float
    percentile_95: float
    probability_of_loss: float
    cvar_95_loss: float
    median_max_drawdown: float
    percentile_95_max_drawdown: float

    def to_dict(self) -> dict[str, float]:
        return {
            name: round(getattr(self, name), 4)
            for name in (
                "mean_final_wealth", "median_final_wealth", "percentile_5", "percentile_95",
                "probability_of_loss", "cvar_95_loss", "median_max_drawdown", "percentile_95_max_drawdown",
            )
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class MonteCarloSimulator:
    def __init__(self, inputs: MonteCarloInputs):
        self.inputs = inputs
        self.n_assets = len(inputs.expected_returns)
        self.n_steps = round(inputs.years * inputs.steps_per_year)
        if not np.isclose(self.n_steps / inputs.steps_per_year, inputs.years):
            raise ValueError("years * steps_per_year must be a whole number of steps.")
        self.weights = inputs.weights if inputs.weights is not None else np.full(self.n_assets, 1 / self.n_assets)
        corr = inputs.correlation_matrix.copy()
        min_eig = np.linalg.eigvalsh(corr).min()
        if min_eig < 1e-12:
            # Jitter diagonal to enforce strict positive definiteness for Cholesky
            corr = corr + np.eye(self.n_assets) * (1e-12 - min_eig)
        self.cholesky = np.linalg.cholesky(corr)

    def _growth(self, rng: np.random.Generator) -> np.ndarray:
        dt = 1 / self.inputs.steps_per_year
        shocks = rng.standard_normal((self.inputs.n_simulations, self.n_assets)) @ self.cholesky.T
        return np.exp(
            (self.inputs.expected_returns - 0.5 * self.inputs.volatilities**2) * dt
            + self.inputs.volatilities * np.sqrt(dt) * shocks
        )

    def simulate(self) -> MonteCarloResult:
        rng = np.random.default_rng(self.inputs.seed)
        paths = np.empty((self.inputs.n_simulations, self.n_steps + 1))
        paths[:, 0] = self.inputs.initial_wealth
        drag = (1 - self.inputs.annual_drag) ** (1 / self.inputs.steps_per_year)

        if self.inputs.strategy == "rebalance":
            for step in range(1, self.n_steps + 1):
                paths[:, step] = paths[:, step - 1] * (self._growth(rng) @ self.weights) * drag
        else:
            values = np.broadcast_to(self.inputs.initial_wealth * self.weights, (self.inputs.n_simulations, self.n_assets)).copy()
            for step in range(1, self.n_steps + 1):
                values *= self._growth(rng) * drag
                paths[:, step] = values.sum(axis=1)

        final_wealth = paths[:, -1]
        losses = self.inputs.initial_wealth - final_wealth
        sorted_losses = np.sort(losses)
        tail_start = int(0.95 * len(sorted_losses))
        cvar_95 = float(sorted_losses[tail_start:].mean())
        drawdowns = 1 - paths / np.maximum.accumulate(paths, axis=1)
        max_drawdowns = drawdowns.max(axis=1)
        return MonteCarloResult(
            final_wealth=final_wealth,
            wealth_paths=paths,
            mean_final_wealth=float(final_wealth.mean()),
            median_final_wealth=float(np.median(final_wealth)),
            percentile_5=float(np.percentile(final_wealth, 5)),
            percentile_95=float(np.percentile(final_wealth, 95)),
            probability_of_loss=float(np.mean(final_wealth < self.inputs.initial_wealth)),
            cvar_95_loss=cvar_95,
            median_max_drawdown=float(np.median(max_drawdowns)),
            percentile_95_max_drawdown=float(np.percentile(max_drawdowns, 95)),
        )


def self_check() -> None:
    # Check 1: deterministic zero-vol rebalance
    inputs1 = MonteCarloInputs(
        initial_wealth=100,
        expected_returns=np.array([0.10]),
        volatilities=np.array([0.0]),
        correlation_matrix=np.array([[1.0]]),
        years=1,
        steps_per_year=12,
        n_simulations=3,
        seed=42,
    )
    result1 = MonteCarloSimulator(inputs1).simulate()
    assert np.allclose(result1.final_wealth, 100 * np.exp(0.10)), "zero-vol rebalance failed"

    # Check 2: buy-and-hold with drag and correlation
    inputs2 = MonteCarloInputs(
        initial_wealth=100_000,
        expected_returns=np.array([0.08, 0.06]),
        volatilities=np.array([0.20, 0.15]),
        correlation_matrix=np.array([[1.0, 0.5], [0.5, 1.0]]),
        years=1,
        steps_per_year=12,
        n_simulations=100,
        weights=np.array([0.6, 0.4]),
        strategy="buy_and_hold",
        annual_drag=0.01,
        seed=42,
    )
    result2 = MonteCarloSimulator(inputs2).simulate()
    assert result2.mean_final_wealth > 0, "B&H mean wealth non-positive"
    assert 0 <= result2.probability_of_loss <= 1, "probability_of_loss out of range"
    assert result2.cvar_95_loss >= 0, "CVaR negative"
    assert result2.median_max_drawdown >= 0, "drawdown negative"

    # Check 3: near-perfect correlation (Cholesky jitter path)
    inputs3 = MonteCarloInputs(
        initial_wealth=100,
        expected_returns=np.array([0.10, 0.10]),
        volatilities=np.array([0.20, 0.20]),
        correlation_matrix=np.array([[1.0, 0.999999], [0.999999, 1.0]]),
        years=1,
        steps_per_year=12,
        n_simulations=10,
        seed=42,
    )
    result3 = MonteCarloSimulator(inputs3).simulate()
    assert np.isfinite(result3.mean_final_wealth), "near-perfect correlation crashed"

    # Check 4: to_dict / to_json round-trip
    d = result1.to_dict()
    j = result1.to_json()
    assert isinstance(d, dict) and "mean_final_wealth" in d
    assert isinstance(j, str) and "mean_final_wealth" in j


if __name__ == "__main__":
    self_check()
    print("self-check passed")