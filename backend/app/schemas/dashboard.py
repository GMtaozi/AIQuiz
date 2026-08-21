"""Schemas - Pydantic models for API requests and responses"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActivityItem(BaseModel):
    id: int
    type: str
    description: str
    user: str
    created_at: datetime


class DifficultyDistribution(BaseModel):
    easy: int
    medium: int
    hard: int


class OverviewStats(BaseModel):
    total_questions: int
    total_papers: int
    total_exams: int
    total_users: int
    today_questions: int
    today_exams: int
    pending_audit: int
    ai_generated: int


class QuestionTypeDistribution(BaseModel):
    single_choice: int
    multiple_choice: int
    true_false: int
    essay: int


class TrendDataPoint(BaseModel):
    date: str
    count: int


class DashboardOverview(BaseModel):
    stats: OverviewStats
    question_trend: List[TrendDataPoint]
    question_type_dist: QuestionTypeDistribution
    difficulty_dist: DifficultyDistribution
    recent_activities: List[ActivityItem]
