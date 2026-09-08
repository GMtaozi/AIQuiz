"""Authentication Router"""

from collections import defaultdict
from datetime import timedelta
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from passlib.hash import bcrypt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.password_reset import PasswordResetRequest
from app.models.user import ROLE_DEFAULT_PERMISSIONS, User
from app.routers.system import get_role_permissions_config, get_security_settings
from app.schemas.auth import ForgotPasswordRequest, TokenRefreshResponse
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth import AuthService
from app.services.operation_log_service import OperationAction, ResourceType, log_operation
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])


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
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"登录失败次数过多，请{lock_minutes}分钟后再试"
        )


def _record_failure(username: str) -> None:
    """Record a failed login attempt."""
    max_attempts, _ = _get_login_lock_config()
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

    if not re.search(r"[A-Z]", password) and settings.get("password_require_uppercase", True):
        return False, "密码必须包含大写字母"
    if not re.search(r"[a-z]", password) and settings.get("password_require_lowercase", True):
        return False, "密码必须包含小写字母"
    if not re.search(r"\d", password) and settings.get("password_require_digit", True):
        return False, "密码必须包含数字"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password) and settings.get("password_require_special", False):
        return False, "密码必须包含特殊字符"
    return True, ""


def _log_operation(user_id: int, operation: str, details: str = ""):
    """Log user operation if operation log is enabled."""
    settings = get_security_settings()
    if settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 用户ID:{user_id} - {operation} - {details}")


def _get_effective_permissions(user: User, role_perms: dict) -> list:
    """计算用户的有效权限（评估 P1-6 修复）：

    优先使用用户个性化 menu_permissions；为 None（存量数据）时回退角色默认权限。
    注册用户 menu_permissions=[]（空列表）→ 任何 require_permission 均拒绝，
    直到管理员分配权限，杜绝"自注册即获审核/题库权限"的提权漏洞。
    """
    up = user.menu_permissions
    if up is None:
        return role_perms.get(user.role, ROLE_DEFAULT_PERMISSIONS.get(user.role, []))
    if isinstance(up, dict):
        return up.get(str(user.role), up.get(user.role, []))
    if isinstance(up, list):
        return up
    return []


def _set_auth_cookie(response: JSONResponse, token: str) -> JSONResponse:
    """评估 P1-4：登录成功后设置 httpOnly cookie（前端 JS 无法读取，防 XSS 窃取 token）。

    后端 get_current_user 优先读取该 cookie，其次兼容 Authorization 头（渐进迁移期）。
    P0 修复：secure 不再硬编码 False，改为按环境动态取值（Settings.cookie_secure_flag）——
    生产/非调试环境（DEBUG=false）为 True，cookie 仅通过 HTTPS 传输；
    本地调试与自动化测试为 False。可用环境变量 COOKIE_SECURE 显式覆盖。
    """
    max_age = settings.jwt_access_token_expire_minutes * 60
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_secure_flag,
    )
    return response


