"""Temporary protected routes for authentication testing."""

from fastapi import APIRouter, Depends

from server.auth.dependencies import (
    get_current_user,
    require_entitlement,
)


router = APIRouter(
    prefix="/test-protected",
    tags=["testing"],
)


@router.get("/auth")
async def protected_auth(
    current_user: dict = Depends(get_current_user),
):
    """Test JWT authentication."""

    return {
        "user_id": current_user["id"],
        "email": current_user["email"],
    }


@router.get("/monte-carlo")
async def protected_monte_carlo(
    entitlement: dict = Depends(
        require_entitlement("monte_carlo"),
    ),
):
    """Test entitlement protection."""

    return {
        "status": "allowed",
        "feature": entitlement["feature"],
    }