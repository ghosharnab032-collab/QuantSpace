"""Authentication request and response schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=128,
    )


class UserResponse(BaseModel):
    """Safe public representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: str
    is_active: bool


class TokenResponse(BaseModel):
    """JWT access-token response."""

    access_token: str
    token_type: str = "bearer"