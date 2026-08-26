"""Thin adapter between the Unified Quant Data Interface and Black-Scholes.

Responsibilities:
  1. Obtain spot, risk-free rate, and dividend yield through the unified
     quant data layer when requested.
  2. Normalize those inputs into the scalar values expected by the existing
     Black-Scholes engine.
  3. Delegate pricing, Greeks, implied volatility, and parity calculations
     to the existing ``quant_tools.black_scholes`` module.

No Black-Scholes mathematics lives here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from data.unified_quant_data import (
    get_dividend_yield,
    get_latest_prices,
    get_risk_free_rate,
)
from data.dividend_yield import DividendYield
from data.risk_free_rate import RiskFreeRate
from quant_tools.black_scholes_v2 import (
    OptionType,
    delta,
    gamma,
    implied_volatility,
    price,
    put_call_parity,
    rho,
    theta,
    vega,
)


def _to_float(value: object, field_name: str) -> float:
    """Convert a numeric reference-data value to a finite float."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} cannot be a boolean.")

    if isinstance(value, Decimal):
        result = float(value)
    else:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"{field_name} must be numeric, got {type(value).__name__}."
            ) from exc

    if not result == result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{field_name} must be finite, got {result}.")

    return result


def get_black_scholes_inputs(
    ticker: str,
    valuation_date: date | datetime | str,
    rates: Sequence[RiskFreeRate],
    yields: Sequence[DividendYield],
) -> dict[str, float]:
    """Resolve spot, risk-free rate, and dividend yield for a valuation date.

    Spot is the latest available unified price at or before the valuation
    date. Risk-free rate and dividend yield use their respective unified
    reference-data lookup conventions.
    """
    latest = get_latest_prices(
        [ticker],
        as_of_date=valuation_date,
    )

    if not latest:
        raise ValueError(
            f"No price available for {ticker!r} on or before "
            f"{valuation_date}."
        )

    row = latest[0]

    if "close" not in row:
        raise ValueError(
            f"Unified price row for {ticker!r} is missing 'close'. "
            f"Available: {sorted(row)}"
        )

    spot = _to_float(row["close"], "spot")

    risk_free = get_risk_free_rate(
        valuation_date,
        rates,
    )
    dividend = get_dividend_yield(
        ticker,
        valuation_date,
        yields,
    )

    # A missing dividend-yield reference is represented by None by the
    # unified interface. Black-Scholes accepts q=0.0 as its explicit
    # no-dividend convention.
    dividend_value = (
        0.0
        if dividend is None
        else _to_float(
            getattr(dividend, "yield_value", getattr(dividend, "yield_rate", dividend)),
            "dividend_yield",
        )
    )

    return {
        "S": spot,
        "r": _to_float(
            getattr(risk_free, "rate"),
            "risk_free_rate",
        ),
        "q": dividend_value,
    }


def price_option(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    *,
    q: float = 0.0,
    option_type: OptionType = "call",
) -> float:
    """Delegate European option pricing to the existing Black-Scholes engine."""
    return price(
        S,
        K,
        T,
        sigma,
        r,
        q,
        option_type=option_type,
    )


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    *,
    q: float = 0.0,
    option_type: OptionType = "call",
) -> dict[str, float]:
    """Return all supported Black-Scholes Greeks."""
    return {
        "delta": delta(
            S, K, T, sigma, r, q, option_type=option_type
        ),
        "gamma": gamma(
            S, K, T, sigma, r, q
        ),
        "vega": vega(
            S, K, T, sigma, r, q
        ),
        "theta": theta(
            S, K, T, sigma, r, q, option_type=option_type
        ),
        "rho": rho(
            S, K, T, sigma, r, q, option_type=option_type
        ),
    }


def calculate_implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    *,
    q: float = 0.0,
    option_type: OptionType = "call",
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float:
    """Delegate implied-volatility solving to the existing engine."""
    return implied_volatility(
        market_price,
        S,
        K,
        T,
        r,
        q,
        option_type=option_type,
        tol=tol,
        max_iter=max_iter,
    )


def verify_put_call_parity(
    S: float,
    K: float,
    T: float,
    r: float,
    *,
    q: float = 0.0,
    C: float | None = None,
    P: float | None = None,
) -> dict:
    """Delegate European put-call parity to the existing engine."""
    return put_call_parity(
        S,
        K,
        T,
        r,
        q,
        C=C,
        P=P,
    )


def price_option_from_unified_data(
    ticker: str,
    valuation_date: date | datetime | str,
    K: float,
    T: float,
    sigma: float,
    rates: Sequence[RiskFreeRate],
    yields: Sequence[DividendYield],
    *,
    option_type: OptionType = "call",
) -> float:
    """Price an option using spot/reference data from the unified interface."""
    inputs = get_black_scholes_inputs(
        ticker,
        valuation_date,
        rates,
        yields,
    )

    return price_option(
        inputs["S"],
        K,
        T,
        sigma,
        inputs["r"],
        q=inputs["q"],
        option_type=option_type,
    )


def _self_check() -> None:
    """Test adapter integration without changing Black-Scholes mathematics."""
    from unittest.mock import patch
    import sys

    valuation_date = "2025-01-15"

    class MockRiskFree:
        rate = Decimal("0.05")

    class MockDividend:
        yield_value = Decimal("0.02")

    mock_latest = [
        {
            "ticker": "RELIANCE",
            "trade_date": "2025-01-15",
            "close": 100.0,
        }
    ]

    # When running `python -m adapters.black_scholes_adapter`, the module is
    # loaded both as `__main__` and as `adapters.black_scholes_adapter`.  We
    # must patch the *running* module object so the imports at module top-level
    # are actually replaced.
    with (
        patch.object(
            sys.modules[__name__],
            "get_latest_prices",
            return_value=mock_latest,
        ),
        patch.object(
            sys.modules[__name__],
            "get_risk_free_rate",
            return_value=MockRiskFree(),
        ),
        patch.object(
            sys.modules[__name__],
            "get_dividend_yield",
            return_value=MockDividend(),
        ),
    ):
        inputs = get_black_scholes_inputs(
            "RELIANCE",
            valuation_date,
            [],
            [],
        )

        assert inputs == {
            "S": 100.0,
            "r": 0.05,
            "q": 0.02,
        }

        call_price = price_option(
            inputs["S"],
            100.0,
            1.0,
            0.20,
            inputs["r"],
            q=inputs["q"],
            option_type="call",
        )

        assert call_price > 0.0

        greeks = calculate_greeks(
            inputs["S"],
            100.0,
            1.0,
            0.20,
            inputs["r"],
            q=inputs["q"],
        )

        assert set(greeks) == {
            "delta",
            "gamma",
            "vega",
            "theta",
            "rho",
        }

        assert all(
            isinstance(value, float)
            for value in greeks.values()
        )

        iv = calculate_implied_volatility(
            call_price,
            inputs["S"],
            100.0,
            1.0,
            inputs["r"],
            q=inputs["q"],
        )

        assert abs(iv - 0.20) < 1e-6

        put_price = price_option(
            inputs["S"],
            100.0,
            1.0,
            0.20,
            inputs["r"],
            q=inputs["q"],
            option_type="put",
        )

        parity = verify_put_call_parity(
            inputs["S"],
            100.0,
            1.0,
            inputs["r"],
            q=inputs["q"],
            C=call_price,
            P=put_price,
        )

        assert "discrepancy" in parity
        assert isinstance(parity["discrepancy"], (int, float))
        assert abs(parity["discrepancy"]) < 1e-6

        print("  unified inputs: OK")
        print(f"  option pricing: OK (call={call_price:.6f})")
        print("  Greeks: OK")
        print(f"  implied volatility: OK (iv={iv:.6f})")
        print(
            f"  put-call parity: OK "
            f"(discrepancy={parity['discrepancy']:.3e})"
        )


if __name__ == "__main__":
    print("Running Black-Scholes adapter self-check...")
    _self_check()
    print("self-check passed")