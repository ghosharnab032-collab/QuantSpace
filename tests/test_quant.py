"""Tests for the protected Monte Carlo API."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from server.auth.jwt import create_access_token
from server.auth.password import hash_password
from server.db import (
    create_user,
    get_db_client,
    grant_entitlement,
    init_db,
)
from server.main import app


client = TestClient(app)


# ---------------------------------------------------------------------------
# DATABASE FIXTURE
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def clean_data():
    """Clean users and entitlements around every test."""

    await init_db()

    db = await get_db_client()

    await db.execute("DELETE FROM entitlements")
    await db.execute("DELETE FROM users")

    yield

    await db.execute("DELETE FROM entitlements")
    await db.execute("DELETE FROM users")


# ---------------------------------------------------------------------------
# MOCK MARKET DATA
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_quant_data(monkeypatch):
    """Provide deterministic historical prices for tests."""

    import pandas as pd

    dates = [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
        "2025-01-04",
        "2025-01-05",
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
    ]

    frame = pd.DataFrame(
        {
            "RELIANCE": [
                100,
                101,
                102,
                101,
                103,
                104,
                105,
                106,
                107,
                108,
            ],
            "TCS": [
                100,
                100.5,
                101,
                102,
                101.5,
                103,
                104,
                104.5,
                105,
                106,
            ],
            "INFY": [
                100,
                99.5,
                101,
                102,
                102.5,
                103,
                104,
                105,
                105.5,
                107,
            ],
        },
        index=pd.to_datetime(dates),
    )

    def fake_get_prices(
        ticker,
        start_date=None,
        end_date=None,
    ):
        """Return deterministic prices for one ticker."""

        if ticker not in frame.columns:
            raise ValueError(
                f"Unknown test ticker: {ticker}"
            )

        return frame[[ticker]]

    monkeypatch.setattr(
        "adapters.monte_carlo_adapter.get_prices",
        fake_get_prices,
    )


# ---------------------------------------------------------------------------
# TEST USER HELPERS
# ---------------------------------------------------------------------------

async def create_test_user(
    email: str = "quant@example.com",
) -> dict:
    """Create a test user."""

    return await create_user(
        email,
        hash_password("password123"),
    )


# ---------------------------------------------------------------------------
# PAYLOAD HELPER
# ---------------------------------------------------------------------------

def valid_payload():
    """Return a valid Monte Carlo request."""

    return {
        "tickers": [
            "RELIANCE",
            "TCS",
            "INFY",
        ],
        "weights": [
            0.5,
            0.3,
            0.2,
        ],
        "initial_amount": 100000,
        "years": 1,
        "simulations": 1000,
        "strategy": "rebalance",
        "annual_drag": 0,
    }


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monte_carlo_requires_authentication(
    mock_quant_data,
):
    """Monte Carlo requires authentication."""

    response = client.post(
        "/api/v1/quant/monte-carlo",
        json=valid_payload(),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_monte_carlo_requires_entitlement(
    mock_quant_data,
):
    """Authenticated users require Monte Carlo entitlement."""

    user = await create_test_user()

    token = create_access_token(user["id"])

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=valid_payload(),
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# SUCCESS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monte_carlo_success(
    mock_quant_data,
):
    """Entitled users can run Monte Carlo."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=valid_payload(),
    )

    print("\nSTATUS:", response.status_code)
    print("BODY:", response.text)

    assert response.status_code == 200

    data = response.json()

    assert data["tickers"] == [
        "RELIANCE",
        "TCS",
        "INFY",
    ]

    assert data["weights"] == [
        0.5,
        0.3,
        0.2,
    ]

    assert data["initial_amount"] == 100000
    assert data["years"] == 1
    assert data["simulations"] == 1000
    assert data["strategy"] == "rebalance"
    assert data["annual_drag"] == 0

    assert "mean_final_wealth" in data
    assert "median_final_wealth" in data
    assert "percentile_5" in data
    assert "percentile_95" in data
    assert "probability_of_loss" in data
    assert "cvar_95_loss" in data
    assert "median_max_drawdown" in data
    assert "percentile_95_max_drawdown" in data


# ---------------------------------------------------------------------------
# DEFAULT WEIGHTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monte_carlo_default_weights(
    mock_quant_data,
):
    """Weights default to equal weighting."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload.pop("weights")

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["weights"] == pytest.approx(
        [
            1 / 3,
            1 / 3,
            1 / 3,
        ]
    )


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monte_carlo_weight_length_mismatch(
    mock_quant_data,
):
    """Weights must match ticker count."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload["weights"] = [0.5, 0.5]

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_monte_carlo_weights_not_sum_to_one(
    mock_quant_data,
):
    """Weights must sum to one."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload["weights"] = [0.5, 0.5, 0.5]

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_monte_carlo_negative_weight(
    mock_quant_data,
):
    """Negative weights are rejected."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload["weights"] = [0.8, 0.4, -0.2]

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_monte_carlo_zero_initial_amount(
    mock_quant_data,
):
    """Initial amount must be positive."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload["initial_amount"] = 0

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_monte_carlo_zero_simulations(
    mock_quant_data,
):
    """Simulation count must be positive."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload["simulations"] = 0

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_monte_carlo_invalid_strategy(
    mock_quant_data,
):
    """Invalid strategy is rejected."""

    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    payload = valid_payload()
    payload["strategy"] = "invalid"

    response = client.post(
        "/api/v1/quant/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )

    assert response.status_code == 422