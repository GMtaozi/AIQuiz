from datetime import datetime
import enum
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import ExamPaper, ExamRecord, Question, QuestionOption, UserAnswer
from app.models.user import User
from app.schemas.exam import (
    ExamCreate,
    ExamGradeRequest,
    ExamGradeResponse,
    ExamRecordResponse,
    ExamResponse,
    ExamUpdate,
    UserAnswerCreate,
    UserAnswerResponse,
)
from app.utils.security import get_current_user, require_teacher_or_admin

router = APIRouter(tags=["exams"])


class ExamStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"  # 1=进行中
    SUBMITTED = "submitted"  # 2=已提交
    GRADED = "graded"  # 3=已批改


# ============ Auto-grade Logic ============

AUTO_GRADABLE_TYPES = {"single_choice", "multiple_choice", "true_false"}


def get_correct_answer(db: Session, question: Question) -> dict | None:
    """Get correct answer for a question."""
    if question.question_type == "single_choice" or question.question_type == "true_false":
        correct_option = (
            db.query(QuestionOption)
            .filter(QuestionOption.question_id == question.id, QuestionOption.is_correct == True)
            .first()
        )
        if correct_option:
            return {"type": question.question_type, "answer": correct_option.option_label}
    elif question.question_type == "multiple_choice":
        correct_options = (
            db.query(QuestionOption)
            .filter(QuestionOption.question_id == question.id, QuestionOption.is_correct == True)
            .all()
        )
        if correct_options:
            return {"type": question.question_type, "answer": sorted([opt.option_label for opt in correct_options])}
    return None


def grade_answer(question: Question, user_answer_content: str, correct_answer: dict) -> tuple[bool, float]:
    """Grade a single answer. Returns (is_correct, score)."""
    if correct_answer is None:
        return False, 0.0

    question_type = correct_answer["type"]
    correct = correct_answer["answer"]

    if question_type == "single_choice" or question_type == "true_false":
        is_correct = user_answer_content.strip().lower() == str(correct).lower()
        return is_correct, float(question.score) if is_correct else 0.0
    elif question_type == "multiple_choice":
        user_answers = sorted([ans.strip() for ans in user_answer_content.split(",")])
        correct_list = correct if isinstance(correct, list) else [correct]
        is_correct = user_answers == sorted(correct_list)
        return is_correct, float(question.score) if is_correct else 0.0

    return False, 0.0


# ============ Endpoints ============


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(
    exam_data: ExamCreate, db: Session = Depends(get_db), current_user: User = Depends(require_teacher_or_admin)
):
    """Create a new exam assignment with paper_id, title, start_time, end_time, and student_ids."""
    # Verify exam paper exists
    exam_paper = db.query(ExamPaper).filter(ExamPaper.id == exam_data.exam_paper_id).first()
    if not exam_paper:
        raise HTTPException(status_code=404, detail="Exam paper not found")

    # Update exam paper with exam metadata
    exam_paper.title = exam_data.title
    exam_paper.subject_id = exam_data.subject_id
    exam_paper.total_time = exam_data.duration
    exam_paper.config = exam_paper.config or {}
    exam_paper.config.update(
        {
            "start_time": exam_data.start_time.isoformat(),
            "end_time": exam_data.end_time.isoformat(),
            "student_ids": exam_data.student_ids,
            "exam_status": "pending",
        }
    )

    # Create ExamRecord entries for each student
    for student_id in exam_data.student_ids:
        exam_record = ExamRecord(
            exam_paper_id=exam_data.exam_paper_id,
            user_id=student_id,
            status="pending",
            meta={
                "start_time": exam_data.start_time.isoformat(),
                "end_time": exam_data.end_time.isoformat(),
            },
        )
        db.add(exam_record)

    db.commit()
    db.refresh(exam_paper)

    return ExamResponse(
        id=exam_paper.id,
        exam_paper_id=exam_paper.id,
        title=exam_data.title,
        start_time=exam_data.start_time,
        end_time=exam_data.end_time,
        status="pending",
        created_at=exam_paper.created_at,
        updated_at=exam_paper.updated_at,
    )


