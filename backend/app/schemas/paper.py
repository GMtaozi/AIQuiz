"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import PAPER_STATUS_DRAFT, STATUS_MAP_STR_TO_INT, VALID_QUESTION_TYPES


class AutoGeneratePreviewRequest(BaseModel):
    """组卷预览请求"""

    subject_id: int
    knowledge_point_ids: List[int] | None = None
    question_type_config: dict = Field(default_factory=dict)
    difficulty_config: dict = Field(default_factory=dict)
    total_score: float = 100.0

    @field_validator("question_type_config")
    @classmethod
    def validate_question_types(cls, v):
        for qtype in v.keys():
            if qtype not in VALID_QUESTION_TYPES:
                raise ValueError(f"无效的题型: {qtype}")
        return v


class AutoGenerateRequest(BaseModel):
    """智能组卷请求"""

    title: str = Field(..., min_length=1, max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: str | None = None
    template_id: int | None = None
    knowledge_point_ids: List[int] | None = None
    question_type_config: dict = Field(default_factory=dict)  # {"single_choice": 20, "multiple_choice": 10}
    difficulty_config: dict = Field(default_factory=dict)  # {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    total_score: float = Field(default=100.0, ge=0)

    @field_validator("question_type_config")
    @classmethod
    def validate_question_types(cls, v):
        for qtype in v.keys():
            if qtype not in VALID_QUESTION_TYPES:
                raise ValueError(f"无效的题型: {qtype}，有效值为: {VALID_QUESTION_TYPES}")
        for config in v.values():
            # 支持新旧格式: 旧格式 {"single_choice": 20}, 新格式 {"single_choice": {"count": 20, "score": 2}}
            if isinstance(config, dict):
                count = config.get("count", 0)
                if not isinstance(count, (int, float)) or count < 0:
                    raise ValueError("题目数量必须是非负数字")
            else:
                if not isinstance(config, (int, float)) or config < 0:
                    raise ValueError("题目数量必须是非负数字")
        return v

    @field_validator("difficulty_config")
    @classmethod
    def validate_difficulty_config(cls, v):
        valid_difficulties = {"easy", "medium", "hard"}
        for diff in v.keys():
            if diff not in valid_difficulties:
                raise ValueError(f"无效的难度: {diff}，有效值为: {valid_difficulties}")
        for ratio in v.values():
            if not isinstance(ratio, (int, float)) or ratio < 0:
                raise ValueError("难度配置值必须为非负数字")
        return v


class DifficultyDistributionRequest(BaseModel):
    subject_id: int
    question_types: List[str] = []  # 要统计的题型列表
    knowledge_point_ids: List[int] = []  # 知识点ID列表


class DifficultyDistributionResponse(BaseModel):
    total: int = 0
    easy: int = 0
    medium: int = 0
    hard: int = 0
    easy_ratio: float = 0.0  # 可用比例
    medium_ratio: float = 0.0
    hard_ratio: float = 0.0
    suggestions: dict = {}  # 建议的难度分布（每种题型独立）
    by_question_type: dict = {}  # 按题型统计的难度分布


class PaperOutlineRequest(BaseModel):
    """AI 辅助试卷大纲请求"""
    subject_id: int
    knowledge_point_ids: List[int] | None = None
    total_score: float = Field(default=100.0, ge=0)
    total_time: int = Field(default=120, ge=1)
    sections: List[dict] | None = None  # 可选：用户预设的章节结构


class PaperOutlineSection(BaseModel):
    section_name: str
    knowledge_point_ids: List[int]
    question_type: str
    count: int
    score: float


class PaperOutlineResponse(BaseModel):
    subject_id: int
    total_score: float
    total_time: int
    sections: List[PaperOutlineSection]
    suggestions: List[str] = []
    message: str | None = None


class SimilarityCheckRequest(BaseModel):
    """相似度检测请求"""
    paper_id: int
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="相似度阈值，0-1之间")


class SimilarQuestionPair(BaseModel):
    """相似题目对"""
    question_a_id: int
    question_a_content: str
    question_b_id: int
    question_b_content: str
    question_type: str
    knowledge_point_ids: List[int] = []
    similarity_score: float
    similarity_reason: str


class SimilarityCheckResponse(BaseModel):
    paper_id: int
    total_checked: int
    similar_pairs_count: int
    similar_pairs: List[SimilarQuestionPair]
    message: str | None = None


class ExportPaperRequest(BaseModel):
    paper_id: int
    format: str = "word"


class FixedQuestionItem(BaseModel):
    question_id: int
    order: int = 0
    score: float = Field(..., ge=0)


