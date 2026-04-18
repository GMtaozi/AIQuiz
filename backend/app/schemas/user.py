"""User Schemas"""
import re
from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: int = 3

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password meets complexity requirements."""
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        if len(v) > 128:
            raise ValueError('密码长度不能超过128位')
        if not re.search(r'[A-Z]', v):
            raise ValueError('密码必须包含大写字母')
        if not re.search(r'[a-z]', v):
            raise ValueError('密码必须包含小写字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None