"""
black_scholes.py
================

Focused, interview-ready Black-Scholes implementation.

Features
--------
- European call / put pricing
- Greeks: delta, gamma, vega, theta, rho
- Implied volatility via Brent's method
- Put-call parity verification
- Input validation with clear error messages

No exotic models (Heston, jumps, etc.). Depth over breadth.

Dependencies: numpy, scipy
"""

from __future__ import annotations

import math

from typing import Literal, Optional, Tuple

import numpy as np
from scipy.optimize import brentq


OptionType = Literal["call", "put"]


# ==============================================================================
# Input validation
# ==============================================================================

def _validate_inputs(
    S: float,
    K: float,
    T: float,
    sigma: Optional[float],
    r: float,
    q: float,
) -> None:
    """Validate Black-Scholes inputs."""
    for name, val in [("S", S), ("K", K), ("T", T), ("r", r), ("q", q)]:
        if not np.isfinite(val):
            raise ValueError(f"{name} must be finite, got {val}")
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"Strike K must be positive, got {K}")
    if T < 0:
        raise ValueError(f"Time to expiry T must be non-negative, got {T}")
    if sigma is not None and (sigma < 0 or not np.isfinite(sigma)):
        raise ValueError(f"Volatility sigma must be non-negative and finite, got {sigma}")


# ==============================================================================
# Core pricing
# ==============================================================================

def d1_d2(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float,
) -> Tuple[float, float]:
    """Compute d1 and d2 for Black-Scholes."""
    if T == 0:
        d1_val = float("inf") if S > K else float("-inf") if S < K else 0.0
        return d1_val, d1_val

    if sigma == 0:
        # Deterministic forward case. Avoid 0/0 and NaN at the
        # forward-at-the-money boundary. The sign is determined by
        # log(S/K) + (r-q)T, i.e. by S*exp((r-q)T) relative to K.
        moneyness = np.log(S / K) + (r - q) * T
        if moneyness > 0:
            return float("inf"), float("inf")
        if moneyness < 0:
            return float("-inf"), float("-inf")
        return 0.0, 0.0

    sig_sqrt_t = sigma * np.sqrt(T)
    d1_val = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / sig_sqrt_t
    d2_val = d1_val - sig_sqrt_t
    return d1_val, d2_val


def price(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
    *,
    option_type: OptionType = "call",
) -> float:
    """
    Black-Scholes price for a European option.

    Parameters
    ----------
    S : float
        Current spot price (> 0)
    K : float
        Strike price (> 0)
    T : float
        Time to expiry in years (>= 0)
    sigma : float
        Implied volatility (>= 0)
    r : float
        Risk-free rate (continuously compounded)
    q : float
        Dividend yield (continuously compounded)
    option_type : {"call", "put"}

    Returns
    -------
    float
        Option premium
    """
    _validate_inputs(S, K, T, sigma, r, q)

    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'.")

    if T == 0:
        if option_type == "call":
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    if sigma == 0:
        # Deterministic terminal spot under zero volatility.
        forward_spot = S * np.exp((r - q) * T)
        discount_factor = np.exp(-r * T)
        if option_type == "call":
            return float(discount_factor * max(forward_spot - K, 0.0))
        return float(discount_factor * max(K - forward_spot, 0.0))

    d1_val, d2_val = d1_d2(S, K, T, sigma, r, q)

    disc_factor = np.exp(-q * T)
    strike_disc = np.exp(-r * T)

    if option_type == "call":
        return S * disc_factor * _N(d1_val) - K * strike_disc * _N(d2_val)

    # put
    return K * strike_disc * _N(-d2_val) - S * disc_factor * _N(-d1_val)


# ==============================================================================
# Greeks
# ==============================================================================

def delta(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
    *,
    option_type: OptionType = "call",
) -> float:
    """Delta: rate of change of option price w.r.t. spot."""
    _validate_inputs(S, K, T, sigma, r, q)

    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'.")

    if T == 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0 if S < K else 0.5
        return -1.0 if S < K else 0.0 if S > K else -0.5

    if sigma == 0:
        forward_spot = S * np.exp((r - q) * T)
        if forward_spot > K:
            call_delta = np.exp(-q * T)
        elif forward_spot < K:
            call_delta = 0.0
        else:
            call_delta = 0.5 * np.exp(-q * T)
        return float(call_delta if option_type == "call" else call_delta - np.exp(-q*T))

    d1_val, _ = d1_d2(S, K, T, sigma, r, q)
    disc = np.exp(-q * T)

    if option_type == "call":
        return disc * _N(d1_val)
    return disc * (_N(d1_val) - 1.0)


