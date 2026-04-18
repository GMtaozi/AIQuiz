"""Question Schemas - Pydantic models for question-related API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Literal
from datetime import datetime


# --- Subject Schemas ---

class SubjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    description: Optional[str] = None
    status: Optional[int] = 1


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    status: Optional[int] = None


class SubjectResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    status: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Chapter Schemas ---

class ChapterCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    parent_id: Optional[int] = None
    order: Optional[int] = 0
    description: Optional[str] = None
    status: Optional[int] = 1


class ChapterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[int] = None
    order: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = None


class ChapterResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    code: str
    parent_id: Optional[int] = None
    order: int
    description: Optional[str] = None
    status: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChapterTreeResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    code: str
    parent_id: Optional[int] = None
    order: int
    description: Optional[str] = None
    status: int
    created_at: datetime
    updated_at: datetime
    children: List["ChapterTreeResponse"] = []

    class Config:
        from_attributes = True


# --- Question Option Schemas ---

class QuestionOptionCreate(BaseModel):
    option_label: str = Field(..., max_length=10)
    option_content: str
    is_correct: bool = False
    order: Optional[int] = 0


class QuestionOptionResponse(BaseModel):
    id: int
    question_id: int
    option_label: str
    option_content: str
    is_correct: bool
    order: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Question Schemas ---

# Valid question types using Literal for type safety
QuestionType = Literal["single_choice", "multiple_choice", "true_false", "essay"]

class QuestionCreate(BaseModel):
    chapter_id: int
    subject_id: int
    question_type: QuestionType = Field(..., description="single_choice, multiple_choice, true_false, essay")
    content: str
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: int = Field(default=1, ge=1, le=5)
    score: float = Field(default=5.0, ge=0)
    is_public: bool = False
    tags: Optional[dict] = None
    meta: Optional[dict] = None
    # created_by is intentionally omitted - always set by server from current_user
    status: Optional[int] = 1
    options: Optional[List[QuestionOptionCreate]] = None
    # 来源标记：ai=AI生成, import=手动导入, system=系统原有（默认）
    source: Optional[str] = "system"
    is_ai_generated: Optional[bool] = False


class QuestionUpdate(BaseModel):
    chapter_id: Optional[int] = None
    subject_id: Optional[int] = None
    question_type: Optional[QuestionType] = None
    content: Optional[str] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    score: Optional[float] = Field(None, ge=0)
    is_public: Optional[bool] = None
    tags: Optional[dict] = None
    meta: Optional[dict] = None
    status: Optional[int] = None
    options: Optional[List[QuestionOptionCreate]] = None
    # created_by intentionally omitted - never updatable by client


class QuestionResponse(BaseModel):
    id: int
    chapter_id: int
    subject_id: int
    question_type: str
    content: str
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: int
    score: float
    is_public: bool
    tags: Optional[dict] = None
    meta: Optional[dict] = None
    created_by: Optional[int] = None
    status: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuestionDetailResponse(BaseModel):
    id: int
    chapter_id: int
    subject_id: int
    question_type: str
    content: str
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: int
    score: float
    is_public: bool
    is_ai_generated: bool = False
    audit_status: str = "pending"
    audit_reason: Optional[str] = None
    tags: Optional[dict] = None
    meta: Optional[dict] = None
    created_by: Optional[int] = None
    status: int
    created_at: datetime
    updated_at: datetime
    audited_at: Optional[datetime] = None
    options: List[QuestionOptionResponse] = []

    class Config:
        from_attributes = True


# --- AI Template Schemas ---

class AiTemplateCreate(BaseModel):
    name: str = Field(..., max_length=100)
    template_type: str = Field(..., description="question_generation, grading, explanation")
    prompt_template: str
    variables: Optional[dict] = None
    model: Optional[str] = "abab6.5s-chat"
    config: Optional[dict] = None
    status: Optional[str] = "active"
    created_by: Optional[int] = None


class AiTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    template_type: Optional[str] = None
    prompt_template: Optional[str] = None
    variables: Optional[dict] = None
    model: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[str] = None


class AiTemplateResponse(BaseModel):
    id: int
    name: str
    template_type: str
    prompt_template: str
    variables: Optional[dict] = None
    model: str
    config: Optional[dict] = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True