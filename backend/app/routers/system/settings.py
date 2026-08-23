"""System Router - Settings, AI config, and role permissions endpoints"""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.routers.system._helpers import (
    AI_PROVIDERS_LIST,
    DEFAULT_SETTINGS,
    get_setting_from_db,
    init_default_settings,
    save_role_permissions,
)
from app.routers.system.schemas import (
    AIConfigResponse,
    AIConfigUpdate,
    AIProviderInfo,
    AIProviderListResponse,
    RolePermissionResponse,
    RolePermissionUpdate,
    SettingItem,
    SettingsResponse,
    SettingUpdateRequest,
)
from app.services.settings_service import get_role_permissions_config
from app.utils.security import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Sensitive-value masking ============
# 安全修复（评估 P0-12）：API Key / 密钥类设置不允许明文回显给任意登录用户。

SENSITIVE_SETTING_KEYS = ("api_key", "secret", "password", "token")


def _mask_sensitive_value(key: str, value: Any) -> Any:
    """密钥类设置掩码返回：值非空时只回显 '****'，避免明文泄露。

    仅按 key 名称判断，不影响其他类型设置（如开关、文案等）。
    """
    if value in (None, ""):
        return value
    lowered = str(key).lower()
    if any(s in lowered for s in SENSITIVE_SETTING_KEYS):
        return "****"
    return value


# ============ System Settings ============


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取系统设置"""
    init_default_settings(db)

    settings = {}
    for key in DEFAULT_SETTINGS.keys():
        value = get_setting_from_db(db, key)
        settings[key] = SettingItem(
            key=key,
            value=_mask_sensitive_value(key, value),
            type=DEFAULT_SETTINGS[key].get("type", "string"),
            description=DEFAULT_SETTINGS[key].get("description", ""),
        )
    return {"settings": settings}


@router.put("/settings")
def update_settings(
    data: List[SettingUpdateRequest],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量更新系统设置"""
    updated_count = 0
    for item in data:
        setting = db.query(SystemSetting).filter(SystemSetting.key == item.key).first()
        if setting:
            setting.value = str(item.value) if item.value is not None else ""
            updated_count += 1
        else:
            setting_type = DEFAULT_SETTINGS.get(item.key, {}).get("type", "string")
            new_setting = SystemSetting(
                key=item.key, value=str(item.value) if item.value is not None else "", type=setting_type
            )
            db.add(new_setting)
            updated_count += 1

    db.commit()
    from app.services.settings_service import invalidate_cache

    invalidate_cache()
    return {"message": "设置已更新", "updated": updated_count}


