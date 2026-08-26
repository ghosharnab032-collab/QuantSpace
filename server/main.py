"""Quant Space FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.db.database import close_db_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application shutdown without initializing the DB on startup."""
    yield
    await close_db_client()


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
    lifespan=lifespan,
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
# ============================================================

app.include_router(
    auth_router,
    prefix="/api/v1",
)


# ============================================================
# PAYMENTS
# ============================================================

app.include_router(
    payments_router,
    prefix="/api/v1",
)


# ============================================================
# ENTITLEMENTS
# ============================================================

app.include_router(
    entitlements_router,
    prefix="/api/v1",
)


# ============================================================
# QUANT
# ============================================================

app.include_router(
    quant_router,
    prefix="/api/v1",
)


# ============================================================
# MARKET DATA
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