"""System Router - User management and password reset endpoints"""

from datetime import datetime
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.password_reset import PasswordResetRequest as PasswordResetRequestModel
from app.models.user import User
from app.routers.system._helpers import (
    _validate_password_strength,
    get_role_permissions_config,
)
from app.routers.system.schemas import (
    PasswordResetProcessRequest,
    PasswordResetResponse,
    UserCreate,
    UserPermissionsUpdate,
    UserResponse,
    UserUpdate,
)
from app.routers.system.schemas import (
    PasswordResetRequest as PasswordResetRequestSchema,
)
from app.services.auth import AuthService
from app.utils.security import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Helper ============


def _get_user_permissions(user: User, role_perms: Dict[int, List[str]]) -> List[str]:
    """Get effective permissions for a user."""
    user_perms = user.menu_permissions
    if isinstance(user_perms, dict):
        user_perms = user_perms.get(str(user.role), user_perms.get(user.role, role_perms.get(user.role, [])))
    elif not user_perms:
        user_perms = role_perms.get(user.role, [])
    return user_perms


def _log_operation(current_user: User, message: str) -> None:
    """Log admin operations if enabled."""
    try:
        from app.services.settings_service import get_security_settings

        security_settings = get_security_settings()
        if security_settings.get("operation_log_enabled", True):
            logger.info(f"[操作日志] 管理员 {current_user.username} {message}")
    except Exception:
        pass


# ============ Users ============


