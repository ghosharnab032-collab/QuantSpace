"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Application
    app_name: str
    api_prefix: str
    frontend_origin: str

    # Database
    database_url: str
    database_auth_token: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int

    # Razorpay
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""

        return cls(
            # ---------------------------------------------------------
            # Application
            # ---------------------------------------------------------
            app_name=os.getenv(
                "APP_NAME",
                "Quant Tools Marketplace API",
            ),
            api_prefix=os.getenv(
                "API_PREFIX",
                "/api/v1",
            ),
            frontend_origin=os.getenv(
                "FRONTEND_ORIGIN",
                "http://localhost:5173",
            ),

            # ---------------------------------------------------------
            # Database
            # ---------------------------------------------------------
            database_url=os.getenv(
                "TURSO_DATABASE_URL",
                "file:app.db",
            ),
            database_auth_token=os.getenv(
                "TURSO_AUTH_TOKEN",
                "",
            ),

            # ---------------------------------------------------------
            # JWT
            # ---------------------------------------------------------
            jwt_secret_key=os.getenv(
                "JWT_SECRET_KEY",
                "dev-only-change-this",
            ),
            jwt_algorithm=os.getenv(
                "JWT_ALGORITHM",
                "HS256",
            ),
            jwt_access_token_expire_minutes=int(
                os.getenv(
                    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
                    "30",
                )
            ),

            # ---------------------------------------------------------
            # Razorpay
            # ---------------------------------------------------------
            razorpay_key_id=os.getenv(
                "RAZORPAY_KEY_ID",
                "",
            ),
            razorpay_key_secret=os.getenv(
                "RAZORPAY_KEY_SECRET",
                "",
            ),
            razorpay_webhook_secret=os.getenv(
                "RAZORPAY_WEBHOOK_SECRET",
                "",
            ),
        )


settings = Settings.from_env()