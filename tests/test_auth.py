"""Authentication endpoint tests."""

import jwt
import pytest_asyncio
from fastapi.testclient import TestClient

from server.auth.password import hash_password
from server.config import settings
from server.db import get_db_client, init_db
from server.main import app


client = TestClient(app)


@pytest_asyncio.fixture(autouse=True)
async def clean_users():
    """Initialize the database and clean users before and after each test."""

    await init_db()

    db = await get_db_client()
    await db.execute("DELETE FROM users")

    yield

    await db.execute("DELETE FROM users")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_user():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "strongpassword123",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "alice@example.com"
    assert isinstance(data["id"], int)
    assert data["is_active"] is True

    # Sensitive information must never be returned.
    assert "password" not in data
    assert "password_hash" not in data


def test_register_normalizes_email():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": " Alice@Example.COM ",
            "password": "strongpassword123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"


def test_duplicate_email():
    payload = {
        "email": "duplicate@example.com",
        "password": "strongpassword123",
    }

    first = client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    second = client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_password_validation():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_invalid_email():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "strongpassword123",
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_success():
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "correctpassword123",
        },
    )

    assert register_response.status_code == 201

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "correctpassword123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 20
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "correctpassword123",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrong@example.com",
            "password": "wrongpassword123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_unknown_email():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "somepassword123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


@pytest_asyncio.fixture
async def inactive_user():
    """Create an inactive test user."""

    user = await __import__(
        "server.db",
        fromlist=["create_user"],
    ).create_user(
        "inactive@example.com",
        hash_password("correctpassword123"),
    )

    db = await get_db_client()

    await db.execute(
        "UPDATE users SET is_active = 0 WHERE id = ?",
        [user["id"]],
    )

    return user


def test_login_inactive_user(inactive_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@example.com",
            "password": "correctpassword123",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive."


def test_login_returns_valid_jwt():
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "jwt@example.com",
            "password": "correctpassword123",
        },
    )

    assert register_response.status_code == 201

    user_id = register_response.json()["id"]

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "jwt@example.com",
            "password": "correctpassword123",
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload