import pytest
import pytest_asyncio

from server.db import (
    create_user,
    get_db_client,
    get_user_by_email,
    get_user_by_id,
    init_db,
)


@pytest_asyncio.fixture(autouse=True)
async def clean_users():
    await init_db()

    client = await get_db_client()
    await client.execute("DELETE FROM users")

    yield

    await client.execute("DELETE FROM users")


@pytest.mark.asyncio
async def test_create_user():
    user = await create_user(
        "alice@example.com",
        "fake_hash_123",
    )

    assert user["email"] == "alice@example.com"
    assert isinstance(user["id"], int)
    assert user["is_active"] is True


@pytest.mark.asyncio
async def test_get_user_by_email():
    await create_user(
        "bob@example.com",
        "hash_bob",
    )

    user = await get_user_by_email(
        "bob@example.com"
    )

    assert user is not None
    assert user["email"] == "bob@example.com"
    assert user["password_hash"] == "hash_bob"


@pytest.mark.asyncio
async def test_get_user_by_id():
    created = await create_user(
        "charlie@example.com",
        "hash_charlie",
    )

    user = await get_user_by_id(
        created["id"]
    )

    assert user is not None
    assert user["email"] == "charlie@example.com"


@pytest.mark.asyncio
async def test_user_not_found():
    assert await get_user_by_email(
        "nobody@example.com"
    ) is None

    assert await get_user_by_id(
        999999
    ) is None


@pytest.mark.asyncio
async def test_email_is_unique():
    await create_user(
        "duplicate@example.com",
        "hash1",
    )

    with pytest.raises(Exception):
        await create_user(
            "duplicate@example.com",
            "hash2",
        )