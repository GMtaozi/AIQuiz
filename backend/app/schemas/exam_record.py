"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
import enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExamRecordStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"


class QuestionResponse(BaseModel):
    id: int
    content: str
    question_type: str
    answer: str | None = None
    explanation: str | None = None
    difficulty: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserAnswerDetailResponse(BaseModel):
    id: int
    exam_record_id: int
    question_id: int
    user_id: int
    answer_content: str
    is_correct: bool | None = None
    score: float | None = None
    teacher_feedback: str | None = None
    question: QuestionResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ExamRecordDetailResponse(BaseModel):
    id: int
    exam_paper_id: int
    user_id: int
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float | None = None
    status: ExamRecordStatus
    answers: dict | None = None
    user_answers: List[UserAnswerDetailResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ExamRecordListResponse(BaseModel):
    id: int
    exam_paper_id: int
    user_id: int
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float | None = None
    status: ExamRecordStatus
    answers: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class ExamRecordStatsResponse(BaseModel):
    average_score: float | None = None
    max_score: float | None = None
    min_score: float | None = None
    pass_rate: float | None = None
    total_count: int = 0
    graded_count: int = 0
