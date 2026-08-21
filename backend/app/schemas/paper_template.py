"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaperTemplateCreate(BaseModel):
    name: str
    subject_id: int
    description: str | None = None
    config: dict = {}  # 模板配置
    status: int = 1


class PaperTemplateResponse(BaseModel):
    id: int
    name: str
    subject_id: int
    description: str | None
    config: dict
    status: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    total_score: int
    duration: int
    is_public: bool
    rating: float
    usage_count: int

    model_config = ConfigDict(from_attributes=True)


class PaperTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    subject_id: int | None = None
    config: dict | None = None
    status: int | None = None
    is_public: bool | None = None
    shared_with: list | None = None
