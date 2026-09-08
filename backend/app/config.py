"""
Application Configuration

Uses pydantic Settings for managing application configuration including
database URL, JWT secret key, and other environment-based settings.
"""

from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# QA Critical：弱 JWT 密钥黑名单。
# 这些值常见于示例配置、本地 .env 或测试夹具，一旦被带到任何环境，
# 攻击者可用其自行签发任意 sub 的 token（get_current_user 完全信任 JWT 的 sub），
# 进而直接获得管理员权限 —— 属于认证绕过 + 提权。
# 新增凭据前先确认无人使用；追加新值即可，校验逻辑无需改动。
# 比较时统一转小写，因此大小写变体同样会被拒绝。
WEAK_JWT_SECRETS: frozenset[str] = frozenset(
    {
        "change-me-in-production",  # 原有校验项：示例配置里的占位值
        "dev-secret-key-for-testing-only-12345678",  # backend/.env 曾使用的本地开发值，已轮换
        "your-jwt-secret-key-here",  # backend/.env.example 里的占位值
        "your-secret-key",
        "your_secret_key",
        "secret",
        "secret-key",
        "jwt-secret-key",
        "changeme",
        "test",
        "test-secret-key-do-not-use-in-production",  # 测试夹具用值，禁止出现在任何部署中
    }
)

# 生产环境（DEBUG=false）要求的 JWT 密钥最小长度：32 字符 ≈ 256 bit 熵（token_hex(32)）
MIN_PROD_JWT_SECRET_LENGTH = 32

# 生成强密钥的命令，出现在所有报错信息里，保证提示可操作
_SECRET_GEN_HINT = 'python -c "import secrets; print(secrets.token_hex(32))"'


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

    # Observability（可观测性）
    sentry_dsn: str = ""  # 留空则不启用 Sentry
    environment: str = "development"  # development / staging / production
    log_json: bool = False  # 生产建议 true，输出 JSON 结构化日志

    # Cookie 安全标志（P0）：None 表示按环境自动推导，见 cookie_secure_flag。
    # 显式设为 true/false 可覆盖自动推导（生产 HTTPS 部署建议 true）。
    cookie_secure: bool | None = None

    # License 授权文件路径（相对后端工作目录；缺失则进入试用模式）
    license_file: str = "license.key"

    # SMTP 邮件通知（可选；smtp_enabled=false 时不发邮件）
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # 留空则使用 smtp_user

    @property
    def cookie_secure_flag(self) -> bool:
        """返回 set_cookie 的 secure 取值（P0：避免 token cookie 明文外泄）。

        取值优先级：
        1. 显式配置 COOKIE_SECURE=true/false（最高优先级，便于运维兜底）；
        2. TESTING 环境变量为真时返回 False —— 测试以 HTTP 明文运行，
           带 Secure 属性的 cookie 不会被客户端回传，会导致认证类测试失败；
        3. 其余情况按 DEBUG 推导：非调试模式（生产/预发）为 True，仅允许 HTTPS 传输。
        """
        if self.cookie_secure is not None:
            return self.cookie_secure
        if os.environ.get("TESTING", "").lower() in ("1", "true", "yes"):
            return False
        return not self.debug


def validate_jwt_secret(secret: str, debug: bool) -> None:
    """校验 JWT 密钥强度（QA Critical：弱/短密钥可用来自签 token 提权）。

    规则：
    1. 密钥为空（或未配置）→ 任何环境都拒绝；
    2. 命中 WEAK_JWT_SECRETS 黑名单 → 任何环境都拒绝（含开发环境）；
    3. 生产环境（debug=false）另要求长度 >= MIN_PROD_JWT_SECRET_LENGTH（32）；
       开发环境放宽长度限制，避免打断本地开发。

    Args:
        secret: 待校验的 JWT 密钥。
        debug: 是否处于调试（开发）模式。

    Raises:
        ValueError: 密钥缺失、命中黑名单，或生产环境长度不足。
    """
    secret = (secret or "").strip()

    if not secret:
        raise ValueError(
            f"JWT_SECRET_KEY 未配置或为空。请用以下命令生成强密钥：{_SECRET_GEN_HINT}"
        )

    if secret.lower() in WEAK_JWT_SECRETS:
        raise ValueError(
            f"JWT_SECRET_KEY 命中弱密钥黑名单（该值可被攻击者猜到并自签 token，"
            f"导致认证绕过与提权）。请立即轮换，用以下命令生成强密钥：{_SECRET_GEN_HINT}"
        )

    if not debug and len(secret) < MIN_PROD_JWT_SECRET_LENGTH:
        raise ValueError(
            f"生产环境（DEBUG=false）的 JWT_SECRET_KEY 长度不足 {MIN_PROD_JWT_SECRET_LENGTH} 字符"
            f"（当前 {len(secret)} 字符，熵值过低可被暴力破解）。"
            f"请用以下命令生成强密钥：{_SECRET_GEN_HINT}"
        )


def validate_settings() -> None:
    """Validate critical settings on startup.

    JWT secret key must be explicitly set regardless of debug mode.
    Set TESTING=true to skip validation (e.g. unit tests).
    """
    if os.environ.get("TESTING", "").lower() in ("1", "true", "yes"):
        return

    s = get_settings()
    validate_jwt_secret(s.jwt_secret_key, s.debug)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

# Validate on module load (raises if JWT_SECRET_KEY is missing)
validate_settings()
