"""Schemas - Paper Version"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class PaperVersionCreate(BaseModel):
    title: str
    description: str | None = None
    change_log: str | None = None


class PaperVersionResponse(BaseModel):
    id: int
    paper_id: int
    version_number: int
    title: str
    description: str | None
    change_log: str | None
    created_by: int | None
    created_at: datetime
    config: dict | None
    questions_snapshot: list | None

    model_config = ConfigDict(from_attributes=True)


class PaperVersionListResponse(BaseModel):
    items: List[PaperVersionResponse]
    total: int
    page: int
    page_size: int


class PaperVersionCompareResponse(BaseModel):
    current: PaperVersionResponse | None
    target: PaperVersionResponse | None
    added_questions: list
    removed_questions: list
    modified_questions: list
    summary: str


class RestoreVersionRequest(BaseModel):
    """空请求体，回滚操作无需额外参数"""
    pass
