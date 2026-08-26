"""Quantitative finance API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import require_entitlement

from .monte_carlo import run_monte_carlo_service
from .optimizer import optimize_portfolio
from .schemas import (
    MonteCarloRequest,
    MonteCarloResponse,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/quant",
    tags=["quant"],
)


# ============================================================
# MONTE CARLO
# ============================================================

@router.post(
    "/monte-carlo",
    response_model=MonteCarloResponse,
)
async def monte_carlo(
    request: MonteCarloRequest,
    _: dict = Depends(
        require_entitlement("monte_carlo")
    ),
):
    """
    Run a portfolio Monte Carlo simulation.

    Requires an active Monte Carlo entitlement.
    """

    try:
        # ----------------------------------------------------
        # Normalize tickers
        # ----------------------------------------------------

        tickers = [
            ticker.strip().upper()
            for ticker in request.tickers
            if ticker and ticker.strip()
        ]

        if not tickers:
            raise ValueError(
                "At least one valid ticker is required."
            )

        if len(set(tickers)) != len(tickers):
            raise ValueError(
                "Duplicate tickers are not allowed."
            )

        # ----------------------------------------------------
        # Run Monte Carlo service
        # ----------------------------------------------------

        result = run_monte_carlo_service(
            tickers=tickers,
            weights=request.weights,
            initial_amount=request.initial_amount,
            years=request.years,
            simulations=request.simulations,
            strategy=request.strategy,
            annual_drag=request.annual_drag,
            start=request.start,
            end=request.end,
        )

        return result

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Monte Carlo failed: {exc}",
        ) from exc


# ============================================================
# PORTFOLIO OPTIMIZER
# ============================================================

class OptimizerRequest(BaseModel):
    """Portfolio optimizer request."""

    tickers: list[str] = Field(
        min_length=2,
        max_length=20,
    )

    start: date | None = None

    end: date | None = None

    risk_free_rate: float = Field(
        default=0.068,
        ge=0,
    )

    max_weight: float = Field(
        default=0.60,
        gt=0,
        le=1,
    )

    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0,
    )

    lookback_months: int = Field(
        default=24,
        ge=2,
    )


@router.post(
    "/optimizer",
)
async def portfolio_optimizer(
    request: OptimizerRequest,
):
    """
    Run the rolling maximum-Sharpe
    portfolio optimizer.
    """

    try:
        # ----------------------------------------------------
        # Normalize tickers
        # ----------------------------------------------------

        tickers = [
            ticker.strip().upper()
            for ticker in request.tickers
            if ticker and ticker.strip()
        ]

        if len(tickers) < 2:
            raise ValueError(
                "At least two valid tickers are required."
            )

        if len(set(tickers)) != len(tickers):
            raise ValueError(
                "Duplicate tickers are not allowed."
            )

        # ----------------------------------------------------
        # Validate dates
        # ----------------------------------------------------

        if (
            request.start is not None
            and request.end is not None
            and request.start > request.end
        ):
            raise ValueError(
                "start cannot be after end."
            )

        # ----------------------------------------------------
        # Run optimizer
        # ----------------------------------------------------

        result = optimize_portfolio(
            tickers=tickers,
            risk_free_rate=request.risk_free_rate,
            max_weight=request.max_weight,
            transaction_cost_bps=(
                request.transaction_cost_bps
            ),
            lookback_months=request.lookback_months,
            start=request.start,
            end=request.end,
        )

        return result

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Portfolio optimizer failed: {exc}"
            ),
        ) from exc


# ============================================================
# OPTIMIZER HEALTH
# ============================================================

@router.get(
    "/optimizer/health",
)
async def optimizer_health():
    """Return optimizer API health."""

    return {
        "status": "ok",
        "service": "portfolio_optimizer",
    }