class RandomSelectionRules(BaseModel):
    """Rules for random question selection."""

    chapter_ids: List[int] | None = None
    question_types: List[str] | None = None
    difficulties: List[int] | None = None
    count_per_type: dict[str, int] | None = None
    total_count: int = Field(..., ge=1)


class PaperCreateFixed(BaseModel):
    """Create a fixed paper with explicitly selected questions."""

    title: str = Field(..., max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: str | None = None
    questions: List[FixedQuestionItem] = Field(..., min_length=1)


class PaperCreateRandom(BaseModel):
    """Create a random paper with question selection rules."""

    title: str = Field(..., max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: str | None = None
    rules: RandomSelectionRules


class PaperCreateUnion(BaseModel):
    """Union type for paper creation - fixed or random."""

    paper_type: int = Field(..., description="1=fixed, 2=random")
    title: str = Field(..., max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: str | None = None
    # For fixed paper
    questions: List[FixedQuestionItem] | None = None
    # For random paper
    rules: RandomSelectionRules | None = None


class QuestionOptionSimpleResponse(BaseModel):
    id: int
    option_label: str
    option_content: str
    is_correct: bool
    order: int

    model_config = ConfigDict(from_attributes=True)


class QuestionInPaperResponse(BaseModel):
    id: int
    chapter_id: int
    subject_id: int
    question_type: str
    content: str
    difficulty: int
    score: float
    answer: str | None = None
    explanation: str | None = None
    options: List[QuestionOptionSimpleResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ExamPaperQuestionResponse(BaseModel):
    id: int
    question_id: int
    order: int
    score: float
    question: QuestionInPaperResponse

    model_config = ConfigDict(from_attributes=True)


class PaperDetailResponse(BaseModel):
    id: int
    title: str
    subject_id: int
    total_score: float
    total_time: int
    passing_score: float
    description: str | None = None
    config: dict | None = None
    status: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    questions: List[ExamPaperQuestionResponse] = []
    shortage_notice: str | None = None  # 题型短缺提示

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_status_int(cls, paper: ExamPaper) -> PaperDetailResponse:
        status_int = STATUS_MAP_STR_TO_INT.get(paper.status, PAPER_STATUS_DRAFT)
        # 手动转换 ExamPaperQuestion ORM 对象为 ExamPaperQuestionResponse Pydantic 模型
        questions = []
        for epq in paper.exam_paper_questions:
            q = epq.question
            questions.append(
                ExamPaperQuestionResponse(
                    id=epq.id,
                    question_id=epq.question_id,
                    order=epq.order,
                    score=epq.score,
                    question=QuestionInPaperResponse(
                        id=q.id,
                        chapter_id=q.chapter_id,
                        subject_id=q.subject_id,
                        question_type=q.question_type,
                        content=q.content,
                        difficulty=q.difficulty,
                        score=q.score,
                        answer=q.answer,
                        explanation=q.explanation,
                        options=[
                            QuestionOptionSimpleResponse(
                                id=opt.id,
                                option_label=opt.option_label,
                                option_content=opt.option_content,
                                is_correct=opt.is_correct,
                                order=opt.order,
                            )
                            for opt in q.options
                        ]
                        if q.options
                        else [],
                    ),
                )
            )
        return cls(
            id=paper.id,
            title=paper.title,
            subject_id=paper.subject_id,
            total_score=paper.total_score,
            total_time=paper.total_time,
            passing_score=paper.passing_score,
            description=paper.description,
            config=paper.config,
            status=status_int,
            created_by=paper.created_by,
            created_at=paper.created_at,
            updated_at=paper.updated_at,
            questions=questions,
        )


class PaperListResponse(BaseModel):
    items: List[PaperResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaperResponse(BaseModel):
    id: int
    title: str
    subject_id: int
    total_score: float
    total_time: int
    passing_score: float
    description: str | None = None
    config: dict | None = None
    status: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_status_int(cls, paper: ExamPaper) -> PaperResponse:
        status_int = STATUS_MAP_STR_TO_INT.get(paper.status, PAPER_STATUS_DRAFT)
        return cls(
            id=paper.id,
            title=paper.title,
            subject_id=paper.subject_id,
            total_score=paper.total_score,
            total_time=paper.total_time,
            passing_score=paper.passing_score,
            description=paper.description,
            config=paper.config,
            status=status_int,
            created_by=paper.created_by,
            created_at=paper.created_at,
            updated_at=paper.updated_at,
        )


class PaperUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    total_time: int | None = Field(None, ge=1)
    passing_score: float | None = Field(None, ge=0)
    description: str | None = None
    config: dict | None = None
    status: int | None = Field(None, description="0=draft, 1=published, 2=archived")
