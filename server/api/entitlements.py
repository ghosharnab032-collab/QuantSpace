"""Entitlement API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from server.auth.dependencies import get_current_user
from server.db.entitlements import get_entitlement


router = APIRouter(
    prefix="/entitlements",
    tags=["entitlements"],
)


@router.get("/{feature}")
async def get_feature_entitlement(
    feature: str,
    current_user: dict = Depends(get_current_user),
):
    """Return the current user's entitlement for a feature."""

    feature = feature.strip().lower()

    entitlement = await get_entitlement(
        current_user["id"],
        feature,
    )

    if entitlement is None:
        return {
            "feature": feature,
            "active": False,
            "expires_at": None,
        }

    return {
        "feature": entitlement["feature"],
        "active": entitlement["active"],
        "expires_at": entitlement["expires_at"],
    }