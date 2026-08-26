"""Quant Space FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# ROUTERS
# ============================================================

from server.auth.router import router as auth_router
from server.payments.router import router as payments_router

from server.api.entitlements import (
    router as entitlements_router,
)

from server.api.quant.router import (
    router as quant_router,
)

from server.api.market_Data.market_data import (
    router as market_data_router,
)

from server.services.routes.backtesting import (
    router as backtesting_router,
)

from server.services.routes.black_scholes import (
    router as black_scholes_router,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Quant Space",
    version="1.0.0",
    description=(
        "Quantitative finance platform providing "
        "market data, Monte Carlo simulation, "
        "portfolio optimization, backtesting, "
        "and Black-Scholes option analytics."
    ),
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://quant-space-delta.vercel.app",
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)

# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/api/v1/health",
    tags=["health"],
)
async def health():
    return {
        "status": "ok",
        "service": "quant-space",
        "version": "1.0.0",
    }


# ============================================================
# AUTH
#
# Router prefix:
#     /auth
#
# Final:
#     /api/v1/auth/...
# ============================================================

app.include_router(
    auth_router,
    prefix="/api/v1",
)


# ============================================================
# PAYMENTS
#
# Router prefix:
#     /payments
#
# Final:
#     POST /api/v1/payments/order
#     POST /api/v1/payments/verify
# ============================================================

app.include_router(
    payments_router,
    prefix="/api/v1",
)


# ============================================================
# ENTITLEMENTS
#
# Router prefix:
#     /entitlements
#
# Final:
#     GET /api/v1/entitlements/{feature}
# ============================================================

app.include_router(
    entitlements_router,
    prefix="/api/v1",
)


# ============================================================
# QUANT
#
# quant/router.py contains:
#
#     /quant/monte-carlo
#     /quant/optimizer
#     /quant/optimizer/health
#
# Final:
#
#     POST /api/v1/quant/monte-carlo
#     POST /api/v1/quant/optimizer
#     GET  /api/v1/quant/optimizer/health
# ============================================================

app.include_router(
    quant_router,
    prefix="/api/v1",
)


# ============================================================
# MARKET DATA
#
# server/api/market_data.py contains:
#
#     /market-data/assets/{ticker}
#     /market-data/{ticker}/history
#
# Final:
#
#     GET /api/v1/market-data/assets/{ticker}
#     GET /api/v1/market-data/{ticker}/history
# ============================================================

app.include_router(
    market_data_router,
    prefix="/api/v1",
)


# ============================================================
# BACKTESTING
# ============================================================

app.include_router(
    backtesting_router,
    prefix="/api/v1",
)


# ============================================================
# BLACK-SCHOLES
# ============================================================

app.include_router(
    black_scholes_router,
    prefix="/api/v1",
)


# ============================================================
# ROOT
# ============================================================

@app.get(
    "/",
    tags=["health"],
)
async def root():
    return {
        "name": "Quant Space",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }