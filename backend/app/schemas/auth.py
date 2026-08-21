"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ForgotPasswordRequest(BaseModel):
    username: str = Field(..., description="用户名")


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