def gamma(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
) -> float:
    """Gamma: rate of change of delta w.r.t. spot. Same for call and put."""
    _validate_inputs(S, K, T, sigma, r, q)

    if T == 0 or sigma == 0:
        return 0.0

    d1_val, _ = d1_d2(S, K, T, sigma, r, q)
    return (
        np.exp(-q * T)
        * _n(d1_val)
        / (S * sigma * np.sqrt(T))
    )


def vega(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
) -> float:
    """
    Vega: sensitivity to a 1 percentage-point change in volatility.
    Returns the change in price for a 1% move in sigma.
    """
    _validate_inputs(S, K, T, sigma, r, q)

    if T == 0 or sigma == 0:
        return 0.0

    d1_val, _ = d1_d2(S, K, T, sigma, r, q)
    # Vega per 1% change in sigma
    return (
        S * np.exp(-q * T)
        * _n(d1_val)
        * np.sqrt(T)
        / 100.0
    )


def theta(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
    *,
    option_type: OptionType = "call",
) -> float:
    """
    Theta: daily time decay.
    Returns the change in price per calendar day.
    """
    _validate_inputs(S, K, T, sigma, r, q)

    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'.")

    if T == 0 or sigma == 0:
        return 0.0

    d1_val, d2_val = d1_d2(S, K, T, sigma, r, q)
    disc = np.exp(-q * T)
    strike_disc = np.exp(-r * T)

    term1 = -(
        S * disc * _n(d1_val) * sigma
        / (2.0 * np.sqrt(T))
    )

    if option_type == "call":
        term2 = q * S * disc * _N(d1_val)
        term3 = -r * K * strike_disc * _N(d2_val)
    else:
        term2 = -q * S * disc * _N(-d1_val)
        term3 = r * K * strike_disc * _N(-d2_val)

    # Per calendar day
    return (term1 + term2 + term3) / 365.0


def rho(
    S: float,
    K: float,
    T: float,
    sigma: float,
    r: float,
    q: float = 0.0,
    *,
    option_type: OptionType = "call",
) -> float:
    """
    Rho: sensitivity to a 1 percentage-point change in interest rate.
    Returns the change in price for a 1% move in r.
    """
    _validate_inputs(S, K, T, sigma, r, q)

    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'.")

    if T == 0 or sigma == 0:
        return 0.0

    _, d2_val = d1_d2(S, K, T, sigma, r, q)
    strike_disc = np.exp(-r * T)

    if option_type == "call":
        return K * T * strike_disc * _N(d2_val) / 100.0
    return -K * T * strike_disc * _N(-d2_val) / 100.0


# ==============================================================================
# Implied volatility
# ==============================================================================

def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    *,
    option_type: OptionType = "call",
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float:
    """
    Solve for implied volatility using Brent's method.

    Parameters
    ----------
    market_price : float
        Observed market price of the option
    S, K, T, r, q : float
        Standard Black-Scholes inputs
    option_type : {"call", "put"}
    tol : float
        Tolerance for Brent's method
    max_iter : int
        Maximum iterations (passed to Brent)

    Returns
    -------
    float
        Implied volatility

    Raises
    ------
    ValueError
        If market_price is below intrinsic value or inputs are invalid.
    RuntimeError
        If Brent's method fails to converge.
    """
    _validate_inputs(S, K, T, None, r, q)

    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'.")

    if T == 0:
        raise ValueError("Implied volatility is undefined at expiry (T=0).")

    if market_price < 0:
        raise ValueError("Market price cannot be negative.")

    # Intrinsic value bound
    if option_type == "call":
        intrinsic = max(S * np.exp(-q * T) - K * np.exp(-r * T), 0.0)
    else:
        intrinsic = max(K * np.exp(-r * T) - S * np.exp(-q * T), 0.0)

    if market_price < intrinsic - 1e-12:
        raise ValueError(
            f"Market price {market_price:.6f} is below intrinsic value "
            f"{intrinsic:.6f}. No solution exists."
        )

    # If price is at or very near intrinsic, IV is effectively zero.
    if market_price <= intrinsic + 1e-10:
        return 0.0

    # Upper bound: as sigma -> infinity, call -> S * e^(-qT), put -> K * e^(-rT)
    if option_type == "call":
        upper_price = S * np.exp(-q * T)
    else:
        upper_price = K * np.exp(-r * T)

    if market_price >= upper_price:
        raise ValueError(
            f"Market price {market_price:.6f} exceeds or equals the "
            f"theoretical maximum {upper_price:.6f} for finite volatility."
        )

    def objective(sigma: float) -> float:
        return price(S, K, T, sigma, r, q, option_type=option_type) - market_price

    # Find bounds for Brent
    # Lower bound: 0 (or very small)
    # Upper bound: find by expansion
    low, high = 1e-12, 5.0
    max_sigma = 100.0

    # Expand without overshooting the hard cap. If the cap itself
    # brackets the root, retain it instead of discarding the bracket.
    while objective(high) < 0 and high < max_sigma:
        high = min(high * 2.0, max_sigma)

    if objective(high) < 0:
        raise RuntimeError(
            "Could not find an upper bound for implied volatility up to "
            f"{max_sigma:.0f}. The market price may be too high."
        )

    try:
        iv = brentq(
            objective,
            low,
            high,
            xtol=tol,
            maxiter=max_iter,
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Brent's method failed: {exc}. "
            f"Price={market_price}, bounds=[{low}, {high}]"
        )

    return float(iv)


