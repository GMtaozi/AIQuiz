from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.question import ExamRecord, UserAnswer, Question
from app.utils.security import get_current_user
import enum

router = APIRouter(tags=["exam-records"])


class ExamRecordStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"


# ============ Pydantic Schemas ============

class QuestionResponse(BaseModel):
    id: int
    content: str
    question_type: str
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None

    class Config:
        from_attributes = True


class UserAnswerDetailResponse(BaseModel):
    id: int
    exam_record_id: int
    question_id: int
    user_id: int
    answer_content: str
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    teacher_feedback: Optional[str] = None
    question: Optional[QuestionResponse] = None

    class Config:
        from_attributes = True


class ExamRecordListResponse(BaseModel):
    id: int
    exam_paper_id: int
    user_id: int
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    status: ExamRecordStatus
    answers: Optional[dict] = None

    class Config:
        from_attributes = True


class ExamRecordDetailResponse(BaseModel):
    id: int
    exam_paper_id: int
    user_id: int
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    status: ExamRecordStatus
    answers: Optional[dict] = None
    user_answers: List[UserAnswerDetailResponse] = []

    class Config:
        from_attributes = True


class ExamRecordStatsResponse(BaseModel):
    average_score: Optional[float] = None
    max_score: Optional[float] = None
    min_score: Optional[float] = None
    pass_rate: Optional[float] = None
    total_count: int = 0
    graded_count: int = 0


# ============ Endpoints ============

@router.get("", response_model=List[ExamRecordListResponse])
def list_exam_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ExamRecordStatus] = Query(None, alias="status"),
    exam_paper_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List current user's exam records with pagination.
    Filter by status and/or exam_paper_id.
    """
    query = db.query(ExamRecord).filter(ExamRecord.user_id == current_user.id)

    if status_filter:
        query = query.filter(ExamRecord.status == status_filter.value)
    if exam_paper_id:
        query = query.filter(ExamRecord.exam_paper_id == exam_paper_id)

    records = query.order_by(ExamRecord.started_at.desc()).offset(skip).limit(limit).all()
    return records


@router.get("/stats", response_model=ExamRecordStatsResponse)
def get_exam_record_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics for current user's graded exam records.
    Returns: average_score, max_score, min_score, pass_rate, total_count, graded_count.
    """
    graded_records = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.id,
        ExamRecord.status == ExamRecordStatus.GRADED.value
    ).all()

    graded_count = len(graded_records)
    total_count = db.query(ExamRecord).filter(ExamRecord.user_id == current_user.id).count()

    if graded_count == 0:
        return ExamRecordStatsResponse(
            average_score=None,
            max_score=None,
            min_score=None,
            pass_rate=None,
            total_count=total_count,
            graded_count=0
        )

    scores = [r.score for r in graded_records if r.score is not None]
    if not scores:
        return ExamRecordStatsResponse(
            average_score=None,
            max_score=None,
            min_score=None,
            pass_rate=None,
            total_count=total_count,
            graded_count=graded_count
        )

    average_score = sum(scores) / len(scores)
    max_score = max(scores)
    min_score = min(scores)
    pass_count = sum(1 for s in scores if s >= 60)
    pass_rate = pass_count / len(scores) if scores else None

    return ExamRecordStatsResponse(
        average_score=round(average_score, 2),
        max_score=max_score,
        min_score=min_score,
        pass_rate=round(pass_rate * 100, 2) if pass_rate is not None else None,
        total_count=total_count,
        graded_count=graded_count
    )


@router.get("/{record_id}", response_model=ExamRecordDetailResponse)
def get_exam_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get exam record detail with question info and user's answers.
    """
    record = db.query(ExamRecord).filter(
        ExamRecord.id == record_id,
        ExamRecord.user_id == current_user.id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Exam record not found")

    user_answers = db.query(UserAnswer).filter(
        UserAnswer.exam_record_id == record_id,
        UserAnswer.user_id == current_user.id
    ).all()

    result = ExamRecordDetailResponse(
        id=record.id,
        exam_paper_id=record.exam_paper_id,
        user_id=record.user_id,
        started_at=record.started_at,
        submitted_at=record.submitted_at,
        score=record.score,
        status=record.status,
        answers=record.answers,
        user_answers=[]
    )

    for ua in user_answers:
        question = db.query(Question).filter(Question.id == ua.question_id).first()
        ua_response = UserAnswerDetailResponse(
            id=ua.id,
            exam_record_id=ua.exam_record_id,
            question_id=ua.question_id,
            user_id=ua.user_id,
            answer_content=ua.answer_content,
            is_correct=ua.is_correct,
            score=ua.score,
            teacher_feedback=ua.teacher_feedback,
            question=QuestionResponse.model_validate(question) if question else None
        )
        result.user_answers.append(ua_response)

    return result
