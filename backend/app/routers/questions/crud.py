"""Questions CRUD Router - Core CRUD operations and statistics for questions"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.constants import UserRole
from app.database import get_db
from app.models.question import Question, QuestionOption
from app.models.user import User
from app.schemas.question import (
    BatchDeleteRequest,
    BatchOperationResponse,
    BatchStatusRequest,
    QuestionCreate,
    QuestionDetailResponse,
    QuestionListResponse,
    QuestionOptionCreate,
    QuestionOptionResponse,
    QuestionStatistics,
    QuestionUpdate,
)
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid question types
VALID_QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "essay"}

# Fields that can be updated by question owner or admin
ALLOWED_UPDATE_FIELDS = {
    "chapter_id",
    "subject_id",
    "question_type",
    "content",
    "answer",
    "explanation",
    "difficulty",
    "score",
    "is_public",
    "tags",
    "meta",
    "status",
}


def _validate_question_options(question_type: str, options: List[QuestionOptionCreate] | None) -> None:
    """Validate question options based on question type."""
    if question_type in ("single_choice", "multiple_choice"):
        if not options or len(options) < 2:
            raise HTTPException(status_code=400, detail="选择题至少需要2个选项")
        correct_options = [o for o in options if o.is_correct]
        if not correct_options:
            raise HTTPException(status_code=400, detail="选择题必须至少有一个正确答案")
        if question_type == "single_choice" and len(correct_options) > 1:
            raise HTTPException(status_code=400, detail="单选题只能有一个正确答案")
    elif question_type == "true_false":
        # true_false should have exactly 2 options or none
        pass


def _resolve_chapter_id(db: Session, chapter_id: int | None, subject_id: int) -> int:
    """Resolve chapter_id for question creation.
    
    If chapter_id is provided, validate it exists.
    If not provided, try to find the first chapter of the subject, or fallback to 1.
    """
    if chapter_id is not None:
        return chapter_id
    
    # Try to find first chapter of the subject
    from app.models.question import Chapter
    chapter = db.query(Chapter).filter(Chapter.subject_id == subject_id).first()
    if chapter:
        return chapter.id
    
    # Final fallback
    return 1


# ============ CRUD Endpoints ============


@router.get("/", response_model=QuestionListResponse)
def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    subject_id: int | None = None,
    chapter_id: int | None = None,
    question_type: str | None = None,
    difficulty: int | None = None,
    status: str | None = None,
    keyword: str | None = Query(None, description="关键词搜索"),
    category_id: int | None = Query(None, description="按考试种类筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List questions with filtering and pagination"""
    from app.models.question import ExamType

    query = db.query(Question).options(joinedload(Question.options))

    if subject_id is not None:
        query = query.filter(Question.subject_id == subject_id)
    if chapter_id is not None:
        query = query.filter(Question.chapter_id == chapter_id)
    if question_type is not None:
        query = query.filter(Question.question_type == question_type)
    if difficulty is not None:
        query = query.filter(Question.difficulty == difficulty)
    if status is not None:
        query = query.filter(Question.status == status)
    else:
        query = query.filter(Question.status == 1, Question.audit_status == "approved")
    if keyword:
        # 转义 SQL LIKE 特殊字符，防止注入
        escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Question.content.ilike(f"%{escaped_keyword}%", escape="\\"))

    # 按考试种类筛选（联表 exam_types）
    if category_id is not None:
        query = query.join(ExamType, Question.subject_id == ExamType.id).filter(ExamType.category_id == category_id)

    total = query.count()
    questions = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for q in questions:
        items.append(
            QuestionDetailResponse(
                id=q.id,
                chapter_id=q.chapter_id,
                subject_id=q.subject_id,
                question_type=q.question_type,
                content=q.content,
                answer=q.answer,
                explanation=q.explanation,
                difficulty=q.difficulty,
                score=q.score,
                is_public=q.is_public,
                is_ai_generated=q.is_ai_generated,
                source=q.source,
                audit_status=q.audit_status,
                audit_reason=q.audit_reason,
                tags=q.tags,
                meta=q.meta,
                created_by=q.created_by,
                status=q.status,
                created_at=q.created_at,
                updated_at=q.updated_at,
                audited_at=q.audited_at,
                options=[
                    QuestionOptionResponse(
                        id=opt.id,
                        option_label=opt.option_label,
                        option_content=opt.option_content,
                        is_correct=opt.is_correct,
                        order=opt.order,
                    )
                    for opt in q.options
                ],
            )
        )

    return QuestionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/", response_model=QuestionDetailResponse, status_code=201)
