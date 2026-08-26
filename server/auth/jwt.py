"""JWT creation and decoding utilities."""

from datetime import datetime, timedelta, timezone

import jwt

from server.config import settings


def create_access_token(user_id: int) -> str:
    """Create a JWT access token."""

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type.")

    return payload