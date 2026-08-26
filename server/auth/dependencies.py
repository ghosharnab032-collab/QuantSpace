"""Authentication and entitlement dependencies."""

from datetime import datetime, timezone
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.auth.jwt import decode_access_token
from server.db import get_entitlement, get_user_by_id


bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Get the authenticated user from a JWT bearer token."""

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user


def require_entitlement(feature: str) -> Callable:
    """Create a dependency requiring a specific feature entitlement."""

    async def entitlement_dependency(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        entitlement = await get_entitlement(
            current_user["id"],
            feature,
        )

        if entitlement is None or not entitlement["active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Entitlement required: {feature}",
            )

        # Check optional expiration.
        if entitlement["expires_at"] is not None:
            expires_at = entitlement["expires_at"]

            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(
                        expires_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid entitlement expiration.",
                    )

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Entitlement expired: {feature}",
                )

        return entitlement

    return entitlement_dependency