@router.post("/register")
def register(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Register a new user - defaults to student role (3) with NO permissions."""
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="该邮箱已被注册")

    # Validate password strength
    valid, msg = _validate_password_strength(user.password)
    if not valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=msg)

    hashed_pw = bcrypt.hash(user.password)
    # 评估 P1-6 修复：新用户 role=3 且 menu_permissions=[]（空列表），
    # require_permission 对空列表拒绝，管理员分配权限前无任何功能可访问。
    # （原实现存 None 会触发 require_permission 的角色默认权限回退，
    #   导致自注册用户即可审核题目、访问题库 —— 权限提权漏洞。）
    db_user = User(email=user.email, hashed_password=hashed_pw, username=user.name, role=3, menu_permissions=[])
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    _log_operation(db_user.id, "用户注册", f"新用户: {db_user.username}")

    # 记录操作日志
    log_operation(
        db=db,
        user=db_user,
        action=OperationAction.REGISTER,
        resource_type=ResourceType.USER,
        resource_id=db_user.id,
        description=f"新用户注册: {db_user.username}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    # 生成 token 并返回权限信息
    access_token = AuthService.create_access_token({"sub": str(db_user.id), "role": db_user.role})
    # 权限单一来源改造：响应统一为扁平数组，前端不再自行解析角色映射
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": db_user.role,
        "menu_permissions": [],
        "needs_admin_approval": True,  # 标记需要管理员分配完整权限
    }


@router.post("/login")
def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Login endpoint with rate limiting - accepts JSON format."""
    _check_rate_limit(credentials.username)

    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not bcrypt.verify(credentials.password, user.hashed_password):
        _record_failure(credentials.username)
        # 记录登录失败
        log_operation(
            db=db,
            user=user if user else User(id=0, username=credentials.username, email="", hashed_password="", role=3),
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            description=f"登录失败: {credentials.username}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failure",
            details={"reason": "用户名或密码错误", "username": credentials.username},
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    # 检查用户状态
    if user.status != 1:
        # 记录登录失败（账号禁用）
        log_operation(
            db=db,
            user=user,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            resource_id=user.id,
            description=f"登录失败(账号禁用): {user.username}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failure",
            details={"reason": "账号已被禁用"},
        )
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    _record_success(credentials.username)
    _log_operation(user.id, "用户登录", f"用户: {user.username}")

    # 记录操作日志
    log_operation(
        db=db,
        user=user,
        action=OperationAction.LOGIN,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        description=f"用户登录: {user.username}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    # 获取该用户的有效权限（个性化 menu_permissions 优先，评估 P1-6）
    role_perms = get_role_permissions_config()
    user_permissions = _get_effective_permissions(user, role_perms)
    # Include role in token payload
    access_token = AuthService.create_access_token({"sub": str(user.id), "role": user.role})
    response = JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "role": user.role,
            "menu_permissions": user_permissions,
        },
    )
    # 评估 P1-4：同时设置 httpOnly cookie
    return _set_auth_cookie(response, access_token)


@router.post("/login/json")
def login_json(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    """JSON-based login endpoint (used by frontend) with rate limiting."""
    _check_rate_limit(credentials.username)

    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not bcrypt.verify(credentials.password, user.hashed_password):
        _record_failure(credentials.username)
        # 记录登录失败
        log_operation(
            db=db,
            user=user if user else User(id=0, username=credentials.username, email="", hashed_password="", role=3),
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            description=f"登录失败: {credentials.username}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failure",
            details={"reason": "用户名或密码错误", "username": credentials.username},
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    # 检查用户状态
    if user.status != 1:
        # 记录登录失败（账号禁用）
        log_operation(
            db=db,
            user=user,
            action=OperationAction.LOGIN,
            resource_type=ResourceType.USER,
            resource_id=user.id,
            description=f"登录失败(账号禁用): {user.username}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failure",
            details={"reason": "账号已被禁用"},
        )
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    _record_success(credentials.username)
    _log_operation(user.id, "用户登录", f"用户: {user.username}")

    # 记录操作日志
    log_operation(
        db=db,
        user=user,
        action=OperationAction.LOGIN,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        description=f"用户登录: {user.username}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    # 与 /login 一致：个性化 menu_permissions 优先，角色默认兜底
    role_perms = get_role_permissions_config()
    user_permissions = _get_effective_permissions(user, role_perms)
    access_token = AuthService.create_access_token({"sub": str(user.id), "role": user.role})
    response = JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "role": user.role,
            "menu_permissions": user_permissions,
        },
    )
    # 评估 P1-4：同时设置 httpOnly cookie
    return _set_auth_cookie(response, access_token)


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """忘记密码 - 记录申请到数据库"""
    # 为防止枚举攻击，不在响应中区分用户名是否存在
    # 记录到 password_reset_requests 表供管理员处理
    reset_request = PasswordResetRequest(username=request.username, status=0)
    db.add(reset_request)
    db.commit()
    logger.info(f"[密码重置请求] 用户名: {request.username}")
    return {"message": "如果用户名存在，管理员将重置密码"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(current_user: User = Depends(get_current_user)):
    """刷新访问令牌（同时刷新 httpOnly cookie）"""
    # 获取该角色的权限配置
    role_perms = get_role_permissions_config()
    user_permissions = _get_effective_permissions(current_user, role_perms)
    access_token = AuthService.create_access_token({"sub": str(current_user.id), "role": current_user.role})
    response = JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "menu_permissions": user_permissions,
        },
    )
    return _set_auth_cookie(response, access_token)


@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """退出登录：清除 httpOnly cookie（评估 P1-4 新增）"""
    # 记录操作日志
    log_operation(
        db=db,
        user=current_user,
        action=OperationAction.LOGOUT,
        resource_type=ResourceType.USER,
        resource_id=current_user.id,
        description=f"用户登出: {current_user.username}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    response = JSONResponse(status_code=200, content={"message": "已退出登录"})
    response.delete_cookie(key="access_token", path="/")
    return response
