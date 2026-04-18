"""System Router - 系统设置模块"""
import json
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models.user import User
from app.models.question import ExamCategory, ExamType, Subject
from app.models.system_setting import SystemSetting
from app.utils.security import get_current_user, require_admin
from passlib.hash import bcrypt


# 默认设置值（用于初始化数据库）
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
    "role_1_permissions": {"value": ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge', 'settings', 'user-permission'], "type": "json", "description": "管理员权限"},
    "role_2_permissions": {"value": ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge'], "type": "json", "description": "题库编辑权限"},
    "role_3_permissions": {"value": ['audit', 'question-bank'], "type": "json", "description": "审核员权限"},
}


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
                description=config.get("description", "")
            )
            db.add(setting)
    db.commit()


def _validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets complexity requirements from settings."""
    settings = get_security_settings()
    if not settings.get("password_strength_enabled", True):
        return True, ""

    if not re.search(r'[A-Z]', password) and settings.get("password_require_uppercase", True):
        return False, "密码必须包含大写字母"
    if not re.search(r'[a-z]', password) and settings.get("password_require_lowercase", True):
        return False, "密码必须包含小写字母"
    if not re.search(r'\d', password) and settings.get("password_require_digit", True):
        return False, "密码必须包含数字"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password) and settings.get("password_require_special", False):
        return False, "密码必须包含特殊字符"
    return True, ""

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])

# ============ Schema ============

class SettingItem(BaseModel):
    key: str = Field(..., max_length=64)
    value: Any
    type: str = Field(..., pattern="^(string|number|boolean|json)$")
    description: Optional[str] = Field(None, max_length=255)


class SettingsResponse(BaseModel):
    settings: Dict[str, SettingItem]


class SettingUpdateRequest(BaseModel):
    key: str = Field(..., max_length=64)
    value: Any


# ============ 考试种类 (ExamCategory) Schemas ============

class ExamCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    status: int = Field(default=1, ge=0, le=1)


class ExamCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[int] = Field(None, ge=0, le=1)


class ExamCategoryResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]
    status: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 考试科目 (ExamType) Schemas ============

class ExamTypeCreate(BaseModel):
    category_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    level: Optional[str] = Field(None, max_length=50)  # 级别：初级、中级、高级
    description: Optional[str] = Field(None, max_length=500)
    duration: int = Field(default=120, ge=1, le=600)
    total_score: float = Field(default=100.0, ge=0)
    passing_score: float = Field(default=60.0, ge=0)
    question_types: List[str] = Field(default_factory=list)
    status: int = Field(default=1, ge=0, le=1)


class ExamTypeUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    level: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    duration: Optional[int] = Field(None, ge=1, le=600)
    total_score: Optional[float] = Field(None, ge=0)
    passing_score: Optional[float] = Field(None, ge=0)
    question_types: Optional[List[str]] = None
    status: Optional[int] = Field(None, ge=0, le=1)


class ExamTypeResponse(BaseModel):
    id: int
    category_id: Optional[int]
    subject_id: Optional[int]  # 对应的科目ID
    name: str
    code: str
    level: Optional[str]
    description: Optional[str]
    duration: int
    total_score: float
    passing_score: float
    question_types: List[str]
    status: int
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_types(cls, obj):
        """Convert ExamType model to response with parsed question_types."""
        import json
        question_types = []
        if obj.question_types:
            try:
                question_types = json.loads(obj.question_types)
            except:
                question_types = []
        return cls(
            id=obj.id,
            category_id=obj.category_id,
            subject_id=obj.subject_id,
            name=obj.name,
            code=obj.code,
            level=obj.level,
            description=obj.description,
            duration=obj.duration,
            total_score=obj.total_score,
            passing_score=obj.passing_score,
            question_types=question_types,
            status=obj.status,
            created_at=obj.created_at
        )


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: int = Field(..., ge=1, le=3)
    real_name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', v):
            raise ValueError('邮箱格式不正确')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        if not re.search(r'[A-Z]', v):
            raise ValueError('密码必须包含大写字母')
        if not re.search(r'[a-z]', v):
            raise ValueError('密码必须包含小写字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=100)
    role: Optional[int] = Field(None, ge=1, le=3)
    real_name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    status: Optional[int] = Field(None, ge=0, le=1)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is None:
            return v
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', v):
            raise ValueError('邮箱格式不正确')
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: int
    real_name: Optional[str]
    phone: Optional[str]
    status: int
    created_at: datetime
    custom_permissions: Optional[Any] = None  # 用户个性化权限（可以是list或dict）
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        if not re.search(r'[A-Z]', v):
            raise ValueError('密码必须包含大写字母')
        if not re.search(r'[a-z]', v):
            raise ValueError('密码必须包含小写字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v


# ============ Mock Data ============

MOCK_SETTINGS: Dict[str, SettingItem] = {
    "system_name": SettingItem(key="system_name", value="AI智能题库管理系统", type="string", description="系统名称"),
    "system_logo": SettingItem(key="system_logo", value="/logo.png", type="string", description="系统Logo"),
    "announcement": SettingItem(key="announcement", value="欢迎使用AI智能题库管理系统", type="string", description="系统公告"),
    "login_bg": SettingItem(key="login_bg", value="/bg.jpg", type="string", description="登录页背景"),
    # AI配置
    "ai_provider": SettingItem(key="ai_provider", value="minimax", type="string", description="AI服务商"),
    "ai_model": SettingItem(key="ai_model", value="MiniMax-M2.7", type="string", description="AI模型"),
    "ai_api_key": SettingItem(key="ai_api_key", value="", type="string", description="API密钥"),
    "ai_api_url": SettingItem(key="ai_api_url", value="", type="string", description="API地址(留空使用默认值)"),
    "ai_timeout": SettingItem(key="ai_timeout", value=120, type="number", description="超时时间(秒)"),
    # 考试规则
    "random_question_order": SettingItem(key="random_question_order", value=True, type="boolean", description="题目随机顺序"),
    "random_option_order": SettingItem(key="random_option_order", value=True, type="boolean", description="选项随机顺序"),
    "allow_review_answer": SettingItem(key="allow_review_answer", value=False, type="boolean", description="允许回看答案"),
    "screen_switch_limit": SettingItem(key="screen_switch_limit", value=5, type="number", description="切屏次数限制"),
    "pass_score_ratio": SettingItem(key="pass_score_ratio", value=0.6, type="number", description="及格分数比例"),
    # 安全设置
    "login_lock_enabled": SettingItem(key="login_lock_enabled", value=True, type="boolean", description="登录失败锁定"),
    "login_lock_count": SettingItem(key="login_lock_count", value=5, type="number", description="登录锁定次数"),
    "login_lock_duration": SettingItem(key="login_lock_duration", value=30, type="number", description="锁定时长(分钟)"),
    "password_strength_enabled": SettingItem(key="password_strength_enabled", value=True, type="boolean", description="密码强度要求"),
    "password_require_uppercase": SettingItem(key="password_require_uppercase", value=True, type="boolean", description="密码必须包含大写字母"),
    "password_require_lowercase": SettingItem(key="password_require_lowercase", value=True, type="boolean", description="密码必须包含小写字母"),
    "password_require_digit": SettingItem(key="password_require_digit", value=True, type="boolean", description="密码必须包含数字"),
    "password_require_special": SettingItem(key="password_require_special", value=False, type="boolean", description="密码必须包含特殊字符"),
    "session_timeout": SettingItem(key="session_timeout", value=120, type="number", description="会话超时(分钟)"),
    "operation_log_enabled": SettingItem(key="operation_log_enabled", value=True, type="boolean", description="操作日志"),
    # 角色权限配置
    "role_1_permissions": SettingItem(key="role_1_permissions", value=['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge', 'settings', 'user-permission'], type="json", description="管理员权限"),
    "role_2_permissions": SettingItem(key="role_2_permissions", value=['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge'], type="json", description="题库编辑权限"),
    "role_3_permissions": SettingItem(key="role_3_permissions", value=['audit', 'question-bank'], type="json", description="审核员权限"),
}


# ============ 角色权限配置 Schema ============

class RolePermissionUpdate(BaseModel):
    role: int = Field(..., ge=1, le=3, description="角色ID (1=管理员, 2=题库编辑, 3=审核员)")
    permissions: List[str] = Field(..., description="权限列表，如 ['ai-question', 'audit']")


class RolePermissionResponse(BaseModel):
    role: int
    permissions: List[str]
    description: str


def get_role_permissions_config() -> Dict[int, List[str]]:
    """获取所有角色的菜单权限配置"""
    return {
        1: DEFAULT_SETTINGS.get("role_1_permissions", {}).get("value", ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge', 'settings', 'user-permission']),
        2: DEFAULT_SETTINGS.get("role_2_permissions", {}).get("value", ['ai-question', 'audit', 'auto-paper', 'question-bank', 'paper-management', 'knowledge']),
        3: DEFAULT_SETTINGS.get("role_3_permissions", {}).get("value", ['audit', 'question-bank']),
    }


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
                key=key,
                value=json.dumps(permissions),
                type="json",
                description=f"角色{role}权限"
            )
            db.add(new_setting)
            db.commit()


# ============ AI服务商配置 Schema ============

class AIProviderInfo(BaseModel):
    """AI服务商信息"""
    key: str
    name: str
    models: List[str]
    default_model: str
    supports_streaming: bool = False


class AIProviderListResponse(BaseModel):
    """AI服务商列表响应"""
    providers: List[AIProviderInfo]


class AIConfigUpdate(BaseModel):
    """AI配置更新请求"""
    provider: str = Field(..., description="服务商key，如 openai, anthropic, zhipu, qwen, minimax, baidu, gemini")
    api_key: str = Field(..., description="API密钥")
    api_url: Optional[str] = Field(None, description="API地址，留空使用默认值")
    model: str = Field(..., description="模型名称")
    timeout: int = Field(default=120, ge=10, le=300, description="超时时间(秒)")


class AIConfigResponse(BaseModel):
    """AI配置响应"""
    provider: str
    model: str
    api_url: str
    timeout: int

# ============ 安全设置访问函数 ============

def get_security_settings() -> Dict[str, Any]:
    """获取当前生效的安全设置（供其他模块使用）"""
    return {
        "login_lock_enabled": DEFAULT_SETTINGS.get("login_lock_enabled", {}).get("value", True),
        "login_lock_count": DEFAULT_SETTINGS.get("login_lock_count", {}).get("value", 5),
        "login_lock_duration": DEFAULT_SETTINGS.get("login_lock_duration", {}).get("value", 30),
        "password_strength_enabled": DEFAULT_SETTINGS.get("password_strength_enabled", {}).get("value", True),
        "password_require_uppercase": DEFAULT_SETTINGS.get("password_require_uppercase", {}).get("value", True),
        "password_require_lowercase": DEFAULT_SETTINGS.get("password_require_lowercase", {}).get("value", True),
        "password_require_digit": DEFAULT_SETTINGS.get("password_require_digit", {}).get("value", True),
        "password_require_special": DEFAULT_SETTINGS.get("password_require_special", {}).get("value", False),
        "session_timeout": DEFAULT_SETTINGS.get("session_timeout", {}).get("value", 120),
        "operation_log_enabled": DEFAULT_SETTINGS.get("operation_log_enabled", {}).get("value", True),
    }


# ============ AI配置访问函数 ============

def get_ai_config() -> Dict[str, Any]:
    """获取当前AI配置（供其他模块使用）"""
    return {
        "provider": DEFAULT_SETTINGS.get("ai_provider", {}).get("value", "minimax"),
        "model": DEFAULT_SETTINGS.get("ai_model", {}).get("value", "MiniMax-M2.7"),
        "api_key": DEFAULT_SETTINGS.get("ai_api_key", {}).get("value", ""),
        "api_url": DEFAULT_SETTINGS.get("ai_api_url", {}).get("value", ""),
        "timeout": DEFAULT_SETTINGS.get("ai_timeout", {}).get("value", 120),
    }


# ============ AI服务商配置 ============

# 支持的AI服务商列表（与 app/services/ai_provider.py 保持一致）
AI_PROVIDERS_LIST = {
    "openai": {
        "key": "openai",
        "name": "OpenAI",
        "models": ["gpt-4o-2024-11-20", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "supports_streaming": True
    },
    "anthropic": {
        "key": "anthropic",
        "name": "Anthropic Claude",
        "models": ["claude-opus-4-20251120", "claude-sonnet-4-20251120", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest", "claude-3-sonnet-latest", "claude-3-haiku-latest"],
        "default_model": "claude-3-5-sonnet-latest",
        "supports_streaming": True
    },
    "zhipu": {
        "key": "zhipu",
        "name": "智谱AI (GLM)",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-long", "glm-4-alltools", "glm-4", "glm-3-turbo"],
        "default_model": "glm-4-flash",
        "supports_streaming": True
    },
    "qwen": {
        "key": "qwen",
        "name": "阿里云 (Qwen)",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-max-long上下文"],
        "default_model": "qwen-plus",
        "supports_streaming": True
    },
    "minimax": {
        "key": "minimax",
        "name": "MiniMax",
        "models": ["MiniMax-M2.7", "abab6.5s-chat", "abab6-chat"],
        "default_model": "MiniMax-M2.7",
        "supports_streaming": True
    },
    "baidu": {
        "key": "baidu",
        "name": "百度文心一言",
        "models": ["ernie-4.0-8k-latest", "ernie-4.0-8k", "ernie-4.0-turbo-8k-latest", "ernie-3.5-8k-latest", "ernie-3.5-8k"],
        "default_model": "ernie-4.0-8k-latest",
        "supports_streaming": False
    },
    "gemini": {
        "key": "gemini",
        "name": "Google Gemini",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b"],
        "default_model": "gemini-1.5-flash",
        "supports_streaming": True
    }
}


# ============ Router ============

@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取系统设置"""
    # 确保默认设置已初始化
    init_default_settings(db)

    settings = {}
    for key in DEFAULT_SETTINGS.keys():
        value = get_setting_from_db(db, key)
        settings[key] = SettingItem(
            key=key,
            value=value,
            type=DEFAULT_SETTINGS[key].get("type", "string"),
            description=DEFAULT_SETTINGS[key].get("description", "")
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
            # 如果设置不存在，创建它
            setting_type = DEFAULT_SETTINGS.get(item.key, {}).get("type", "string")
            new_setting = SystemSetting(
                key=item.key,
                value=str(item.value) if item.value is not None else "",
                type=setting_type
            )
            db.add(new_setting)
            updated_count += 1

    db.commit()
    return {"message": "设置已更新", "updated": updated_count}


# ============ AI配置 API ============

@router.get("/ai-providers", response_model=AIProviderListResponse)
def get_ai_providers(
    current_user: User = Depends(get_current_user),
):
    """获取支持的AI服务商列表"""
    providers = []
    for key, info in AI_PROVIDERS_LIST.items():
        providers.append(AIProviderInfo(
            key=info["key"],
            name=info["name"],
            models=info["models"],
            default_model=info["default_model"],
            supports_streaming=info.get("supports_streaming", False)
        ))
    return {"providers": providers}


@router.get("/ai-config", response_model=AIConfigResponse)
def get_ai_config_api(
    current_user: User = Depends(get_current_user),
):
    """获取当前AI配置"""
    config = get_ai_config()
    return AIConfigResponse(
        provider=config["provider"],
        model=config["model"],
        api_url=config["api_url"] or "",
        timeout=config["timeout"]
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

    # 更新配置到数据库
    ai_config_keys = {
        "ai_provider": config.provider,
        "ai_model": config.model,
        "ai_api_key": config.api_key,
        "ai_api_url": config.api_url or "",
        "ai_timeout": config.timeout
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
                description=f"AI配置 - {key}"
            )
            db.add(new_setting)
    db.commit()

    # 重新加载AI服务提供者的配置
    try:
        from app.services.ai_provider import reload_ai_provider
        reload_ai_provider()
    except ImportError:
        pass

    logger.info(f"[操作日志] 管理员 {current_user.id}({current_user.username}) 更新了AI配置: 服务商={config.provider}, 模型={config.model}")

    return {"message": "AI配置已更新", "provider": config.provider, "model": config.model}


@router.post("/ai-config/test")
def test_ai_connection(
    current_user: User = Depends(require_admin),
):
    """测试AI连接"""
    try:
        from app.services.ai_provider import get_ai_provider
        import asyncio

        async def _test():
            provider = get_ai_provider()
            return await provider.test_connection()

        result = asyncio.run(_test())
        return result
    except ImportError:
        return {"success": False, "message": "AI服务模块未正确加载"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {str(e)}"}


# ============ 角色权限 API ============

@router.get("/role-permissions", response_model=List[RolePermissionResponse])
def get_role_permissions(
    current_user: User = Depends(get_current_user),
):
    """获取所有角色的菜单权限配置"""
    role_perms = get_role_permissions_config()
    role_descriptions = {
        1: "管理员",
        2: "题库编辑",
        3: "审核员"
    }
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

    return {"message": "权限配置已更新", "role": role, "permissions": data.permissions}


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
        "value": setting.value,
        "type": setting.type,
        "description": setting.description
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
    return {"message": "设置已更新", "key": key, "value": value}


# ============ 考试种类 (ExamCategory) ============

@router.get("/exam-categories")
def get_exam_categories(
    status: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取考试种类列表"""
    query = db.query(ExamCategory)
    if status is not None:
        query = query.filter(ExamCategory.status == status)
    categories = query.order_by(ExamCategory.id).all()
    items = [ExamCategoryResponse.model_validate(e) for e in categories]
    return {"items": items, "total": len(items)}


@router.post("/exam-categories", status_code=201)
def create_exam_category(
    data: ExamCategoryCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建考试种类"""
    existing = db.query(ExamCategory).filter(ExamCategory.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="考试种类代码已存在")

    category = ExamCategory(
        name=data.name,
        code=data.code,
        description=data.description,
        status=data.status,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return ExamCategoryResponse.model_validate(category)


@router.put("/exam-categories/{category_id}")
def update_exam_category(
    category_id: int,
    data: ExamCategoryUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新考试种类"""
    category = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="考试种类不存在")

    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.status is not None:
        category.status = data.status

    db.commit()
    db.refresh(category)
    return ExamCategoryResponse.model_validate(category)


@router.delete("/exam-categories/{category_id}")
def delete_exam_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除考试种类"""
    category = db.query(ExamCategory).filter(ExamCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="考试种类不存在")

    db.delete(category)
    db.commit()
    return {"message": "删除成功"}


# ============ 考试科目 (ExamType) ============

@router.get("/exam-types")
def get_exam_types(
    category_id: Optional[int] = None,
    status: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取考试科目列表"""
    query = db.query(ExamType)
    if category_id is not None:
        query = query.filter(ExamType.category_id == category_id)
    if status is not None:
        query = query.filter(ExamType.status == status)
    exam_types = query.order_by(ExamType.id).all()
    items = [ExamTypeResponse.from_orm_with_types(e) for e in exam_types]
    return {"items": items, "total": len(items)}


@router.post("/exam-types", status_code=201)
def create_exam_type(
    data: ExamTypeCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建考试科目（同时创建对应的科目）"""
    import json
    existing = db.query(ExamType).filter(ExamType.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="考试科目代码已存在")

    # 先创建对应的科目
    subject = Subject(
        name=data.name,
        code=data.code,
        description=data.description or None,
        status=1,
    )
    db.add(subject)
    db.flush()  # 获取 subject.id

    exam_type = ExamType(
        category_id=data.category_id,
        subject_id=subject.id,  # 建立关联
        name=data.name,
        code=data.code,
        level=data.level,
        description=data.description,
        duration=data.duration,
        total_score=data.total_score,
        passing_score=data.passing_score,
        question_types=json.dumps(data.question_types) if data.question_types else "[]",
        status=data.status,
    )
    db.add(exam_type)
    db.commit()
    db.refresh(exam_type)
    return ExamTypeResponse.from_orm_with_types(exam_type)


@router.put("/exam-types/{type_id}")
def update_exam_type(
    type_id: int,
    data: ExamTypeUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新考试科目"""
    import json
    exam_type = db.query(ExamType).filter(ExamType.id == type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="考试科目不存在")

    if data.category_id is not None:
        exam_type.category_id = data.category_id
    if data.name is not None:
        exam_type.name = data.name
    if data.level is not None:
        exam_type.level = data.level
    if data.description is not None:
        exam_type.description = data.description
    if data.duration is not None:
        exam_type.duration = data.duration
    if data.total_score is not None:
        exam_type.total_score = data.total_score
    if data.passing_score is not None:
        exam_type.passing_score = data.passing_score
    if data.question_types is not None:
        exam_type.question_types = json.dumps(data.question_types)
    if data.status is not None:
        exam_type.status = data.status

    db.commit()
    db.refresh(exam_type)
    return ExamTypeResponse.from_orm_with_types(exam_type)


@router.delete("/exam-types/{type_id}")
def delete_exam_type(
    type_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除考试科目"""
    exam_type = db.query(ExamType).filter(ExamType.id == type_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="考试科目不存在")

    db.delete(exam_type)
    db.commit()
    return {"message": "删除成功"}


# ============ Users ============

@router.get("/users")
def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: Optional[int] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取用户列表"""
    # 从数据库查询真实用户
    query = db.query(User)

    if role is not None:
        query = query.filter(User.role == role)
    if status is not None:
        query = query.filter(User.status == status)
    if keyword:
        # 转义特殊字符防止SQL注入，使用func.lower() + contains()进行安全搜索
        escaped_keyword = keyword.replace('%', '\\%').replace('_', '\\_')
        query = query.filter(
            (User.username.ilike(f"%{escaped_keyword}%", escape='\\')) |
            (User.email.ilike(f"%{escaped_keyword}%", escape='\\'))
        )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取角色默认权限配置
    role_perms = get_role_permissions_config()

    items = []
    for user in users:
        # 获取用户实际权限：如果有个性化权限（列表格式）则使用，否则使用角色默认权限
        user_perms = user.menu_permissions
        if isinstance(user_perms, dict):
            # menu_permissions 是按角色分类的字典，取用户所属角色的权限
            user_perms = user_perms.get(str(user.role), user_perms.get(user.role, role_perms.get(user.role, [])))
        elif not user_perms:
            # 为空则使用角色默认权限
            user_perms = role_perms.get(user.role, [])

        items.append(UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            real_name=None,
            phone=None,
            status=user.status,
            created_at=user.created_at,
            custom_permissions=user_perms,
            last_login=user.last_login
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/users", status_code=201)
def create_user(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建用户"""
    # 检查用户名和邮箱是否已存在
    existing = db.query(User).filter(
        (User.username == data.username) | (User.email == data.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    # 验证密码强度
    valid, msg = _validate_password_strength(data.password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    hashed_pw = bcrypt.hash(data.password)

    # 获取该角色的默认权限
    role_perms = get_role_permissions_config()
    default_perms = role_perms.get(data.role, [])

    # 创建用户
    new_user = User(
        username=data.username,
        email=data.email,
        hashed_password=hashed_pw,
        role=data.role,
        status=1,
        menu_permissions=default_perms
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 管理员 {current_user.username} 创建了用户: username={data.username}, role={data.role}")

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
        last_login=new_user.last_login
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

    # 更新字段
    if data.email is not None:
        user.email = data.email
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status
    if data.real_name is not None:
        pass  # User model doesn't have real_name field yet
    if data.phone is not None:
        pass  # User model doesn't have phone field yet

    db.commit()
    db.refresh(user)

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        update_fields = []
        if data.email is not None:
            update_fields.append(f"邮箱={data.email}")
        if data.role is not None:
            update_fields.append(f"角色={data.role}")
        if data.status is not None:
            update_fields.append(f"状态={'启用' if data.status else '禁用'}")
        logger.info(f"[操作日志] 管理员 {current_user.username} 更新了用户 user_id={user_id}, 更新内容: {', '.join(update_fields)}")

    # 获取用户实际权限
    role_perms = get_role_permissions_config()
    user_perms = user.menu_permissions
    if isinstance(user_perms, dict):
        user_perms = user_perms.get(str(user.role), user_perms.get(user.role, role_perms.get(user.role, [])))
    elif not user_perms:
        user_perms = role_perms.get(user.role, [])

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
        last_login=user.last_login
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

    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    # 软删除：设置status=0而不是真正删除记录
    user.status = 0
    db.commit()

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 管理员 {current_user.username} 删除了用户 user_id={user_id}, username={user.username}")

    return {"message": "用户已删除", "id": user_id}


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    data: PasswordResetRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重置用户密码"""
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 验证新密码强度
    valid, msg = _validate_password_strength(data.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 更新密码
    user.hashed_password = bcrypt.hash(data.new_password)
    db.commit()

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 管理员 {current_user.username} 重置了用户 {user.username}(id={user_id}) 的密码")

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

    # 获取用户实际权限
    role_perms = get_role_permissions_config()
    user_perms = user.menu_permissions
    if isinstance(user_perms, dict):
        user_perms = user_perms.get(str(user.role), user_perms.get(user.role, role_perms.get(user.role, [])))
    elif not user_perms:
        user_perms = role_perms.get(user.role, [])

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
        last_login=user.last_login
    )


class UserPermissionsUpdate(BaseModel):
    custom_permissions: Optional[List[str]] = None
    role: Optional[int] = None
    status: Optional[int] = None


@router.put("/users/{user_id}/permissions")
def update_user_permissions(
    user_id: int,
    data: UserPermissionsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新用户个性化权限（可覆盖角色默认权限）"""
    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 更新权限
    if data.custom_permissions is not None:
        user.menu_permissions = data.custom_permissions
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status

    db.commit()

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        log_msg = f"[操作日志] 管理员 {current_user.username} 更新了用户 {user.username}(id={user_id}) 的权限"
        if data.custom_permissions is not None:
            log_msg += f", 个性化权限={data.custom_permissions}"
        if data.role is not None:
            log_msg += f", 角色={data.role}"
        if data.status is not None:
            log_msg += f", 状态={'启用' if data.status else '禁用'}"
        logger.info(log_msg)

    return {
        "message": "用户权限已更新",
        "id": user_id,
        "custom_permissions": user.menu_permissions,
        "role": user.role,
        "status": user.status
    }


@router.put("/users/batch-role-permissions/{role}")
def batch_update_role_permissions(
    role: int,
    permissions: List[str],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量更新某角色下所有用户的默认权限（不影响有个性化权限的用户）"""
    if role not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="无效的角色值")

    # 获取该角色的默认权限配置
    role_perms = get_role_permissions_config()
    default_perms = role_perms.get(role, [])

    # 只更新那些使用角色默认权限的用户（custom_permissions为空或等于角色默认值的）
    updated_count = 0
    users = db.query(User).filter(User.role == role).all()
    for user in users:
        # 如果用户的个性化权限为空，才更新为新的角色默认权限
        if not user.menu_permissions or user.menu_permissions == default_perms:
            user.menu_permissions = permissions
            updated_count += 1

    db.commit()

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 管理员 {current_user.username} 批量更新了角色{role}的默认权限: {permissions}, 影响了 {updated_count} 个用户")

    return {
        "message": f"已为 {updated_count} 个用户更新权限",
        "role": role,
        "permissions": permissions,
        "updated_count": updated_count
    }


# ============ 密码重置申请 ============

from app.models.password_reset import PasswordResetRequest as PasswordResetRequestModel


class PasswordResetRequestResponse(BaseModel):
    id: int
    username: str
    status: int  # 0=待处理, 1=已处理
    admin_id: Optional[int]
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PasswordResetProcessRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        if not re.search(r'[A-Z]', v):
            raise ValueError('密码必须包含大写字母')
        if not re.search(r'[a-z]', v):
            raise ValueError('密码必须包含小写字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v


@router.get("/password-reset-requests")
def get_password_reset_requests(
    status: Optional[int] = None,  # 0=待处理, 1=已处理, None=全部
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
    items = query.order_by(PasswordResetRequestModel.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [PasswordResetRequestResponse.model_validate(i) for i in items], "total": total, "page": page, "page_size": page_size}


@router.post("/password-reset-requests/{request_id}/process")
def process_password_reset_request(
    request_id: int,
    data: PasswordResetProcessRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """处理密码重置申请：重置用户密码（管理员）"""
    # 查找申请记录
    reset_request = db.query(PasswordResetRequestModel).filter(PasswordResetRequestModel.id == request_id).first()
    if not reset_request:
        raise HTTPException(status_code=404, detail="申请记录不存在")

    if reset_request.status == 1:
        raise HTTPException(status_code=400, detail="该申请已被处理")

    # 查找目标用户
    user = db.query(User).filter(User.username == reset_request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {reset_request.username} 不存在")

    # 验证新密码强度
    valid, msg = _validate_password_strength(data.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 重置密码
    user.hashed_password = bcrypt.hash(data.new_password)

    # 更新申请状态
    reset_request.status = 1
    reset_request.admin_id = current_user.id
    reset_request.processed_at = datetime.now()

    db.commit()

    # 操作日志
    security_settings = get_security_settings()
    if security_settings.get("operation_log_enabled", True):
        logger.info(f"[操作日志] 管理员 {current_user.username} 处理了密码重置申请 request_id={request_id}, 用户={reset_request.username}")

    return {"message": "密码已重置", "username": reset_request.username}


@router.delete("/password-reset-requests/{request_id}")
def delete_password_reset_request(
    request_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除密码重置申请记录（管理员）"""
    reset_request = db.query(PasswordResetRequestModel).filter(PasswordResetRequestModel.id == request_id).first()
    if not reset_request:
        raise HTTPException(status_code=404, detail="申请记录不存在")

    db.delete(reset_request)
    db.commit()
    return {"message": "申请记录已删除"}
