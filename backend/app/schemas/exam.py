"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserAnswerCreate(BaseModel):
    question_id: int
    answer_content: str


class UserAnswerResponse(BaseModel):
    id: int
    exam_record_id: int
    question_id: int
    user_id: int
    answer_content: str
    is_correct: bool | None = None
    score: float | None = None
    teacher_feedback: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExamCreate(BaseModel):
    exam_paper_id: int
    subject_id: int
    title: str
    duration: int
    start_time: datetime
    end_time: datetime
    student_ids: List[int] = []


class ExamGradeRequest(BaseModel):
    exam_record_id: int


class ExamGradeResponse(BaseModel):
    exam_record_id: int
    total_score: float
    graded_count: int
    results: List[UserAnswerResponse]


class ExamRecordResponse(BaseModel):
    id: int
    exam_paper_id: int
    user_id: int
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float | None = None
    status: str
    answers: dict | None = None
    meta: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamResponse(BaseModel):
    id: int
    exam_paper_id: int
    title: str
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamUpdate(BaseModel):
    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