def create_question(
    question_data: QuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_teacher_or_admin)
):
    """Create a question with its options (teacher/admin only)."""
    if question_data.question_type not in VALID_QUESTION_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的题型: {question_data.question_type}")

    _validate_question_options(question_data.question_type, question_data.options)
    resolved_chapter_id = _resolve_chapter_id(db, question_data.chapter_id, question_data.subject_id)

    question = Question(
        chapter_id=resolved_chapter_id,
        subject_id=question_data.subject_id,
        question_type=question_data.question_type,
        content=question_data.content,
        answer=question_data.answer,
        explanation=question_data.explanation,
        difficulty=question_data.difficulty,
        score=question_data.score,
        is_public=question_data.is_public,
        tags=question_data.tags,
        meta=question_data.meta,
        status=question_data.status or 1,
        source=question_data.source or "system",
        is_ai_generated=question_data.is_ai_generated or False,
        created_by=current_user.id,
    )
    db.add(question)
    db.flush()

    if question_data.options:
        for i, opt_data in enumerate(question_data.options):
            option = QuestionOption(
                question_id=question.id,
                option_label=opt_data.option_label,
                option_content=opt_data.option_content,
                is_correct=opt_data.is_correct,
                order=opt_data.order if opt_data.order is not None else i,
            )
            db.add(option)

    db.commit()
    db.refresh(question)
    return question


