"""Question Schemas - Pydantic models for question-related API requests and responses"""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Subject Schemas ---


class SubjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    description: str | None = None
    status: int | None = 1


class SubjectUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    code: str | None = Field(None, max_length=50)
    description: str | None = None
    status: int | None = None


class SubjectResponse(BaseModel):
    id: int
    name: str
    code: str
    description: str | None = None
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Chapter Schemas ---


class ChapterCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    parent_id: int | None = None
    order: int | None = 0
    description: str | None = None
    status: int | None = 1


class ChapterUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    code: str | None = Field(None, max_length=50)
    parent_id: int | None = None
    order: int | None = None
    description: str | None = None
    status: int | None = None


class ChapterResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    code: str
    parent_id: int | None = None
    order: int
    description: str | None = None
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChapterTreeResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    code: str
    parent_id: int | None = None
    order: int
    description: str | None = None
    status: int
    created_at: datetime
    updated_at: datetime
    children: List["ChapterTreeResponse"] = []

    model_config = ConfigDict(from_attributes=True)


# --- Question Option Schemas ---


class QuestionOptionCreate(BaseModel):
    option_label: str = Field(..., max_length=10)
    option_content: str
    is_correct: bool = False
    order: int | None = 0


class QuestionOptionResponse(BaseModel):
    id: int
    question_id: int
    option_label: str
    option_content: str
    is_correct: bool
    order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Question Schemas ---

# Valid question types using Literal for type safety
QuestionType = Literal["single_choice", "multiple_choice", "true_false", "essay"]


class QuestionCreate(BaseModel):
    chapter_id: int | None = None
    subject_id: int
    question_type: QuestionType = Field(..., description="single_choice, multiple_choice, true_false, essay")
    content: str
    answer: str | None = None
    explanation: str | None = None
    difficulty: int = Field(default=1, ge=1, le=5)
    score: float = Field(default=5.0, ge=0)
    is_public: bool = False
    tags: dict | None = None
    meta: dict | None = None
    # created_by is intentionally omitted - always set by server from current_user
    status: int | None = 1
    options: List[QuestionOptionCreate] | None = None
    # 来源标记：ai=AI生成, import=手动导入, system=系统原有（默认）
    source: str | None = "system"
    is_ai_generated: bool | None = False


class QuestionUpdate(BaseModel):
    chapter_id: int | None = None
    subject_id: int | None = None
    question_type: QuestionType | None = None
    content: str | None = None
    answer: str | None = None
    explanation: str | None = None
    difficulty: int | None = Field(None, ge=1, le=5)
    score: float | None = Field(None, ge=0)
    is_public: bool | None = None
    tags: dict | None = None
    meta: dict | None = None
    status: int | None = None
    options: List[QuestionOptionCreate] | None = None
    # created_by intentionally omitted - never updatable by client


