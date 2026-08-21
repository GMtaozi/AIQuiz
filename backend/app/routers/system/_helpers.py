"""System Router - Shared helpers, constants, and default settings"""

import json
import logging
import re
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting

logger = logging.getLogger(__name__)

# ============ Default Settings ============

DEFAULT_SETTINGS = {
    "system_name": {"value": "AI智能题库管理系统", "type": "string", "description": "系统名称"},
    "system_logo": {"value": "/logo.png", "type": "string", "description": "系统Logo"},
    "announcement": {"value": "欢迎使用AI智能题库管理系统", "type": "string", "description": "系统公告"},
    "login_bg": {"value": "/bg.jpg", "type": "string", "description": "登录页背景"},
    "ai_provider": {"value": "minimax", "type": "string", "description": "AI服务商"},
    "ai_model": {"value": "MiniMax-M2.7", "type": "string", "description": "AI模型"},
    "ai_api_key": {"value": "", "type": "string", "description": "API密钥"},
    "ai_api_url": {"value": "", "type": "string", "description": "API地址(留空使用默认值)"},
    "ai_timeout": {"value": 120, "type": "number", "description": "超时时间(秒)"},
    "random_question_order": {"value": True, "type": "boolean", "description": "题目随机顺序"},
    "random_option_order": {"value": True, "type": "boolean", "description": "选项随机顺序"},
    "pass_score_ratio": {"value": 0.6, "type": "number", "description": "及格分数比例"},
    "screen_switch_limit": {"value": 5, "type": "number", "description": "切屏次数限制"},
    "exam_time_limit": {"value": 120, "type": "number", "description": "考试时间限制(分钟)"},
    "allow_copy_paste": {"value": False, "type": "boolean", "description": "允许复制粘贴"},
    "login_lock_enabled": {"value": True, "type": "boolean", "description": "登录锁定启用"},
    "login_lock_count": {"value": 5, "type": "number", "description": "登录锁定次数"},
    "login_lock_duration": {"value": 30, "type": "number", "description": "登录锁定时长(分钟)"},
    "password_strength_enabled": {"value": True, "type": "boolean", "description": "密码强度检查"},
    "password_require_uppercase": {"value": True, "type": "boolean", "description": "密码必须包含大写字母"},
    "password_require_lowercase": {"value": True, "type": "boolean", "description": "密码必须包含小写字母"},
    "password_require_digit": {"value": True, "type": "boolean", "description": "密码必须包含数字"},
    "password_require_special": {"value": False, "type": "boolean", "description": "密码必须包含特殊字符"},
    "session_timeout": {"value": 120, "type": "number", "description": "会话超时(分钟)"},
    "operation_log_enabled": {"value": True, "type": "boolean", "description": "操作日志"},
    "role_1_permissions": {
        "value": [
            "ai-question",
            "audit",
            "auto-paper",
            "question-bank",
            "paper-management",
            "knowledge",
            "knowledge-bases",
            "settings",
            "user-permission",
        ],
        "type": "json",
        "description": "管理员权限",
    },
    "role_2_permissions": {
        "value": [
            "ai-question",
            "audit",
            "auto-paper",
            "question-bank",
            "paper-management",
            "knowledge",
            "knowledge-bases",
        ],
        "type": "json",
        "description": "题库编辑权限",
    },
    "role_3_permissions": {"value": ["audit", "question-bank"], "type": "json", "description": "审核员权限"},
}

# ============ AI Providers ============

