"""
Application Configuration

Uses pydantic Settings for managing application configuration including
database URL, JWT secret key, and other environment-based settings.
"""

import os
import secrets
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "FastAPI Application"
    debug: bool = False
    api_v1_prefix: str = "/api"

    # Database
    database_url: str = "sqlite:///./app.db"

    # JWT Authentication
    jwt_secret_key: str = ""  # Must be set via environment variable
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # CORS - Must be explicitly configured, no wildcards allowed
    cors_origins: list[str] = ["http://localhost:3002", "http://localhost:5173", "http://localhost:3000", "http://localhost:3001", "http://localhost:3004"]

    # User Roles
    user_roles: list[str] = ["admin", "teacher", "student"]

    # MiniMax AI API (用于 AI 出题和知识点提取)
    minimax_api_key: str = ""
    minimax_group_id: str = ""


def validate_settings() -> None:
    """Validate critical settings on startup."""
    # Skip validation in test mode
    if os.environ.get("TESTING", "").lower() in ("1", "true", "yes"):
        return

    s = get_settings()
    # Generate a secure default only for development (never use in production)
    if not s.jwt_secret_key:
        if s.debug:
            # Only generate a warning in debug mode
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY not set! Using insecure default for development only. "
                "Set JWT_SECRET_KEY environment variable in production.",
                RuntimeWarning
            )
            return "dev-only-insecure-key-do-not-use-in-production"
        else:
            raise ValueError(
                "JWT_SECRET_KEY must be set in production environment. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

# Validate on module load
_ = validate_settings()
