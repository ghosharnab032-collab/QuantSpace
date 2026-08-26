from typing import Any, Literal, Optional
import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from quant_tools.black_scholes_v2 import (
    price,
    delta,
    gamma,
    vega,
    theta,
    rho,
    implied_volatility,
    put_call_parity,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    tags=["black-scholes"],
)


# ============================================================
# REQUEST SCHEMA
# ============================================================

class BlackScholesRequest(BaseModel):
    spot: float = Field(..., gt=0)
    strike: float = Field(..., gt=0)
    time_to_expiry: float = Field(..., gt=0)
    volatility: float = Field(..., gt=0)
    risk_free_rate: float = 0.0
    dividend_yield: float = Field(0.0, ge=0.0)
    option_type: Literal["call", "put"] = "call"
    market_price: Optional[float] = Field(default=None, gt=0)


# ============================================================
# JSON SERIALIZATION
# ============================================================

def json_safe(value: Any):
    """
    Convert NumPy/scientific Python scalar types into native
    Python values that FastAPI can serialize as JSON.
    """

    if value is None:
        return None

    try:
        import numpy as np

        if isinstance(value, np.bool_):
            return bool(value)

        if isinstance(value, np.integer):
            return int(value)

        if isinstance(value, np.floating):
            number = float(value)
            return number if math.isfinite(number) else None

        if isinstance(value, np.ndarray):
            return json_safe(value.tolist())

    except ImportError:
        pass

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    return value


# ============================================================
# BLACK-SCHOLES
# ============================================================

@router.post(
    "/black-scholes",
    summary="Calculate Black-Scholes option price and Greeks",
)
def calculate_black_scholes(
    request: BlackScholesRequest,
):
    S = request.spot
    K = request.strike
    T = request.time_to_expiry
    sigma = request.volatility
    r = request.risk_free_rate
    q = request.dividend_yield
    option_type = request.option_type

    try:
        # ----------------------------------------------------
        # PRICES
        # ----------------------------------------------------

        call_price = price(
            S,
            K,
            T,
            sigma,
            r,
            q,
            option_type="call",
        )

        put_price = price(
            S,
            K,
            T,
            sigma,
            r,
            q,
            option_type="put",
        )

        option_price = (
            call_price
            if option_type == "call"
            else put_price
        )

        # ----------------------------------------------------
        # GREEKS
        # ----------------------------------------------------

        option_delta = delta(
            S,
            K,
            T,
            sigma,
            r,
            q,
            option_type=option_type,
        )

        option_gamma = gamma(
            S,
            K,
            T,
            sigma,
            r,
            q,
        )

        option_vega = vega(
            S,
            K,
            T,
            sigma,
            r,
            q,
        )

        option_theta = theta(
            S,
            K,
            T,
            sigma,
            r,
            q,
            option_type=option_type,
        )

        option_rho = rho(
            S,
            K,
            T,
            sigma,
            r,
            q,
            option_type=option_type,
        )

        # ----------------------------------------------------
        # IMPLIED VOLATILITY
        # ----------------------------------------------------

        iv = None

        if request.market_price is not None:
            iv = implied_volatility(
                request.market_price,
                S,
                K,
                T,
                r,
                q,
                option_type=option_type,
            )

        # ----------------------------------------------------
        # PUT-CALL PARITY
        # ----------------------------------------------------

        parity = put_call_parity(
            S,
            K,
            T,
            r,
            q,
            C=call_price,
            P=put_price,
        )

        # Explicitly normalize parity values. This is important
        # because np.isclose() may return numpy.bool_.
        parity = {
            "forward": float(parity["forward"]),
            "parity_holds": bool(parity["parity_holds"]),
            "discrepancy": float(parity["discrepancy"]),
            "implied_call": (
                None
                if parity.get("implied_call") is None
                else float(parity["implied_call"])
            ),
            "implied_put": (
                None
                if parity.get("implied_put") is None
                else float(parity["implied_put"])
            ),
        }

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        result = {
            "inputs": {
                "spot": S,
                "strike": K,
                "time_to_expiry": T,
                "volatility": sigma,
                "risk_free_rate": r,
                "dividend_yield": q,
                "option_type": option_type,
            },

            "price": {
                "option": option_price,
                "call": call_price,
                "put": put_price,
            },

            "greeks": {
                "delta": option_delta,
                "gamma": option_gamma,
                "vega": option_vega,
                "theta": option_theta,
                "rho": option_rho,
            },

            "implied_volatility": iv,

            "put_call_parity": parity,
        }

        return json_safe(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "type": type(exc).__name__,
            },
        )