"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    content: str
    is_read: bool
    link: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationStats(BaseModel):
    total: int
    unread: int
    pending_audit: int
    ai_tasks_completed: int
    ai_tasks_failed: int
