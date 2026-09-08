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


# ============ Exam Analysis Schemas ============


class ExamAnalysisQuestionStat(BaseModel):
    """单题分析数据"""

    question_id: int
    order: int = 0
    question_type: str
    content: str = ""
    difficulty: int = 1
    full_score: float = 0.0
    correct_count: int = 0
    total_attempts: int = 0
    correct_rate: float = 0.0
    average_score: float = 0.0
    discrimination: float = 0.0  # 区分度（高分组正确率 - 低分组正确率）


class ExamAnalysisKnowledgePoint(BaseModel):
    """知识点分析数据"""

    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    question_count: int = 0
    total_score: float = 0.0
    average_score_rate: float = 0.0
    mastery_level: str = "unknown"  # excellent / good / average / weak / unknown


class ExamAnalysisScoreDistribution(BaseModel):
    """分数段分布"""

    range_90_100: int = 0
    range_80_89: int = 0
    range_70_79: int = 0
    range_60_69: int = 0
    range_0_59: int = 0


class ExamAnalysisResponse(BaseModel):
    """考试分析报告响应"""

    exam_id: int
    exam_title: str = ""
    total_students: int = 0
    submitted_count: int = 0
    graded_count: int = 0
    average_score: float = 0.0
    max_score: float = 0.0
    min_score: float = 0.0
    standard_deviation: float = 0.0
    pass_rate: float = 0.0
    total_full_score: float = 0.0
    question_stats: List[ExamAnalysisQuestionStat] = []
    knowledge_point_stats: List[ExamAnalysisKnowledgePoint] = []
    score_distribution: ExamAnalysisScoreDistribution = ExamAnalysisScoreDistribution()


# ============ Subjective Grading Schemas ============


class SubjectiveGradeRequest(BaseModel):
    """主观题评分请求"""

    exam_record_id: int
    question_id: int
    score: float = Field(..., ge=0, description="得分（必须 >= 0）")
    feedback: str | None = None


class ExamGradeSubjectiveResponse(BaseModel):
    """主观题评分响应"""

    exam_record_id: int
    question_id: int
    score: float
    feedback: str | None = None
    graded_by: int
    graded_at: datetime
    record_total_score: float
    record_status: str
    all_subjective_graded: bool
