[CODEBASE_ANALYSIS.md](https://github.com/user-attachments/files/31512736/CODEBASE_ANALYSIS.md)
# QuantSpace

**Note:** The Razorpay integration on the live deployment is a demo/test link — no real money will be deducted.

Live deployment: https://quant-space-delta.vercel.app

This document is an outside read of the current state of the repo — what's actually built, how the pieces fit together, and where the gaps are. It's meant as a working reference, not a polished product README.

## 1. What this is

QuantSpace is a quant-finance tools platform aimed at the Indian market (NSE/BSE), with:

- A **FastAPI backend** (`server/`) handling auth, payments (Razorpay), entitlements, and quant compute endpoints
- A **React + Vite frontend** (`frontend/`) with one page per tool (Black-Scholes, Monte Carlo, Portfolio Optimizer, Backtester) plus a market data/chart view
- A **data pipeline** (`data/`, `scripts/`, `database/`) that ingests and validates NSE price/dividend/corporate-action data into a libSQL (Turso) database
- A **quant tools library** (`quant_tools/`) with the actual financial models, decoupled from the API layer via `adapters/`

The overall shape is: `quant_tools` (pure math) → `adapters` (I/O-friendly wrappers) → `server/api` + `server/services` (HTTP layer, gated by auth/entitlements) → `frontend` (per-tool React pages).

## 2. Stack

| Layer | Choice |
|---|---|
| Backend framework | FastAPI 0.141, Uvicorn |
| Database | libSQL / Turso (SQLite-compatible, edge-hosted) |
| Auth | Custom JWT (PyJWT) + argon2 password hashing (pwdlib) |
| Payments | Razorpay SDK |
| Numerics | NumPy, SciPy, pandas |
| Market data | `nse` package for live/official NSE data |
| Frontend | React + Vite, `lightweight-charts` for market charts |
| Testing | pytest (backend only — no frontend tests found) |

Nothing exotic here — it's a conventional, sensible stack for this kind of project, and the versions in `requirements-backend.txt` are current.

## 3. Backend architecture

`server/main.py` wires together six routers under `/api/v1`: `auth`, `payments`, `entitlements`, `quant`, `market_data`, `backtesting`, and `black_scholes` (the last runs unprefixed by its own router but still mounted under `/api/v1`). Structure is clean and consistent — each domain has its own `router.py`, `schemas.py` (Pydantic), and where relevant a `service.py` for business logic separate from the route handler. `server/db/` centralizes all SQL, so routes never touch the database client directly.

**Auth flow**: email/password → argon2 hash → JWT with configurable expiry. `verify_password` deliberately returns a generic "invalid email or password" on both a missing user and a wrong password, which is the right call for not leaking account existence.

**Entitlements**: a feature-flag-style table (`user_id`, `feature`, `active`, `expires_at`) checked via a `require_entitlement("feature_name")` FastAPI dependency. This is the gating mechanism for paid tools.

**Payments**: Razorpay order creation + signature verification, with the verified webhook/callback granting the entitlement row. Reasonably standard integration.

### Gap worth flagging: inconsistent gating

Only the **Monte Carlo** endpoint (`/quant/monte-carlo`) is wrapped in `require_entitlement("monte_carlo")`. The **Portfolio Optimizer**, **Backtester**, and **Black-Scholes** endpoints have no auth or entitlement dependency at all — they're fully open. If the monetization model is "four gated tools," three of the four routes currently give away the compute for free. This may well be intentional for this stage (dev/demo), but it's the single most important thing to check before treating the Gumroad/Razorpay version as revenue-ready.

## 4. Data pipeline

This is the most mature part of the repo. `data/ingest.py` is a deliberately strict, single-direction pipeline:

1. Load from source (CSV, NSE bhavcopy, live NSE)
2. Normalize into a common schema
3. Validate OHLCV per row (the SQL schema itself enforces `high ≥ open/close`, `low ≤ open/close`, positive prices, etc. — validation is pushed into the database, not just application code)
5. Verify the ticker already exists in `assets` (assets are owned by `asset_loader.py`; ingestion never silently creates them)
5. Insert immutable rows into `price_daily`, skipping existing `(ticker, date, source)` combinations
6. Log every run in `data_runs`, with rejected rows captured in `rejected_rows` rather than silently dropped

That's a genuinely good design for a financial data pipeline: idempotent inserts, an audit trail of rejections, and DB-level constraints as a second line of defense. `scripts/populate_nifty50.py`, `populate_midcap150.py`, etc. suggest coverage across NSE index constituents, and `dividend_yield*.py` / `corporate_actions` handle the messier real-world adjustments (splits, dividends) that a lot of hobby projects skip.

## 5. Quant tools

`quant_tools/` holds the actual models:

- `black_scholes_v2.py` — pricing, full Greeks (delta/gamma/vega/theta/rho), implied volatility, put-call parity
- `monte_carlo_v3.py` — portfolio simulation
- `portfolio_optimizer_v6.py` — rolling maximum-Sharpe optimization with weight caps and transaction costs
- `india_backtester.py` — MA-crossover backtester with an India-specific equity delivery cost model (STT, brokerage, etc.)

The `_v2`/`_v3`/`_v6` suffixes suggest active iteration rather than a single frozen version — worth eventually renaming once these stabilize, since the version number in the filename doesn't mean anything to an importer and just adds noise (`from quant_tools.black_scholes_v2 import price` reads oddly once there's no `v1` around).

`adapters/` wraps each tool for the API layer (input coercion, output shaping) — a reasonable seam that keeps `quant_tools` framework-agnostic and unit-testable on its own.

## 6. Frontend

Vite + React, unstyled beyond per-component CSS files (no Tailwind/component library). One `.jsx` + `.css` pair per tool (`BlackScholes`, `MonteCarlo`, `PortfolioOptimizer`, `Backtesting`), a `Dashboard`, a `MarketData`/`MarketChart` pair using `lightweight-charts`, and a `Login`/`AuthContext` pair for the auth state. `frontend/src/api/` mirrors the backend's route groups almost 1:1 (`auth.js`, `payments.js`, `quant.js`, `marketdata.js`, `entitlements.js`) — a clean, low-magic API client layer.

One stray file: `src/components/backtesting.jsx` sits **outside** `frontend/`, at the repo root, alongside an empty `src/` directory. It looks like a leftover from before the frontend was moved into its own folder — worth deleting or confirming it's not accidentally being built from two places.

## 7. Tests

Backend test coverage is real, not decorative:

- `test_auth.py` (250 lines), `test_payments.py` (220), `test_quant.py` (488), `test_dependencies.py`, `test_entitlements.py`, `test_db.py`, `test_health.py`

`test_quant.py` being the largest file suggests the numerical correctness of the models has had real attention (edge cases, known-value checks are typical for Black-Scholes/Monte Carlo tests). There is no frontend test suite (no Vitest/Jest/RTL config found) — fine for a solo project at this stage, but worth naming as a known gap rather than an oversight if this goes further.

## 8. Configuration & secrets

`server/config.py` loads everything through a single frozen `Settings` dataclass from env vars, with sane local-dev fallbacks (`file:app.db` for the database, a clearly-labeled `dev-only-change-this` JWT secret). `.env.example` documents the required Turso variables. No obvious secrets are committed — the `.env.example` values are placeholders, not live credentials, and `.gitignore` is present.

