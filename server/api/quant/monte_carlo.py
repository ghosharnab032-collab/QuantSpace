"""Monte Carlo application service."""

from __future__ import annotations

from adapters.monte_carlo_adapter import (
    load_price_matrix,
    build_inputs,
    run_monte_carlo,
)


def run_monte_carlo_service(
    *,
    tickers: list[str],
    weights: list[float] | None,
    initial_amount: float,
    years: float,
    simulations: int,
    strategy: str,
    annual_drag: float,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Run the existing Monte Carlo engine through the adapter."""

    # Load historical prices through the Unified Quant Data Interface.
    prices = load_price_matrix(
        tickers,
        start=start,
        end=end,
    )

    # Build the actual engine inputs from historical data.
    inputs = build_inputs(
        prices,
        weights=weights,
        initial_wealth=initial_amount,
        years=years,
        n_simulations=simulations,
        strategy=strategy,
        annual_drag=annual_drag,
    )

    # Delegate simulation to the existing MonteCarloSimulator.
    result = run_monte_carlo(
        inputs,
        n_sims=simulations,
        n_days=round(years * 252),
        initial_capital=initial_amount,
    )

    resolved_weights = (
        inputs.weights.tolist()
        if inputs.weights is not None
        else [1.0 / len(tickers)] * len(tickers)
    )

    return {
        "tickers": tickers,
        "weights": resolved_weights,
        "initial_amount": initial_amount,
        "years": years,
        "simulations": simulations,
        "strategy": strategy,
        "annual_drag": annual_drag,
        "mean_final_wealth": result.mean_final_wealth,
        "median_final_wealth": result.median_final_wealth,
        "percentile_5": result.percentile_5,
        "percentile_95": result.percentile_95,
        "probability_of_loss": result.probability_of_loss,
        "cvar_95_loss": result.cvar_95_loss,
        "median_max_drawdown": result.median_max_drawdown,
        "percentile_95_max_drawdown": result.percentile_95_max_drawdown,
    }