# ==============================================================================
# Put-call parity
# ==============================================================================

def put_call_parity(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    *,
    C: Optional[float] = None,
    P: Optional[float] = None,
) -> dict:
    """
    Put-call parity for European options:
        C - P = S * e^(-qT) - K * e^(-rT)

    Parameters
    ----------
    C : float, optional
        Call price. If provided with P, verifies parity.
    P : float, optional
        Put price. If provided with C, verifies parity.

    Returns
    -------
    dict
        {
            "forward": float,      # S * e^(-qT) - K * e^(-rT)
            "parity_holds": bool,  # only if both C and P given
            "discrepancy": float,  # C - P - forward
            "implied_call": float, # if only P given
            "implied_put": float,  # if only C given
        }
    """
    _validate_inputs(S, K, T, None, r, q)

    forward = S * np.exp(-q * T) - K * np.exp(-r * T)

    result = {
        "forward": float(forward),
        "parity_holds": None,
        "discrepancy": None,
        "implied_call": None,
        "implied_put": None,
    }

    if C is not None and P is not None:
        discrepancy = C - P - forward
        result["discrepancy"] = float(discrepancy)
        result["parity_holds"] = abs(discrepancy) < 1e-6
    elif C is not None:
        result["implied_put"] = float(C - forward)
    elif P is not None:
        result["implied_call"] = float(P + forward)

    return result


# ==============================================================================
# Utility: CDF and PDF of standard normal
# ==============================================================================

def _N(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / np.sqrt(2.0)))


def _n(x: float) -> float:
    """Standard normal PDF."""
    return np.exp(-0.5 * x**2) / np.sqrt(2.0 * np.pi)


# ==============================================================================
# Demo / tests
# ==============================================================================

