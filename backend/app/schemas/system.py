"""System Router - Pydantic schemas for system-related endpoints"""

from datetime import datetime
import re
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============ Settings Schemas ============


class SettingItem(BaseModel):
    key: str = Field(..., max_length=64)
    value: Any
    type: str = Field(..., pattern="^(string|number|boolean|json)$")
    description: str | None = Field(None, max_length=255)


class SettingsResponse(BaseModel):
    settings: Dict[str, SettingItem]


class SettingUpdateRequest(BaseModel):
    key: str = Field(..., max_length=64)
    value: Any


# ============ Exam Category Schemas ============


class ExamCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)
    status: int = Field(default=1, ge=0, le=1)


class ExamCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    status: int | None = Field(None, ge=0, le=1)


class ExamCategoryResponse(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    status: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============ Exam Type Schemas ============


class ExamTypeCreate(BaseModel):
    category_id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    level: str | None = Field(None, max_length=50)
    description: str | None = Field(None, max_length=500)
    duration: int = Field(default=120, ge=1, le=600)
    total_score: float = Field(default=100.0, ge=0)
    passing_score: float = Field(default=60.0, ge=0)
    question_types: List[str] = Field(default_factory=list)
    status: int = Field(default=1, ge=0, le=1)


class ExamTypeUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    level: str | None = Field(None, max_length=50)
    description: str | None = Field(None, max_length=500)
    duration: int | None = Field(None, ge=1, le=600)
    total_score: float | None = Field(None, ge=0)
    passing_score: float | None = Field(None, ge=0)
    question_types: List[str] | None = None
    status: int | None = Field(None, ge=0, le=1)


class ExamTypeResponse(BaseModel):
    id: int
    category_id: int | None
    subject_id: int | None
    name: str
    code: str
    level: str | None
    description: str | None
    duration: int
    total_score: float
    passing_score: float
    question_types: List[str]
    status: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
            created_at=obj.created_at,
        )


# ============ User Schemas ============


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: int = Field(..., ge=1, le=3)
    real_name: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=20)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少8位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v


class UserUpdate(BaseModel):
    email: str | None = Field(None, max_length=100)
    role: int | None = Field(None, ge=1, le=3)
    real_name: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=20)
    status: int | None = Field(None, ge=0, le=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is None:
            return v
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            raise ValueError("邮箱格式不正确")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: int
    real_name: str | None
    phone: str | None
    status: int
    created_at: datetime
    custom_permissions: Any | None = None
    last_login: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserPermissionsUpdate(BaseModel):
    custom_permissions: List[str] | None = None
    role: int | None = None
    status: int | None = None


# ============ Password Reset Schemas ============


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少8位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v


class PasswordResetResponse(BaseModel):
    id: int
    username: str
    status: int
    admin_id: int | None
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PasswordResetProcessRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少8位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v


# ============ Role Permission Schemas ============


class RolePermissionUpdate(BaseModel):
    role: int = Field(..., ge=1, le=3, description="角色ID (1=管理员, 2=题库编辑, 3=审核员)")
    permissions: List[str] = Field(..., description="权限列表")


class RolePermissionResponse(BaseModel):
    role: int
    permissions: List[str]
    description: str


# ============ AI Config Schemas ============


class AIProviderInfo(BaseModel):
    key: str
    name: str
    models: List[str]
    default_model: str
    default_api_url: str = ""
    protocol: str = "openai_compatible"
    supports_streaming: bool = False


class AIProviderListResponse(BaseModel):
    providers: List[AIProviderInfo]


class AIConfigUpdate(BaseModel):
    provider: str = Field(..., description="服务商key")
    api_key: str | None = Field(None, description="API密钥，留空表示不修改现有密钥")
    api_url: str | None = Field(None, description="API地址，留空使用默认值")
    model: str = Field(..., description="模型名称")
    timeout: int = Field(default=120, ge=10, le=300, description="超时时间(秒)")


class AIConfigResponse(BaseModel):
    provider: str
    model: str
    api_url: str
    timeout: int
    api_key_configured: bool = Field(default=False, description="是否已配置API密钥")
