"""Schemas - 知识库（KnowledgeBase）相关 Pydantic 模型"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    subject_id: int | None = None
    category: str = Field(default="default", max_length=50)
    exam_type: str | None = Field(default=None, max_length=50)
    visibility: str = Field(default="private", max_length=20)  # private/shared/public


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    subject_id: int | None = None
    category: str | None = Field(None, max_length=50)
    exam_type: str | None = Field(None, max_length=50)
    visibility: str | None = Field(None, max_length=20)
    status: int | None = Field(None, ge=0, le=1)


class KnowledgeEntryResponse(BaseModel):
    """知识条目响应"""

    id: int
    knowledge_base_id: int
    title: str
    content: str
    order: int
    source_location: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeEntryBriefResponse(BaseModel):
    """知识条目简要响应（列表用，不含 content 全文）"""

    id: int
    knowledge_base_id: int
    title: str
    order: int
    source_location: str | None = None
    content_preview: str = ""  # content 前 200 字预览
    content_length: int = 0

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""

    id: int
    name: str
    description: str | None = None
    subject_id: int | None = None
    category: str
    exam_type: str | None = None
    visibility: str
    source_file: str | None = None
    source_content: str | None = None
    status: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    entries_count: int = 0
    points_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""

    items: List[KnowledgeBaseResponse]
    total: int


class UploadDocumentResponse(BaseModel):
    """文档上传响应"""

    success: bool
    message: str
    source_file: str | None = None
    entries_created: int = 0
    total_chars: int = 0