@router.get("/users")
def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: int | None = None,
    status: int | None = None,
    keyword: str | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取用户列表"""
    query = db.query(User)

    if role is not None:
        query = query.filter(User.role == role)
    if status is not None:
        query = query.filter(User.status == status)
    if keyword:
        escaped_keyword = keyword.replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            (User.username.ilike(f"%{escaped_keyword}%", escape="\\"))
            | (User.email.ilike(f"%{escaped_keyword}%", escape="\\"))
        )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    role_perms = get_role_permissions_config()

    items = []
    for user in users:
        user_perms = _get_user_permissions(user, role_perms)
        items.append(
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                real_name=None,
                phone=None,
                status=user.status,
                created_at=user.created_at,
                custom_permissions=user_perms,
                last_login=user.last_login,
            )
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/users", status_code=201)
def create_user(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建用户"""
    existing = db.query(User).filter((User.username == data.username) | (User.email == data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    # 验证密码强度
    valid, msg = _validate_password_strength(data.password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    hashed_pw = AuthService.get_password_hash(data.password)

    # 获取该角色的默认权限
    role_perms = get_role_permissions_config()
    default_perms = role_perms.get(data.role, [])

    new_user = User(
        username=data.username,
        email=data.email,
        hashed_password=hashed_pw,
        role=data.role,
        status=1,
        menu_permissions=default_perms,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    _log_operation(current_user, f"创建了用户: username={data.username}, role={data.role}")

    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role,
        real_name=new_user.real_name,
        phone=new_user.phone,
        status=new_user.status,
        created_at=new_user.created_at,
        custom_permissions=new_user.menu_permissions,
        last_login=new_user.last_login,
    )


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if data.email is not None:
        user.email = data.email
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status

    db.commit()
    db.refresh(user)

    update_fields = []
    if data.email is not None:
        update_fields.append(f"邮箱={data.email}")
    if data.role is not None:
        update_fields.append(f"角色={data.role}")
    if data.status is not None:
        update_fields.append(f"状态={'启用' if data.status else '禁用'}")
    _log_operation(current_user, f"更新了用户 user_id={user_id}, 更新内容: {', '.join(update_fields)}")

    # 获取用户实际权限
    role_perms = get_role_permissions_config()
    user_perms = _get_user_permissions(user, role_perms)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        real_name=None,
        phone=None,
        status=user.status,
        created_at=user.created_at,
        custom_permissions=user_perms,
        last_login=user.last_login,
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除用户（软删除 - 设置status=0）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    user.status = 0
    db.commit()
    _log_operation(current_user, f"删除了用户 user_id={user_id}, username={user.username}")

    return {"message": "用户已删除", "id": user_id}


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    data: PasswordResetRequestSchema,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重置用户密码"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    valid, msg = _validate_password_strength(data.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    user.hashed_password = AuthService.get_password_hash(data.new_password)
    db.commit()

    _log_operation(current_user, f"重置了用户 {user.username}(id={user_id}) 的密码")

    return {"message": "密码已重置", "id": user_id}


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    role_perms = get_role_permissions_config()
    user_perms = _get_user_permissions(user, role_perms)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        real_name=None,
        phone=None,
        status=user.status,
        created_at=user.created_at,
        custom_permissions=user_perms,
        last_login=user.last_login,
    )


@router.put("/users/{user_id}/permissions")
def update_user_permissions(
    user_id: int,
    data: UserPermissionsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新用户个性化权限"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if data.custom_permissions is not None:
        user.menu_permissions = data.custom_permissions
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status

    db.commit()

    log_msg = f"更新了用户 {user.username}(id={user_id}) 的权限"
    if data.custom_permissions is not None:
        log_msg += f", 个性化权限={data.custom_permissions}"
    if data.role is not None:
        log_msg += f", 角色={data.role}"
    if data.status is not None:
        log_msg += f", 状态={'启用' if data.status else '禁用'}"
    _log_operation(current_user, log_msg)

    return {
        "message": "用户权限已更新",
        "id": user_id,
        "custom_permissions": user.menu_permissions,
        "role": user.role,
        "status": user.status,
    }


@router.put("/users/batch-role-permissions/{role}")
def batch_update_role_permissions(
    role: int,
    permissions: List[str],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量更新某角色下所有用户的默认权限"""
    if role not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="无效的角色值")

    role_perms = get_role_permissions_config()
    default_perms = role_perms.get(role, [])

    updated_count = 0
    users = db.query(User).filter(User.role == role).all()
    for user in users:
        if not user.menu_permissions or user.menu_permissions == default_perms:
            user.menu_permissions = permissions
            updated_count += 1

    db.commit()
    _log_operation(current_user, f"批量更新了角色{role}的默认权限: {permissions}, 影响了 {updated_count} 个用户")

    return {
        "message": f"已为 {updated_count} 个用户更新权限",
        "role": role,
        "permissions": permissions,
        "updated_count": updated_count,
    }


# ============ Password Reset Requests ============


@router.get("/password-reset-requests")
def get_password_reset_requests(
    status: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取密码重置申请列表（管理员）"""
    query = db.query(PasswordResetRequestModel)
    if status is not None:
        query = query.filter(PasswordResetRequestModel.status == status)
    total = query.count()
    items = (
        query.order_by(PasswordResetRequestModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [PasswordResetResponse.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/password-reset-requests/{request_id}/process")
def process_password_reset_request(
    request_id: int,
    data: PasswordResetProcessRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """处理密码重置申请"""
    reset_request = db.query(PasswordResetRequestModel).filter(PasswordResetRequestModel.id == request_id).first()
    if not reset_request:
        raise HTTPException(status_code=404, detail="申请记录不存在")

    if reset_request.status == 1:
        raise HTTPException(status_code=400, detail="该申请已被处理")

    user = db.query(User).filter(User.username == reset_request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {reset_request.username} 不存在")

    from app.routers.system._helpers import _validate_password_strength

    valid, msg = _validate_password_strength(data.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    user.hashed_password = AuthService.get_password_hash(data.new_password)

    reset_request.status = 1
    reset_request.admin_id = current_user.id
    reset_request.processed_at = datetime.now()

    db.commit()
    _log_operation(current_user, f"处理了密码重置申请 request_id={request_id}, 用户={reset_request.username}")

    return {"message": "密码已重置", "username": reset_request.username}


@router.delete("/password-reset-requests/{request_id}")
def delete_password_reset_request(
    request_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除密码重置申请记录"""
    reset_request = db.query(PasswordResetRequestModel).filter(PasswordResetRequestModel.id == request_id).first()
    if not reset_request:
        raise HTTPException(status_code=404, detail="申请记录不存在")

    db.delete(reset_request)
    db.commit()
    return {"message": "申请记录已删除"}
