"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditQuestionResponse(BaseModel):
    id: int
    content: str
    question_type: str
    difficulty: int
    subject_id: int
    chapter_id: int
    answer: str | None
    explanation: str | None
    is_ai_generated: bool
    audit_status: str
    audit_reason: str | None
    status: int
    created_at: datetime
    options: List[dict] = []

    # 仅管理员可见的字段
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditListResponse(BaseModel):
    items: List[AuditQuestionResponse]
    total: int
    page: int
    page_size: int


class BatchAuditRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)
    reason: str | None = Field(None, max_length=500)


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        if not v or not v.strip():
            raise ValueError("驳回原因不能为空")
        return v.strip()


class AuditLogResponse(BaseModel):
    id: int
    question_id: int
    auditor_id: int | None
    action: str
    old_status: str | None
    new_status: str
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