AI_PROVIDERS_LIST = {
    # ==================== 国内厂商 ====================
    "doubao": {
        "key": "doubao",
        "name": "豆包 (字节跳动)",
        "models": ["doubao-seed-2.1-pro", "doubao-seed-2.1-turbo"],
        "default_model": "doubao-seed-2.1-pro",
        "default_api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "qwen": {
        "key": "qwen",
        "name": "通义千问 (阿里云)",
        "models": ["qwen3.8-max", "qwen3.7-plus"],
        "default_model": "qwen3.7-plus",
        "default_api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "deepseek": {
        "key": "deepseek",
        "name": "DeepSeek (深度求索)",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-r1"],
        "default_model": "deepseek-v4-pro",
        "default_api_url": "https://api.deepseek.com/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "moonshot": {
        "key": "moonshot",
        "name": "Kimi (月之暗面)",
        "models": ["kimi-k3"],
        "default_model": "kimi-k3",
        "default_api_url": "https://api.moonshot.cn/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "mimo": {
        "key": "mimo",
        "name": "MiMo (小米)",
        "models": ["mimo-v2.5-pro", "mimo-v2.5"],
        "default_model": "mimo-v2.5-pro",
        "default_api_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "stepfun": {
        "key": "stepfun",
        "name": "阶跃星辰 (StepFun)",
        "models": ["step-3.7-flash"],
        "default_model": "step-3.7-flash",
        "default_api_url": "https://api.stepfun.com/step_plan/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "zhipu": {
        "key": "zhipu",
        "name": "智谱AI (GLM)",
        "models": ["glm-5.2-max", "glm-5.2-vl"],
        "default_model": "glm-5.2-max",
        "default_api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "minimax": {
        "key": "minimax",
        "name": "MiniMax",
        "models": ["MiniMax-M3"],
        "default_model": "MiniMax-M3",
        "default_api_url": "https://api.minimaxi.com/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    # ==================== 国外厂商 ====================
    "openai": {
        "key": "openai",
        "name": "ChatGPT (OpenAI)",
        "models": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
        "default_model": "gpt-5.6-sol",
        "default_api_url": "https://api.openai.com/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
    "anthropic": {
        "key": "anthropic",
        "name": "Claude (Anthropic)",
        "models": ["claude-opus-5.0", "claude-sonnet-5"],
        "default_model": "claude-sonnet-5",
        "default_api_url": "https://api.anthropic.com/v1/messages",
        "protocol": "anthropic_compatible",
        "supports_streaming": True,
    },
    "gemini": {
        "key": "gemini",
        "name": "Gemini (Google)",
        "models": ["gemini-3.6-flash", "gemini-3.1-pro"],
        "default_model": "gemini-3.6-flash",
        "default_api_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "protocol": "gemini_compatible",
        "supports_streaming": True,
    },
    "grok": {
        "key": "grok",
        "name": "Grok (xAI)",
        "models": ["grok-4.3"],
        "default_model": "grok-4.3",
        "default_api_url": "https://api.x.ai/v1/chat/completions",
        "protocol": "openai_compatible",
        "supports_streaming": True,
    },
}

# ============ Helper Functions ============


def get_setting_from_db(db: Session, key: str) -> Any:
    """从数据库获取单个设置值"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting:
        if setting.type == "json":
            try:
                return json.loads(setting.value) if setting.value else []
            except:
                return []
        elif setting.type == "boolean":
            return setting.value == "true" or setting.value == True
        elif setting.type == "number":
            try:
                return int(setting.value) if setting.value else 0
            except:
                try:
                    return float(setting.value) if setting.value else 0.0
                except:
                    return 0
        return setting.value
    # 返回默认值
    if key in DEFAULT_SETTINGS:
        return DEFAULT_SETTINGS[key]["value"]
    return None


def init_default_settings(db: Session) -> None:
    """初始化默认设置到数据库"""
    for key, config in DEFAULT_SETTINGS.items():
        existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not existing:
            value = config["value"]
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            elif isinstance(value, bool):
                value = "true" if value else "false"
            setting = SystemSetting(
                key=key,
                value=str(value) if not isinstance(value, str) else value,
                type=config["type"],
                description=config.get("description", ""),
            )
            db.add(setting)
    db.commit()


def _validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets complexity requirements from settings."""
    from app.services.settings_service import get_security_settings

    settings = get_security_settings()
    if not settings.get("password_strength_enabled", True):
        return True, ""

    if not re.search(r"[A-Z]", password) and settings.get("password_require_uppercase", True):
        return False, "密码必须包含大写字母"
    if not re.search(r"[a-z]", password) and settings.get("password_require_lowercase", True):
        return False, "密码必须包含小写字母"
    if not re.search(r"\d", password) and settings.get("password_require_digit", True):
        return False, "密码必须包含数字"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password) and settings.get("password_require_special", False):
        return False, "密码必须包含特殊字符"
    return True, ""


def save_role_permissions(role: int, permissions: List[str], db: Session = None) -> None:
    """保存角色权限配置到数据库"""
    key = f"role_{role}_permissions"
    if db:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = json.dumps(permissions)
            db.commit()
        else:
            new_setting = SystemSetting(
                key=key, value=json.dumps(permissions), type="json", description=f"角色{role}权限"
            )
            db.add(new_setting)
            db.commit()


def get_ai_config() -> Dict[str, Any]:
    """获取当前AI配置（实际读取逻辑在 settings_service，读 DB）。"""
    from app.services.settings_service import get_ai_config as _impl

    return _impl()


def get_role_permissions_config() -> Dict[int, List[str]]:
    """获取所有角色的菜单权限配置（实际读取逻辑在 settings_service，读 DB）。"""
    from app.services.settings_service import get_role_permissions_config as _impl

    return _impl()