class QuestionResponse(BaseModel):
    id: int
    chapter_id: int
    subject_id: int
    question_type: str
    content: str
    answer: str | None = None
    explanation: str | None = None
    difficulty: int
    score: float
    is_public: bool
    tags: dict | None = None
    meta: dict | None = None
    created_by: int | None = None
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionDetailResponse(BaseModel):
    id: int
    chapter_id: int
    subject_id: int
    question_type: str
    content: str
    answer: str | None = None
    explanation: str | None = None
    difficulty: int
    score: float
    is_public: bool
    is_ai_generated: bool = False
    audit_status: str = "pending"
    audit_reason: str | None = None
    tags: dict | None = None
    meta: dict | None = None
    created_by: int | None = None
    status: int
    created_at: datetime
    updated_at: datetime
    audited_at: datetime | None = None
    options: List[QuestionOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- AI Template Schemas ---


class AiTemplateCreate(BaseModel):
    name: str = Field(..., max_length=100)
    template_type: str = Field(..., description="question_generation, grading, explanation")
    prompt_template: str
    variables: dict | None = None
    model: str | None = "abab6.5s-chat"
    config: dict | None = None
    status: str | None = "active"
    created_by: int | None = None


class AiTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    template_type: str | None = None
    prompt_template: str | None = None
    variables: dict | None = None
    model: str | None = None
    config: dict | None = None
    status: str | None = None


class AiTemplateResponse(BaseModel):
    id: int
    name: str
    template_type: str
    prompt_template: str
    variables: dict | None = None
    model: str
    config: dict | None = None
    status: str
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Question generation schemas ---


class GenerateQuestionsRequest(BaseModel):
    subject_id: int | None = None
    subject_name: str | None = None
    chapter_ids: List[int] | None = None
    chapter_names: List[str] | None = None
    knowledge_point_ids: List[int] | None = None
    knowledge_content: str | None = None
    question_types: List[str] | None = None
    count: int = 10
    difficulty: int = 3
    template_id: int | None = None


class GenerateQuestionsResponse(BaseModel):
    success: bool
    questions: List[dict]
    total_generated: int
    rule_count: int
    ai_count: int
    message: str


class HybridGenerateRequest(BaseModel):
    subject_id: int | None = None
    subject_name: str | None = None
    chapter_ids: List[int] | None = None
    chapter_names: List[str] | None = None
    knowledge_point_ids: List[int] | None = None
    knowledge_content: str | None = None
    question_types: List[str] | None = None
    count: int = 10
    difficulty: int = 3
    mode: str = "hybrid"
    template_id: int | None = None


class HybridGenerateResponse(BaseModel):
    success: bool
    questions: List[dict]
    total_generated: int
    rule_count: int
    ai_count: int
    message: str


# --- Async generation task schemas ---


class AsyncGenerateRequest(BaseModel):
    subject_id: int | None = None
    subject_name: str | None = None
    chapter_ids: List[int] | None = None
    chapter_names: List[str] | None = None
    knowledge_point_ids: List[int] | None = None
    knowledge_content: str | None = None
    question_types: List[str] | None = None
    count: int = 10
    difficulty: int = 3
    mode: str = "hybrid"
    template_id: int | None = None


class AsyncTaskResponse(BaseModel):
    task_id: int
    status: str
    message: str


class TaskProgressResponse(BaseModel):
    task_id: int
    status: str
    progress: int
    mode: str
    rule_questions: int = 0
    ai_questions: int = 0
    total_questions: int = 0
    error_message: str = ""
    questions: List[dict] = []


# --- Question CRUD response schemas ---


class QuestionListResponse(BaseModel):
    items: List["QuestionDetailResponse"]
    total: int
    page: int
    page_size: int


class QuestionStatistics(BaseModel):
    total: int
    by_type: dict
    by_difficulty: dict
    by_subject: dict
    by_audit_status: dict
    ai_generated_count: int


# --- Question import/export schemas ---


class ImportResult(BaseModel):
    success_count: int
    fail_count: int
    errors: List[str] = []


class PreviewResult(BaseModel):
    total: int
    single_choice: int = 0
    multiple_choice: int = 0
    true_false: int = 0
    essay: int = 0
    duplicate_count: int = 0
    internal_duplicate_count: int = 0
    unique_count: int = 0
    errors: List[str] = []


# --- Question batch operation schemas ---


class BatchDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100, description="要删除的题目ID列表，最多100个")


class BatchStatusRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100, description="要更新状态的题目ID列表，最多100个")
    status: int = Field(..., description="目标状态：1=启用，0=禁用")


class BatchOperationResponse(BaseModel):
    success_count: int
    fail_count: int
    failed_ids: List[int] = []
    message: str


class SimilarQuestionResponse(BaseModel):
    question_a_id: int
    question_a_content: str
    question_b_id: int
    question_b_content: str
    question_type: str
    similarity_score: float
    similarity_reason: str


class QuestionSimilarityResponse(BaseModel):
    total_checked: int
    similar_pairs_count: int
    similar_pairs: List[SimilarQuestionResponse]
    message: str | None = None
