"""Authentication Router"""
import re
import time
import logging
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import timedelta
from passlib.hash import bcrypt
from app.models.user import User, ROLE_DEFAULT_PERMISSIONS
from app.models.password_reset import PasswordResetRequest
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth import AuthService
from app.database import get_db
from app.utils.security import get_current_user
from app.routers.system import get_security_settings, get_role_permissions_config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])


# ============ Schema ============

class ForgotPasswordRequest(BaseModel):
    username: str = Field(..., description="用户名")


# ============ Rate Limiting ============

# Rate limiting: track failed attempts by IP/username
# In production, use Redis for distributed rate limiting
_login_failures: dict = defaultdict(list)  # username -> list of timestamps


def _get_login_lock_config() -> tuple[int, int]:
    """Get login lock config from settings: (max_attempts, lockout_duration_seconds)"""
    settings = get_security_settings()
    if not settings.get("login_lock_enabled", True):
        return 0, 0  # Disabled
    max_attempts = settings.get("login_lock_count", 5)
    lockout_duration = settings.get("login_lock_duration", 30) * 60  # Convert minutes to seconds
    return max_attempts, lockout_duration


def _check_rate_limit(username: str) -> None:
    """Check if account is rate limited due to failed attempts."""
    max_attempts, lockout_duration = _get_login_lock_config()
    if max_attempts <= 0:
        return  # Disabled

    now = time.time()
    # Clean old attempts
    _login_failures[username] = [t for t in _login_failures[username] if now - t < lockout_duration]
    if len(_login_failures[username]) >= max_attempts:
        lock_minutes = lockout_duration // 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请{lock_minutes}分钟后再试"
        )


def _record_failure(username: str) -> None:
    """Record a failed login attempt."""
    max_attempts, lockout_duration = _get_login_lock_config()
    if max_attempts <= 0:
        return  # Disabled
    _login_failures[username].append(time.time())


def _record_success(username: str) -> None:
    """Clear failed attempts on successful login."""
    _login_failures.pop(username, None)


def _validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets complexity requirements from settings."""
    settings = get_security_settings()
    if not settings.get("password_strength_enabled", True):
        return True, ""  # Disabled

    if not re.search(r'[A-Z]', password) and settings.get("password_require_uppercase", True):
        return False, "密码必须包含大写字母"
    if not re.search(r'[a-z]', password) and settings.get("password_require_lowercase", True):
        return False, "密码必须包含小写字母"
    if not re.search(r'\d', password) and settings.get("password_require_digit", True):
        return False, "密码必须包含数字"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password) and settings.get("password_require_special", False):
        return False, "密码必须包含特殊字符"
    return True, ""


def _log_operation(user_id: int, operation: str, details: str = ""):
    """Log user operation if operation log is enabled."""
    settings = get_security_settings()
    if settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 用户ID:{user_id} - {operation} - {details}")


@router.post('/register')
def async_register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user - defaults to auditor role (3) with NO permissions."""
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='该邮箱已被注册')

    # Validate password strength
    valid, msg = _validate_password_strength(user.password)
    if not valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=msg)

    hashed_pw = bcrypt.hash(user.password)
    # New users get role=3 (auditor) but NO permissions - admin must assign
    db_user = User(email=user.email, hashed_password=hashed_pw, username=user.name, role=3, menu_permissions=None)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    _log_operation(db_user.id, "用户注册", f"新用户: {db_user.username}")

    # 生成 token 并返回权限信息
    access_token = AuthService.create_access_token({'sub': str(db_user.id), 'role': db_user.role})
    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'role': db_user.role,
        'menu_permissions': None,
        'needs_admin_approval': True  # 标记需要管理员分配完整权限
    }


@router.post('/login')
def async_login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login endpoint with rate limiting - accepts JSON format."""
    _check_rate_limit(credentials.username)

    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not bcrypt.verify(credentials.password, user.hashed_password):
        _record_failure(credentials.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='用户名或密码错误')

    # 检查用户状态
    if user.status != 1:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='账号已被禁用')

    _record_success(credentials.username)
    _log_operation(user.id, "用户登录", f"用户: {user.username}")
    # 获取该角色的权限配置
    role_perms = get_role_permissions_config()
    user_permissions = role_perms.get(user.role, ROLE_DEFAULT_PERMISSIONS.get(user.role, []))
    # Include role in token payload
    access_token = AuthService.create_access_token({'sub': str(user.id), 'role': user.role})
    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'role': user.role,
        'menu_permissions': {user.role: user_permissions}
    }


@router.post('/login/json')
def async_login_json(credentials: UserLogin, db: Session = Depends(get_db)):
    """JSON-based login endpoint (used by frontend) with rate limiting."""
    _check_rate_limit(credentials.username)

    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not bcrypt.verify(credentials.password, user.hashed_password):
        _record_failure(credentials.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='用户名或密码错误')

    # 检查用户状态
    if user.status != 1:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='账号已被禁用')

    _record_success(credentials.username)
    _log_operation(user.id, "用户登录", f"用户: {user.username}")
    # 获取该角色的权限配置
    role_perms = get_role_permissions_config()
    user_permissions = role_perms.get(user.role, ROLE_DEFAULT_PERMISSIONS.get(user.role, []))
    access_token = AuthService.create_access_token({'sub': str(user.id), 'role': user.role})
    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'role': user.role,
        'menu_permissions': {user.role: user_permissions}
    }


@router.post('/forgot-password')
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """忘记密码 - 记录申请到数据库"""
    # 为防止枚举攻击，不在响应中区分用户名是否存在
    # 记录到 password_reset_requests 表供管理员处理
    reset_request = PasswordResetRequest(username=request.username, status=0)
    db.add(reset_request)
    db.commit()
    logger.info(f"[密码重置请求] 用户名: {request.username}")
    return {'message': '如果用户名存在，管理员将重置密码'}


@router.get('/me', response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post('/refresh', response_model=TokenRefreshResponse)
def refresh_token(current_user: User = Depends(get_current_user)):
    """刷新访问令牌"""
    # 获取该角色的权限配置
    role_perms = get_role_permissions_config()
    user_permissions = role_perms.get(current_user.role, ROLE_DEFAULT_PERMISSIONS.get(current_user.role, []))
    access_token = AuthService.create_access_token({'sub': str(current_user.id), 'role': current_user.role})
    return {
        'access_token': access_token,
        'token_type': 'bearer'
    }