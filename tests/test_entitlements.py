"""Entitlement database tests."""

import pytest
import pytest_asyncio

from server.auth.password import hash_password
from server.db import (
    create_user,
    get_db_client,
    get_entitlement,
    grant_entitlement,
    init_db,
    revoke_entitlement,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_data():
    """Initialize database and clean test data."""

    await init_db()

    db = await get_db_client()

    await db.execute("DELETE FROM entitlements")
    await db.execute("DELETE FROM users")

    yield

    await db.execute("DELETE FROM entitlements")
    await db.execute("DELETE FROM users")


async def create_test_user() -> dict:
    """Create a user for entitlement tests."""

    return await create_user(
        "entitlement@example.com",
        hash_password("password123"),
    )


@pytest.mark.asyncio
async def test_grant_entitlement():
    user = await create_test_user()

    entitlement = await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    assert entitlement["user_id"] == user["id"]
    assert entitlement["feature"] == "monte_carlo"
    assert entitlement["active"] is True


@pytest.mark.asyncio
async def test_get_entitlement():
    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    entitlement = await get_entitlement(
        user["id"],
        "monte_carlo",
    )

    assert entitlement is not None
    assert entitlement["feature"] == "monte_carlo"
    assert entitlement["active"] is True


@pytest.mark.asyncio
async def test_missing_entitlement():
    user = await create_test_user()

    entitlement = await get_entitlement(
        user["id"],
        "monte_carlo",
    )

    assert entitlement is None


@pytest.mark.asyncio
async def test_revoke_entitlement():
    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    revoked = await revoke_entitlement(
        user["id"],
        "monte_carlo",
    )

    assert revoked is True

    entitlement = await get_entitlement(
        user["id"],
        "monte_carlo",
    )

    assert entitlement is not None
    assert entitlement["active"] is False


@pytest.mark.asyncio
async def test_grant_reactivates_existing_entitlement():
    user = await create_test_user()

    await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    await revoke_entitlement(
        user["id"],
        "monte_carlo",
    )

    entitlement = await grant_entitlement(
        user["id"],
        "monte_carlo",
    )

    assert entitlement["active"] is True