def _run_tests() -> None:
    """Unit tests for the Black-Scholes implementation."""

    print("=" * 50)
    print("BLACK-SCHOLES UNIT TESTS")
    print("=" * 50)

    # Standard test parameters
    S, K, T, sigma, r, q = 100.0, 100.0, 1.0, 0.20, 0.05, 0.02

    # --- Test 1: Prices >= intrinsic value ---
    print("\n1. Price >= intrinsic value")
    for opt_type in ["call", "put"]:
        for S_test in [80.0, 100.0, 120.0]:
            p = price(S_test, K, T, sigma, r, q, option_type=opt_type)
            if opt_type == "call":
                intrinsic = max(S_test * np.exp(-q * T) - K * np.exp(-r * T), 0.0)
            else:
                intrinsic = max(K * np.exp(-r * T) - S_test * np.exp(-q * T), 0.0)
            assert p >= intrinsic - 1e-10, f"{opt_type} price {p} < intrinsic {intrinsic}"
    print("   ✅ Passed")

    # --- Test 2: Delta ranges ---
    print("\n2. Delta ranges")
    for S_test in [50.0, 100.0, 150.0]:
        d_call = delta(S_test, K, T, sigma, r, q, option_type="call")
        d_put = delta(S_test, K, T, sigma, r, q, option_type="put")
        assert 0.0 <= d_call <= 1.0, f"Call delta {d_call} out of range"
        assert -1.0 <= d_put <= 0.0, f"Put delta {d_put} out of range"
    print("   ✅ Passed")

    # --- Test 3: Gamma, vega >= 0 ---
    print("\n3. Gamma, vega >= 0")
    for S_test in [50.0, 100.0, 150.0]:
        g = gamma(S_test, K, T, sigma, r, q)
        v = vega(S_test, K, T, sigma, r, q)
        assert g >= 0, f"Gamma {g} < 0"
        assert v >= 0, f"Vega {v} < 0"
    print("   ✅ Passed")

    # --- Test 4: Put-call parity ---
    print("\n4. Put-call parity")
    C = price(S, K, T, sigma, r, q, option_type="call")
    P = price(S, K, T, sigma, r, q, option_type="put")
    parity = put_call_parity(S, K, T, r, q, C=C, P=P)
    assert parity["parity_holds"], f"Parity failed: discrepancy={parity['discrepancy']}"
    print(f"   C={C:.4f}, P={P:.4f}, forward={parity['forward']:.4f}")
    print("   ✅ Passed")

    # --- Test 5: Invalid inputs raise ValueError ---
    print("\n5. Invalid inputs")
    invalid_cases = [
        (lambda: price(-100, K, T, sigma, r, q), "negative S"),
        (lambda: price(S, -K, T, sigma, r, q), "negative K"),
        (lambda: price(S, K, -T, sigma, r, q), "negative T"),
        (lambda: price(S, K, T, -sigma, r, q), "negative sigma"),
        (lambda: implied_volatility(-1, S, K, T, r, q), "negative price"),
        (lambda: price(float("nan"), K, T, sigma, r, q), "NaN S"),
        (lambda: price(S, K, T, float("inf"), r, q), "inf sigma"),
        (lambda: price(S, K, T, sigma, float("nan"), q), "NaN r"),
    ]
    for fn, desc in invalid_cases:
        try:
            fn()
            assert False, f"Should have raised for {desc}"
        except ValueError:
            pass
    print("   ✅ Passed")

    # --- Test 6: Deep ITM/OTM behaviour ---
    print("\n6. Deep ITM/OTM")
    # Deep ITM call
    C_itm = price(200.0, 100.0, T, sigma, r, q, option_type="call")
    assert C_itm > 90.0, f"Deep ITM call too cheap: {C_itm}"
    # Deep OTM call
    C_otm = price(50.0, 100.0, T, sigma, r, q, option_type="call")
    assert C_otm < 1.0, f"Deep OTM call too expensive: {C_otm}"
    # Deep ITM put
    P_itm = price(50.0, 100.0, T, sigma, r, q, option_type="put")
    assert P_itm > 45.0, f"Deep ITM put too cheap: {P_itm}"
    # Deep OTM put
    P_otm = price(200.0, 100.0, T, sigma, r, q, option_type="put")
    assert P_otm < 1.0, f"Deep OTM put too expensive: {P_otm}"
    print("   ✅ Passed")

    # --- Test 7: Implied volatility round-trip ---
    print("\n7. Implied volatility round-trip")
    true_sigma = 0.35
    for opt_type in ["call", "put"]:
        market_p = price(S, K, T, true_sigma, r, q, option_type=opt_type)
        iv = implied_volatility(market_p, S, K, T, r, q, option_type=opt_type)
        assert abs(iv - true_sigma) < 1e-6, f"IV mismatch: {iv} vs {true_sigma}"
        print(f"   {opt_type}: true={true_sigma}, recovered={iv:.6f}")
    print("   ✅ Passed")

    # --- Test 8: IV monotonicity sanity check ---
    print("\n8. IV monotonicity")
    sigmas = [0.10, 0.20, 0.30, 0.40, 0.50]
    prices_call = [price(S, K, T, s, r, q, option_type="call") for s in sigmas]
    for i in range(1, len(prices_call)):
        assert prices_call[i] > prices_call[i-1], "Price not monotonic in sigma"
    print("   ✅ Passed")

    # --- Test 9: T=0 edge cases ---
    print("\n9. T=0 edge cases")
    C_atm = price(S, K, 0.0, sigma, r, q, option_type="call")
    assert abs(C_atm - max(S - K, 0.0)) < 1e-10, f"T=0 call mismatch"
    P_atm = price(S, K, 0.0, sigma, r, q, option_type="put")
    assert abs(P_atm - max(K - S, 0.0)) < 1e-10, f"T=0 put mismatch"
    print("   ✅ Passed")

    # --- Test 10: Parity implies the other price ---
    print("\n10. Parity implies other price")
    C = price(S, K, T, sigma, r, q, option_type="call")
    parity_C = put_call_parity(S, K, T, r, q, C=C)
    implied_P = parity_C["implied_put"]
    true_P = price(S, K, T, sigma, r, q, option_type="put")
    assert abs(implied_P - true_P) < 1e-10, f"Implied put mismatch"
    print("   ✅ Passed")

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED ✅")
    print("=" * 50)


if __name__ == "__main__":
    _run_tests()