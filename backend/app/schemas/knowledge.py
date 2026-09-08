"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentKnowledgeImport(BaseModel):
    """单个文档的知识点导入"""

    filename: str
    knowledge_tree: List[dict]


class BatchAnalyzeRequest(BaseModel):
    """批量分析请求"""

    subject_id: int
    category: str = "default"
    category_id: int | None = None
    exam_type: str | None = None
    exam_type_id: int | None = None
    parent_kp_id: int | None = None
    extraction_mode: str = "auto"  # "auto", "rule_only", "ai"
    max_points_per_doc: int = 50


class BatchImportRequest(BaseModel):
    """批量导入请求"""

    subject_id: int | None = None
    category: str = "default"
    category_id: int | None = None
    exam_type: str | None = None
    exam_type_id: int | None = None
    parent_kp_id: int | None = None
    documents: List[DocumentKnowledgeImport]


class AIImportRequest(BaseModel):
    """AI 导入请求"""

    knowledge_points: list
    category: str | None = "default"
    category_id: int | None = None  # 前端传考试种类 ID
    exam_type: str | None = None
    exam_type_id: int | None = None  # 前端传考试科目 ID
    parent_id: int | None = None
    document_name: str | None = None  # 文档名，用于创建文档节点
    knowledge_base_id: int | None = None  # 关联知识库
    entry_id: int | None = None  # 关联知识条目（原文分块）


class KnowledgePointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: int | None = None
    category: str | None = Field(default="default", max_length=50)
    category_id: int | None = None  # 前端传考试种类 ID
    exam_type: str | None = Field(default=None, max_length=50)
    exam_type_id: int | None = None  # 前端传考试科目 ID
    description: str | None = None
    knowledge_base_id: int | None = None  # 关联知识库
    order: int = Field(default=0, ge=0)


class KnowledgePointResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None
    category: str
    exam_type: str | None
    description: str | None
    content_excerpt: str | None = None
    knowledge_base_id: int | None = None
    entry_id: int | None = None
    order: int
    status: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    question_count: int = 0
    children: List[KnowledgePointResponse] = []

    model_config = ConfigDict(from_attributes=True)


class KnowledgePointUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    parent_id: int | None = None
    category: str | None = None
    category_id: int | None = None
    exam_type: str | None = None
    exam_type_id: int | None = None
    description: str | None = None
    order: int | None = Field(None, ge=0)
    status: int | None = Field(None, ge=0, le=1)


class KnowledgeQuestionCountRequest(BaseModel):
    knowledge_ids: List[int] = Field(..., description="知识点ID列表")


class KnowledgeStatistics(BaseModel):
    total: int
    by_category: dict
    by_exam_type: dict
    max_depth: int


class TextbookKnowledgeRequest(BaseModel):
    """基于教材信息生成知识点框架的请求"""

    grade: str = Field(..., min_length=1, max_length=50, description="年级，如初中七年级、高中一年级")
    subject: str = Field(..., min_length=1, max_length=50, description="学科，如历史、数学、语文")
    version: str = Field(default="人教版", max_length=50, description="教材版本")
    chapter: str | None = Field(default=None, max_length=100, description="可选：具体章节")
    max_points: int = Field(default=80, ge=1, le=200, description="最大知识点数量")


class TextbookKnowledgeResponse(BaseModel):
    """基于教材信息生成知识点框架的响应"""

    success: bool
    knowledge_points: list
    total: int
    quality_warnings: list[str] = []
    ria_enabled: bool = True
    validation_enabled: bool = True