@router.get("/settings/{key}")
def get_setting_by_key(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个设置项"""
    init_default_settings(db)
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="设置项不存在")

    result = {
        "key": setting.key,
        "value": _mask_sensitive_value(setting.key, setting.value),
        "type": setting.type,
        "description": setting.description,
    }
    return result


@router.put("/settings/{key}")
def update_setting_by_key(
    key: str,
    value: Any,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新单个设置项"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="设置项不存在")

    setting.value = str(value) if value is not None else ""
    db.commit()
    return {"message": "设置已更新", "key": key, "value": _mask_sensitive_value(key, value)}


# ============ AI Configuration ============


@router.get("/ai-providers", response_model=AIProviderListResponse)
def get_ai_providers(
    current_user: User = Depends(get_current_user),
):
    """获取支持的AI服务商列表"""
    providers = []
    for key, info in AI_PROVIDERS_LIST.items():
        providers.append(
            AIProviderInfo(
                key=info["key"],
                name=info["name"],
                models=info["models"],
                default_model=info["default_model"],
                default_api_url=info.get("default_api_url", ""),
                protocol=info.get("protocol", "openai_compatible"),
                supports_streaming=info.get("supports_streaming", False),
            )
        )
    return {"providers": providers}


@router.get("/ai-config", response_model=AIConfigResponse)
def get_ai_config_api(
    current_user: User = Depends(get_current_user),
):
    """获取当前AI配置"""
    from app.routers.system._helpers import get_ai_config as _get_ai_config

    config = _get_ai_config()
    api_key = config.get("api_key", "")
    return AIConfigResponse(
        provider=config["provider"],
        model=config["model"],
        api_url=config["api_url"] or "",
        timeout=config["timeout"],
        api_key_configured=bool(api_key and api_key != "****"),
    )


@router.put("/ai-config")
def update_ai_config(
    config: AIConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新AI配置"""
    # 验证服务商是否有效
    if config.provider not in AI_PROVIDERS_LIST:
        raise HTTPException(status_code=400, detail=f"不支持的AI服务商: {config.provider}")

    # 验证模型是否有效
    valid_models = AI_PROVIDERS_LIST[config.provider]["models"]
    if config.model not in valid_models:
        raise HTTPException(status_code=400, detail=f"无效的模型: {config.model}，可选: {', '.join(valid_models)}")

    # 获取现有配置，用于保留未修改的字段
    from app.routers.system._helpers import get_ai_config as _get_ai_config
    existing_config = _get_ai_config()

    # 构建更新字典，未传入的字段保留原值
    ai_config_keys = {
        "ai_provider": config.provider,
        "ai_model": config.model,
        "ai_api_key": config.api_key if config.api_key is not None else existing_config.get("api_key", ""),
        "ai_api_url": config.api_url if config.api_url is not None else existing_config.get("api_url", ""),
        "ai_timeout": config.timeout,
    }

    for key, value in ai_config_keys.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = str(value)
            if key == "ai_timeout":
                setting.value = str(value)
        else:
            new_setting = SystemSetting(
                key=key,
                value=str(value),
                type="string" if key != "ai_timeout" else "number",
                description=f"AI配置 - {key}",
            )
            db.add(new_setting)
    db.commit()

    # 重新加载AI服务提供者的配置
    try:
        from app.services.ai_provider import reload_ai_provider
        from app.services.settings_service import invalidate_cache

        invalidate_cache()
        reload_ai_provider()
    except ImportError:
        pass

    logger.info(
        f"[操作日志] 管理员 {current_user.id}({current_user.username}) 更新了AI配置: 服务商={config.provider}, 模型={config.model}"
    )

    return {"message": "AI配置已更新", "provider": config.provider, "model": config.model}


@router.post("/ai-config/test")
def test_ai_connection(
    config: AIConfigUpdate,
    current_user: User = Depends(require_admin),
):
    """测试AI连接（使用前端传入的配置，不依赖DB保存值）"""
    try:
        import asyncio

        from app.services.ai_provider import AIProvider

        async def _test():
            # 若前端未传入 api_key，则让 AIProvider 从系统设置加载
            provider_kwargs = {
                "provider_key": config.provider,
                "api_url": config.api_url,
                "model": config.model,
                "timeout": config.timeout,
            }
            if config.api_key:
                provider_kwargs["api_key"] = config.api_key
            provider = AIProvider(**provider_kwargs)
            return await provider.test_connection()

        result = asyncio.run(_test())
        return result
    except ImportError:
        return {"success": False, "message": "AI服务模块未正确加载"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {e!s}"}


# ============ Role Permissions ============


@router.get("/role-permissions", response_model=List[RolePermissionResponse])
def get_role_permissions(
    current_user: User = Depends(get_current_user),
):
    """获取所有角色的菜单权限配置"""
    role_perms = get_role_permissions_config()
    role_descriptions = {1: "管理员", 2: "题库编辑", 3: "审核员"}
    return [
        RolePermissionResponse(role=role, permissions=perms, description=role_descriptions.get(role, ""))
        for role, perms in role_perms.items()
    ]


@router.put("/role-permissions/{role}")
def update_role_permissions(
    role: int,
    data: RolePermissionUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新指定角色的菜单权限配置"""
    if role < 1 or role > 3:
        raise HTTPException(status_code=400, detail="无效的角色ID")

    save_role_permissions(role, data.permissions, db)
    logger.info(f"[操作日志] 管理员 {current_user.username} 更新了角色{role}的权限: {data.permissions}")
    from app.services.settings_service import invalidate_cache

    invalidate_cache()

    return {"message": "权限配置已更新", "role": role, "permissions": data.permissions}
