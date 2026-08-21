"""Authentication Service"""

from datetime import datetime, timedelta
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_session_timeout() -> int:
    """Get session timeout in minutes from system settings (read from DB)."""
    try:
        from app.services.settings_service import get_security_settings

        settings_dict = get_security_settings()
        return settings_dict.get("session_timeout", settings.jwt_access_token_expire_minutes)
    except Exception:
        # Fallback to config if system settings not available
        return settings.jwt_access_token_expire_minutes


class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=_get_session_timeout())
        to_encode.update(
            {
                "exp": expire,
                # 评估 P2-18：补全 JWT 标准声明（iss/aud/iat/jti），便于审计与按 jti 吊销
                "iss": "aiquiz",
                "aud": "aiquiz-web",
                "iat": datetime.utcnow(),
                "jti": uuid4().hex,
            }
        )
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> dict:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
