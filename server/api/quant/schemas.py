"""Quant API request and response schemas."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MonteCarloRequest(BaseModel):
    """Monte Carlo portfolio simulation request."""

    tickers: list[str] = Field(
        min_length=1,
        max_length=20,
        description="Portfolio instrument identifiers.",
    )

    weights: list[float] | None = Field(
        default=None,
        description="Portfolio weights. Equal-weighted when omitted.",
    )

    initial_amount: float = Field(
        gt=0,
        description="Initial portfolio value.",
    )

    years: float = Field(
        gt=0,
        le=100,
        description="Simulation horizon in years.",
    )

    simulations: int = Field(
        gt=0,
        le=100_000,
        description="Number of Monte Carlo simulations.",
    )

    strategy: Literal[
        "rebalance",
        "buy_and_hold",
    ] = Field(
        default="rebalance",
        description="Portfolio strategy.",
    )

    annual_drag: float = Field(
        default=0.0,
        ge=0,
        lt=1,
        description="Annual portfolio cost drag.",
    )

    start: str | None = Field(
        default=None,
        description="Historical data start date.",
    )

    end: str | None = Field(
        default=None,
        description="Historical data end date.",
    )

    @model_validator(mode="after")
    def validate_weights(self):
        """Validate portfolio weights."""

        if self.weights is None:
            return self

        if len(self.weights) != len(self.tickers):
            raise ValueError(
                "weights length must match tickers length."
            )

        if any(weight < 0 for weight in self.weights):
            raise ValueError(
                "weights must be non-negative."
            )

        if not self.weights:
            raise ValueError(
                "weights cannot be empty."
            )

        if abs(sum(self.weights) - 1.0) > 1e-6:
            raise ValueError(
                "weights must sum to 1."
            )

        return self


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation response."""

    tickers: list[str]
    weights: list[float]

    initial_amount: float
    years: float
    simulations: int

    strategy: str
    annual_drag: float

    mean_final_wealth: float
    median_final_wealth: float
    percentile_5: float
    percentile_95: float

    probability_of_loss: float
    cvar_95_loss: float

    median_max_drawdown: float
    percentile_95_max_drawdown: float