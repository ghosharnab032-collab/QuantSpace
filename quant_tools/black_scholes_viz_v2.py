"""
black_scholes_viz.py
====================

Simple visualization for Black-Scholes option pricing.

Run: python black_scholes_viz.py

Requires: matplotlib (optional — will raise clear error if missing)
"""

from pathlib import Path
import sys

import numpy as np

# Optional matplotlib with graceful fallback
try:
    import matplotlib.pyplot as plt  # type: ignore
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt = None  # type: ignore

# Robust import: prefer same-dir, fall back to output dir
try:
    from black_scholes_v2 import price, delta, gamma, vega, implied_volatility, put_call_parity
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from black_scholes_v2 import price, delta, gamma, vega, implied_volatility, put_call_parity


def _ensure_matplotlib() -> None:
    """Raise a clear error if matplotlib is not installed."""
    if not HAS_MATPLOTLIB:
        raise ImportError(
            "matplotlib is required for visualization. "
            "Install with: pip install matplotlib"
        )


def plot_premium_and_delta(
    K: float = 100.0,
    T: float = 1.0,
    sigma: float = 0.20,
    r: float = 0.05,
    q: float = 0.02,
    S_min: float = 50.0,
    S_max: float = 150.0,
    n_points: int = 200,
    output_dir: str = ".",
    show: bool = False,
) -> None:
    """
    Plot option premium and delta vs spot price.

    Saves to {output_dir}/bs_premium_delta.png
    """
    _ensure_matplotlib()

    if K <= 0:
        raise ValueError("K must be positive.")
    if n_points < 2:
        raise ValueError("n_points must be at least 2.")
    if S_min <= 0 or S_max <= S_min:
        raise ValueError("Require 0 < S_min < S_max.")

    spots = np.linspace(S_min, S_max, n_points)

    calls = [price(s, K, T, sigma, r, q, option_type="call") for s in spots]
    puts = [price(s, K, T, sigma, r, q, option_type="put") for s in spots]
    deltas_call = [delta(s, K, T, sigma, r, q, option_type="call") for s in spots]
    deltas_put = [delta(s, K, T, sigma, r, q, option_type="put") for s in spots]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Premium
    ax = axes[0]
    ax.plot(spots, calls, label="Call", color="green", linewidth=2)
    ax.plot(spots, puts, label="Put", color="red", linewidth=2)
    ax.axvline(K, color="gray", linestyle="--", alpha=0.5, label=f"Strike K={K}")
    ax.set_ylabel("Premium")
    ax.set_title(f"Black-Scholes Premium  (T={T}y, sigma={sigma:.0%}, r={r:.1%}, q={q:.1%})")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    # Delta
    ax = axes[1]
    ax.plot(spots, deltas_call, label="Call delta", color="green", linewidth=2)
    ax.plot(spots, deltas_put, label="Put delta", color="red", linewidth=2)
    ax.axvline(K, color="gray", linestyle="--", alpha=0.5)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.axhline(1, color="green", linestyle=":", alpha=0.3)
    ax.axhline(-1, color="red", linestyle=":", alpha=0.3)
    ax.set_xlabel("Spot Price")
    ax.set_ylabel("Delta")
    ax.set_title("Delta vs Spot")
    ax.legend(loc="center right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    out_path = Path(output_dir) / "bs_premium_delta.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")

    if show:
        plt.show()
    plt.close(fig)


def plot_gamma_and_vega(
    K: float = 100.0,
    T: float = 1.0,
    sigma: float = 0.20,
    r: float = 0.05,
    q: float = 0.02,
    S_min: float = 50.0,
    S_max: float = 150.0,
    n_points: int = 200,
    output_dir: str = ".",
    show: bool = False,
) -> None:
    """
    Plot gamma and vega vs spot price.

    Saves to {output_dir}/bs_greeks.png
    """
    _ensure_matplotlib()

    if K <= 0:
        raise ValueError("K must be positive.")
    if n_points < 2:
        raise ValueError("n_points must be at least 2.")
    if S_min <= 0 or S_max <= S_min:
        raise ValueError("Require 0 < S_min < S_max.")

    spots = np.linspace(S_min, S_max, n_points)

    gammas = [gamma(s, K, T, sigma, r, q) for s in spots]
    vegas = [vega(s, K, T, sigma, r, q) for s in spots]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Gamma
    ax = axes[0]
    ax.plot(spots, gammas, color="blue", linewidth=2)
    ax.axvline(K, color="gray", linestyle="--", alpha=0.5, label=f"Strike K={K}")
    ax.set_ylabel("Gamma")
    ax.set_title(f"Gamma vs Spot  (T={T}y, sigma={sigma:.0%})")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # Vega
    ax = axes[1]
    ax.plot(spots, vegas, color="purple", linewidth=2)
    ax.axvline(K, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Spot Price")
    ax.set_ylabel("Vega (per 1% vol)")
    ax.set_title("Vega vs Spot")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    out_path = Path(output_dir) / "bs_greeks.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")

    if show:
        plt.show()
    plt.close(fig)


def iv_demo() -> None:
    """Print implied-volatility round-trip for a range of true sigmas."""
    S, K, T, r, q = 100.0, 100.0, 1.0, 0.05, 0.02

    print("\n=== IMPLIED VOLATILITY DEMO ===")
    for true_sigma in [0.10, 0.20, 0.30, 0.50, 0.80]:
        market_p = price(S, K, T, true_sigma, r, q, option_type="call")
        iv = implied_volatility(market_p, S, K, T, r, q, option_type="call")
        print(f"True sigma={true_sigma:.2f}  ->  Market price={market_p:.4f}  ->  IV={iv:.6f}")

    print("\n=== PUT-CALL PARITY DEMO ===")
    C = price(S, K, T, 0.20, r, q, option_type="call")
    P = price(S, K, T, 0.20, r, q, option_type="put")
    parity = put_call_parity(S, K, T, r, q, C=C, P=P)
    print(f"C={C:.4f}, P={P:.4f}")
    print(f"Forward={parity['forward']:.4f}")
    print(f"C - P = {C - P:.4f}")
    print(f"Parity holds: {parity['parity_holds']}")
    if parity["implied_put"] is not None:
        print(f"Implied put from call: {parity['implied_put']:.4f} (true={P:.4f})")
    else:
        print(f"Discrepancy: {parity['discrepancy']:.2e}")


if __name__ == "__main__":
    iv_demo()
    plot_premium_and_delta(show=False)
    plot_gamma_and_vega(show=False)
    print("\nAll plots saved to current directory.")