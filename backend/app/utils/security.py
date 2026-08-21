"""Security Utilities - JWT Token Verification"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UserRole
from app.database import get_db
from app.models import User

security = HTTPBearer()


def verify_token(token: str) -> dict:
    """Verify JWT token with strict algorithm checking."""
    try:
        # Explicitly specify allowed algorithms only
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],  # Must match exactly, no other algorithms
            audience="aiquiz-web",  # 与 create_access_token 的 aud 声明匹配（评估 P2-18）
            options={
                "require": ["exp", "sub"],
                "verify_exp": True,
                "verify_sub": True,
            },
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Extract and validate current user from JWT token.

    评估 P1-4：优先读取 httpOnly cookie 中的 access_token（前端 JS 无法窃取），
    其次兼容 Authorization Bearer 头（渐进迁移期）。"""
    auth_header = request.headers.get("Authorization")
    token = None

    # 1) httpOnly cookie（安全首选）
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        token = cookie_token

    # 2) Authorization Bearer 头（向后兼容）
    if not token and auth_header:
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = auth_header.replace("Bearer ", "")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # 禁用账号（status=0）不允许访问任何接口
    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    return user


def require_teacher_or_admin(user: User = Depends(get_current_user)) -> User:
    """Require user to have teacher/editor (2), admin (1) or auditor (3) role.
    All three roles (admin, editor, auditor) can access most management features.
    """
    if user.role not in [UserRole.ADMIN, UserRole.TEACHER, UserRole.STUDENT]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员、题库编辑或审核员权限",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require user to have admin (1) role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


# 默认角色权限配置
DEFAULT_ROLE_PERMISSIONS = {
    1: [
        "ai-question",
        "audit",
        "auto-paper",
        "question-bank",
        "paper-management",
        "knowledge",
        "settings",
        "user-permission",
    ],
    2: ["ai-question", "audit", "auto-paper", "question-bank", "paper-management", "knowledge"],
    3: ["audit", "question-bank"],
}


def require_permission(permission: str):
    """Require user to have specific menu permission."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        # 获取用户实际权限
        user_perms = user.menu_permissions
        effective_perms = []

        if user_perms is None:
            # 如果没有个性化权限，使用角色默认权限
            effective_perms = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
        elif isinstance(user_perms, dict):
            # menu_permissions 是按角色分类的字典
            effective_perms = user_perms.get(str(user.role), user_perms.get(user.role, []))
        elif isinstance(user_perms, list):
            # 已经是权限列表
            effective_perms = user_perms

        if permission not in effective_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问该功能",
            )
        return user

    return dependency
