"""Authentication and entitlement dependency tests."""

import jwt
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from server.auth.jwt import create_access_token
from server.auth.password import hash_password
from server.config import settings
from server.db import (
    create_user,
    get_db_client,
    grant_entitlement,
    init_db,
)
from server.main import app


client = TestClient(app)


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


async def create_test_user(
    email: str = "dependency@example.com",
) -> dict:
    """Create a test user."""

    return await create_user(
        email,
        hash_password("password123"),
    )


def test_missing_token():
    response = client.get(
        "/api/v1/test-protected/auth"
    )

    assert response.status_code == 401


def test_invalid_token():
    response = client.get(
        "/api/v1/test-protected/auth",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_token():
    user = await create_test_user()

    token = create_access_token(user["id"])

    response = client.get(
        "/api/v1/test-protected/auth",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == user["id"]
    assert data["email"] == user["email"]


@pytest.mark.asyncio
async def test_missing_entitlement():
    user = await create_test_user()

    token = create_access_token(user["id"])

    response = client.get(
        "/api/v1/test-protected/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 403
    assert "Entitlement required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_active_entitlement_allows_access():
    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    token = create_access_token(user["id"])

    response = client.get(
        "/api/v1/test-protected/monte-carlo",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "allowed"
    assert data["feature"] == "monte_carlo"


@pytest.mark.asyncio
async def test_expired_token():
    user = await create_test_user()

    payload = {
        "sub": str(user["id"]),
        "iat": 1,
        "exp": 1,
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/v1/test-protected/auth",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401