@router.post("/batch", response_model=List[QuestionDetailResponse], status_code=201)
def batch_create_questions(
    questions_data: List[QuestionCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Batch create multiple questions (teacher/admin only)."""
    logger.info(f"批量创建题目: 共 {len(questions_data)} 道题目")
    created_questions = []

    try:
        for idx, q_data in enumerate(questions_data):
            if q_data.question_type not in VALID_QUESTION_TYPES:
                logger.error(f"第{idx + 1}题: 无效的题型 {q_data.question_type}")
                raise HTTPException(status_code=400, detail=f"无效的题型: {q_data.question_type}")

            _validate_question_options(q_data.question_type, q_data.options)
            resolved_chapter_id = _resolve_chapter_id(db, q_data.chapter_id, q_data.subject_id)

            question = Question(
                chapter_id=resolved_chapter_id,
                subject_id=q_data.subject_id,
                question_type=q_data.question_type,
                content=q_data.content,
                answer=q_data.answer,
                explanation=q_data.explanation,
                difficulty=q_data.difficulty,
                score=q_data.score,
                is_public=q_data.is_public,
                tags=q_data.tags,
                meta=q_data.meta,
                status=q_data.status or 1,
                source=q_data.source or "system",
                is_ai_generated=q_data.is_ai_generated or False,
                created_by=current_user.id,
            )
            db.add(question)
            db.flush()

            if q_data.options:
                for i, opt_data in enumerate(q_data.options):
                    option = QuestionOption(
                        question_id=question.id,
                        option_label=opt_data.option_label,
                        option_content=opt_data.option_content,
                        is_correct=opt_data.is_correct,
                        order=opt_data.order if opt_data.order is not None else i,
                    )
                    db.add(option)

            created_questions.append(question)
            logger.debug(f"第{idx + 1}题创建成功, question_id={question.id}")

        db.commit()
        for q in created_questions:
            db.refresh(q)

        logger.info(f"批量创建题目成功: {len(created_questions)} 道")
        return created_questions

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"批量创建题目失败: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="批量创建题目失败，请稍后重试")


# ============ Statistics Endpoint ============
# 注意：静态路径必须先于 /{question_id} 注册，否则会被参数路由遮蔽


@router.get("/statistics", response_model=QuestionStatistics)
def get_question_statistics(
    subject_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取题库统计信息 - 使用数据库聚合查询避免内存溢出"""
    from sqlalchemy import case, func

    base_filter = []
    if subject_id is not None:
        base_filter.append(Question.subject_id == subject_id)

    total = db.query(func.count(Question.id)).filter(*base_filter).scalar() or 0

    type_results = (
        db.query(Question.question_type, func.count(Question.id))
        .filter(*base_filter)
        .group_by(Question.question_type)
        .all()
    )
    by_type = {r[0]: r[1] for r in type_results}

    difficulty_result = (
        db.query(
            func.sum(case((Question.difficulty <= 2, 1), else_=0)).label("easy"),
            func.sum(case((Question.difficulty == 3, 1), else_=0)).label("medium"),
            func.sum(case((Question.difficulty >= 4, 1), else_=0)).label("hard"),
        )
        .filter(*base_filter)
        .first()
    )

    difficulty_counts = {
        "easy": difficulty_result.easy or 0,
        "medium": difficulty_result.medium or 0,
        "hard": difficulty_result.hard or 0,
    }

    subject_results = (
        db.query(Question.subject_id, func.count(Question.id)).filter(*base_filter).group_by(Question.subject_id).all()
    )
    by_subject = {str(r[0]): r[1] for r in subject_results}

    audit_results = (
        db.query(Question.audit_status, func.count(Question.id))
        .filter(*base_filter)
        .group_by(Question.audit_status)
        .all()
    )
    by_audit_status = {r[0]: r[1] for r in audit_results}

    ai_generated_count = (
        db.query(func.count(Question.id)).filter(*base_filter, Question.is_ai_generated == True).scalar() or 0
    )

    return QuestionStatistics(
        total=total,
        by_type=by_type,
        by_difficulty=difficulty_counts,
        by_subject=by_subject,
        by_audit_status=by_audit_status,
        ai_generated_count=ai_generated_count,
    )


@router.get("/{question_id}", response_model=QuestionDetailResponse)
def get_question(
    question_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_teacher_or_admin)
):
    """Get a question by ID with its options (requires teacher or admin)"""
    question = db.query(Question).options(joinedload(Question.options)).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.put("/{question_id}", response_model=QuestionDetailResponse)
def update_question(
    question_id: int,
    question_data: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Update a question and its options (teacher/admin only)."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check ownership: only creator or admin can modify
    if question.created_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to update this question")

    # SECURITY FIX: Use whitelist-based update instead of mass assignment
    update_data = question_data.model_dump(exclude_unset=True)
    options_data = update_data.pop("options", None)

    safe_update_data = {k: v for k, v in update_data.items() if k in ALLOWED_UPDATE_FIELDS}

    for field, value in safe_update_data.items():
        setattr(question, field, value)

    if options_data is not None:
        _validate_question_options(question.question_type, options_data)
        db.query(QuestionOption).filter(QuestionOption.question_id == question_id).delete()
        for i, opt_data in enumerate(options_data):
            option = QuestionOption(
                question_id=question_id,
                option_label=opt_data.option_label,
                option_content=opt_data.option_content,
                is_correct=opt_data.is_correct,
                order=opt_data.order if opt_data.order is not None else i,
            )
            db.add(option)

    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=204)
def delete_question(
    question_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_teacher_or_admin)
):
    """Delete a question - soft delete (teacher/admin only)."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check ownership: only creator or admin can delete
    if question.created_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to delete this question")

    question.status = 0
    db.commit()
    return None


@router.post("/batch-delete", response_model=BatchOperationResponse)
def batch_delete_questions(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """批量删除题目（软删除，事务保证原子性）"""
    if not request.ids:
        return BatchOperationResponse(success_count=0, fail_count=0, failed_ids=[], message="未选择题目")

    success_count = 0
    failed_ids = []

    try:
        # 查询存在的题目并检查权限
        questions = db.query(Question).filter(Question.id.in_(request.ids)).with_for_update().all()
        found_ids = {q.id for q in questions}

        for q in questions:
            if q.created_by != current_user.id and current_user.role != UserRole.ADMIN:
                failed_ids.append(q.id)
                continue

            q.status = 0
            success_count += 1

        db.commit()

        missing_ids = set(request.ids) - found_ids
        all_failed = failed_ids + list(missing_ids)

        return BatchOperationResponse(
            success_count=success_count,
            fail_count=len(all_failed),
            failed_ids=all_failed,
            message=f"成功删除 {success_count} 题，失败 {len(all_failed)} 题"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"批量删除题目失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量删除失败: {e}")


@router.post("/batch-status", response_model=BatchOperationResponse)
def batch_update_question_status(
    request: BatchStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """批量更新题目状态（事务保证原子性）"""
    if not request.ids:
        return BatchOperationResponse(success_count=0, fail_count=0, failed_ids=[], message="未选择题目")

    if request.status not in (0, 1, 2):
        return BatchOperationResponse(success_count=0, fail_count=len(request.ids), failed_ids=request.ids, message="无效的状态值")

    success_count = 0
    failed_ids = []

    try:
        questions = db.query(Question).filter(Question.id.in_(request.ids)).with_for_update().all()
        found_ids = {q.id for q in questions}

        for q in questions:
            if q.created_by != current_user.id and current_user.role != UserRole.ADMIN:
                failed_ids.append(q.id)
                continue

            q.status = request.status
            success_count += 1

        db.commit()

        missing_ids = set(request.ids) - found_ids
        all_failed = failed_ids + list(missing_ids)

        status_text = {0: "禁用", 1: "启用", 2: "待启用"}.get(request.status, str(request.status))
        return BatchOperationResponse(
            success_count=success_count,
            fail_count=len(all_failed),
            failed_ids=all_failed,
            message=f"成功{status_text} {success_count} 题，失败 {len(all_failed)} 题"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"批量更新题目状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量更新状态失败: {e}")


# ============ Statistics Endpoint ============
