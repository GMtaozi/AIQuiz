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


def require_editor_or_admin(user: User = Depends(get_current_user)) -> User:
    """Require editor/teacher (2) or admin (1) role.

    管理端功能（出题/审核/组卷/题库等）的准入依赖。
    学生（role=3）不在此列——其考试相关接口走 get_current_user + 名单归属校验。

    历史名 require_teacher_or_admin 曾放行 role=3（当时语义为"审核员"）；
    role=3 语义已定为"学生"（商业化决策），本依赖随之收窄。
    """
    if user.role not in [UserRole.ADMIN, UserRole.TEACHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员或教师权限",
        )
    return user


# 兼容别名：历史路由大量引用旧名，逐步替换后移除
require_teacher_or_admin = require_editor_or_admin


def require_license_feature(feature: str):
    """商业化授权门控：增值特性需有效 License 或未过期的试用。

    用法: Depends(require_license_feature("ai_question"))
    试用期内全特性放行；正式授权看签名中的 features；均不满足 → 403。
    """
    from app.services.license_service import license_service

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not license_service.feature_enabled(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"功能「{feature}」需要有效的商业授权（当前授权不可用或已过期），请联系供应商",
            )
        return user

    return dependency


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require user to have admin (1) role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


def require_permission(permission: str):
    """Require user to have specific menu permission.

    权限判定唯一来源：models.user.ROLE_DEFAULT_PERMISSIONS（角色默认）
    + 用户个性化 menu_permissions（优先）。
    """
    from app.models.user import ROLE_DEFAULT_PERMISSIONS

    def dependency(user: User = Depends(get_current_user)) -> User:
        # 获取用户实际权限
        user_perms = user.menu_permissions
        effective_perms = []

        if user_perms is None:
            # 存量数据：无个性化权限时回退角色默认
            effective_perms = ROLE_DEFAULT_PERMISSIONS.get(user.role, [])
        elif isinstance(user_perms, dict):
            # menu_permissions 是按角色分类的字典（历史形态）
            effective_perms = user_perms.get(str(user.role), user_perms.get(user.role, []))
        elif isinstance(user_perms, list):
            # 已经是权限列表（新形态，注册用户为 [] 即无任何权限）
            effective_perms = user_perms

        if permission not in effective_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问该功能",
            )
        return user

    return dependency
