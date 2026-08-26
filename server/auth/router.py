"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, status

from server.auth.jwt import create_access_token
from server.auth.password import hash_password, verify_password
from server.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from server.db import create_user, get_user_by_email


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
) -> UserResponse:
    """Register a new user."""

    email = str(request.email).strip().lower()

    existing_user = await get_user_by_email(email)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    password_hash = hash_password(request.password)

    user = await create_user(
        email=email,
        password_hash=password_hash,
    )

    return UserResponse(
        id=user["id"],
        email=user["email"],
        created_at=str(user["created_at"]),
        is_active=user["is_active"],
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: LoginRequest,
) -> TokenResponse:
    """Authenticate a user and issue a JWT."""

    email = str(request.email).strip().lower()

    user = await get_user_by_email(email)

    # Do not reveal whether the email exists.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    if not verify_password(
        request.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(user["id"])

    return TokenResponse(
        access_token=access_token,
    )