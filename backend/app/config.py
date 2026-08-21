"""
Application Configuration

Uses pydantic Settings for managing application configuration including
database URL, JWT secret key, and other environment-based settings.
"""

from functools import lru_cache
import os

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
    cors_origins: list[str] = [
        "http://localhost:3002",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3004",
    ]

    # User Roles
    user_roles: list[str] = ["admin", "teacher", "student"]

    # MiniMax AI API (用于 AI 出题和知识点提取)
    minimax_api_key: str = ""

    # API docs (Swagger/ReDoc/OpenAPI). Disabled by default; enable locally only.
    enable_docs: bool = False

    # Redis (用于限流等). 容错：连不上由调用方降级。
    redis_url: str = "redis://localhost:6379/0"

    # PDF 导出中文字体路径（可选；留空则自动探测常见系统字体）
    pdf_font_path: str = ""


def validate_settings() -> None:
    """Validate critical settings on startup.

    JWT secret key must be explicitly set regardless of debug mode.
    Set TESTING=true to skip validation (e.g. unit tests).
    """
    if os.environ.get("TESTING", "").lower() in ("1", "true", "yes"):
        return

    s = get_settings()
    if not s.jwt_secret_key or s.jwt_secret_key == "change-me-in-production":
        raise ValueError(
            'JWT_SECRET_KEY must be set. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

# Validate on module load (raises if JWT_SECRET_KEY is missing)
validate_settings()