@router.get("", response_model=List[ExamResponse])
def list_exams(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    status: str | None = Query(None, description="考试状态筛选"),
    subject_id: int | None = Query(None, description="按科目筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取考试场次列表"""
    # 查询有考试配置的试卷（config 中包含 exam 相关字段）
    query = db.query(ExamPaper).filter(ExamPaper.config.isnot(None))

    if status:
        query = query.filter(ExamPaper.config["exam_status"].astext == status)
    if subject_id is not None:
        query = query.filter(ExamPaper.subject_id == subject_id)

    exams = query.offset(skip).limit(limit).all()

    results = []
    for exam in exams:
        config = exam.config or {}
        results.append(
            ExamResponse(
                id=exam.id,
                exam_paper_id=exam.id,
                title=config.get("exam_title", exam.title),
                start_time=config.get("start_time"),
                end_time=config.get("end_time"),
                status=config.get("exam_status", "pending"),
                created_at=exam.created_at,
                updated_at=exam.updated_at,
            )
        )

    return results


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取考试场次详情"""
    exam = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试场次不存在")

    config = exam.config or {}
    return ExamResponse(
        id=exam.id,
        exam_paper_id=exam.id,
        title=config.get("exam_title", exam.title),
        start_time=config.get("start_time"),
        end_time=config.get("end_time"),
        status=config.get("exam_status", "pending"),
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


def _check_exam_ownership(exam: ExamPaper, current_user: User) -> None:
    """校验考试归属（评估 P1-10 修复）：管理员或创建者才能修改/删除。"""
    if current_user.role != 1 and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该考试场次")


@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: int,
    exam_data: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新考试场次（教师/管理员）"""
    exam = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试场次不存在")

    _check_exam_ownership(exam, current_user)

    config = exam.config or {}
    if exam_data.title is not None:
        config["exam_title"] = exam_data.title
        exam.title = exam_data.title
    if exam_data.start_time is not None:
        config["start_time"] = exam_data.start_time.isoformat()
    if exam_data.end_time is not None:
        config["end_time"] = exam_data.end_time.isoformat()

    exam.config = config
    db.commit()
    db.refresh(exam)

    return ExamResponse(
        id=exam.id,
        exam_paper_id=exam.id,
        title=config.get("exam_title", exam.title),
        start_time=config.get("start_time"),
        end_time=config.get("end_time"),
        status=config.get("exam_status", "pending"),
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除考试场次（级联删除考试记录）"""
    exam = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试场次不存在")

    _check_exam_ownership(exam, current_user)

    # 删除关联的考试记录
    db.query(ExamRecord).filter(ExamRecord.exam_paper_id == exam_id).delete(synchronize_session=False)
    # 删除考试
    db.delete(exam)
    db.commit()
    return None


@router.post("/{exam_id}/start", response_model=List[ExamRecordResponse], status_code=status.HTTP_201_CREATED)
def start_exam(
    exam_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Student starts exam - creates/updates an ExamRecord.
    exam_id here is the ExamPaper id (the exam assignment id).
    If student_ids provided in body, create records for those students (admin/teacher only).
    Otherwise, create record for current user.
    """
    # exam_id is the ExamPaper id (the exam assignment)
    exam_paper = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not exam_paper:
        raise HTTPException(status_code=404, detail="Exam not found")

    # 评估 P1-12 修复：考生名单与时间窗校验
    config = exam_paper.config or {}
    exam_student_ids = config.get("student_ids")
    if exam_student_ids and current_user.id not in exam_student_ids:
        raise HTTPException(status_code=403, detail="您不在本场考试的考生名单中")
    now_iso = datetime.utcnow().isoformat()
    if config.get("start_time") and now_iso < str(config["start_time"]):
        raise HTTPException(status_code=403, detail="考试尚未开始")
    if config.get("end_time") and now_iso > str(config["end_time"]):
        raise HTTPException(status_code=403, detail="考试已结束")

    # Determine which students to create records for
    student_ids = [current_user.id]

    # Create exam record for each student
    records = []
    for sid in student_ids:
        # Check if record already exists
        existing = (
            db.query(ExamRecord)
            .filter(
                ExamRecord.exam_paper_id == exam_id,
                ExamRecord.user_id == sid,
                ExamRecord.status.in_(["in_progress", "submitted", "graded"]),
            )
            .first()
        )
        if existing:
            records.append(existing)
            continue

        record = ExamRecord(exam_paper_id=exam_id, user_id=sid, started_at=datetime.utcnow(), status="in_progress")
        db.add(record)
        records.append(record)

    db.commit()
    for r in records:
        db.refresh(r)

    return records


@router.post("/{exam_id}/submit", response_model=ExamRecordResponse)
def submit_exam(
    exam_id: int,
    exam_record_id: int,
    answers: List[UserAnswerCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit exam - save user answers and update exam record status to submitted.
    Uses SELECT FOR UPDATE to prevent race conditions and double submission.
    """
    # SECURITY FIX: Use SELECT FOR UPDATE to lock the row and prevent race conditions
    record = (
        db.query(ExamRecord)
        .filter(ExamRecord.id == exam_record_id, ExamRecord.user_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not record:
        raise HTTPException(status_code=404, detail="Exam record not found")

    # Check status AFTER acquiring lock to prevent double submission
    if record.status != "in_progress":
        raise HTTPException(status_code=400, detail="考试已提交，请勿重复提交")

    # 评估 P1-12 修复：校验提交的题目是否属于本试卷
    paper_question_ids = {
        pq.question_id
        for pq in db.query(ExamPaperQuestion)
        .filter(ExamPaperQuestion.exam_paper_id == record.exam_paper_id)
        .all()
    }
    for answer in answers:
        if answer.question_id not in paper_question_ids:
            raise HTTPException(status_code=400, detail=f"题目 {answer.question_id} 不属于本试卷")

    try:
        # Save user answers
        for answer in answers:
            # Check if answer already exists (update) or create new
            existing_answer = (
                db.query(UserAnswer)
                .filter(
                    UserAnswer.exam_record_id == exam_record_id,
                    UserAnswer.question_id == answer.question_id,
                    UserAnswer.user_id == current_user.id,
                )
                .first()
            )

            if existing_answer:
                existing_answer.answer_content = answer.answer_content
            else:
                user_answer = UserAnswer(
                    exam_record_id=exam_record_id,
                    question_id=answer.question_id,
                    user_id=current_user.id,
                    answer_content=answer.answer_content,
                )
                db.add(user_answer)

        # Update record status
        record.status = "submitted"
        record.submitted_at = datetime.utcnow()

        db.commit()
        db.refresh(record)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="提交失败，请稍后重试")

    return record


@router.post("/{exam_id}/grade", response_model=ExamGradeResponse)
def grade_exam(
    exam_id: int,
    grade_request: ExamGradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Auto grade exam for objective questions (single_choice, multiple_choice, true_false).
    Compares user answers with correct answers from Question and QuestionOption.
    Updates is_correct and score for each UserAnswer.
    """
    # Get exam record
    record = db.query(ExamRecord).filter(ExamRecord.id == grade_request.exam_record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Exam record not found")

    # Get exam paper questions
    paper_questions = db.query(ExamPaper).filter(ExamPaper.id == exam_id).first()
    if not paper_questions:
        raise HTTPException(status_code=404, detail="Exam paper not found")

    # Get user answers for this exam record
    user_answers = db.query(UserAnswer).filter(UserAnswer.exam_record_id == grade_request.exam_record_id).all()

    total_score = 0.0
    graded_count = 0
    results = []

    for ua in user_answers:
        question = db.query(Question).filter(Question.id == ua.question_id).first()
        if not question:
            continue

        if question.question_type not in AUTO_GRADABLE_TYPES:
            continue

        correct_answer = get_correct_answer(db, question)
        is_correct, score = grade_answer(question, ua.answer_content or "", correct_answer)

        ua.is_correct = is_correct
        ua.score = score
        total_score += score
        graded_count += 1

        results.append(
            UserAnswerResponse(
                id=ua.id,
                exam_record_id=ua.exam_record_id,
                question_id=ua.question_id,
                user_id=ua.user_id,
                answer_content=ua.answer_content,
                is_correct=is_correct,
                score=score,
            )
        )

    # Update exam record
    record.score = total_score
    record.status = "graded"

    db.commit()

    return ExamGradeResponse(
        exam_record_id=grade_request.exam_record_id, total_score=total_score, graded_count=graded_count, results=results
    )
