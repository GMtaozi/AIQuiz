"""Audit Router - 试题审核模块"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, update
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models.question import Question
from app.models.user import User
from app.utils.security import get_current_user, require_admin, require_permission
from app.constants import UserRole

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audit"])

# ============ Schema ============

class AuditQuestionResponse(BaseModel):
    id: int
    content: str
    question_type: str
    difficulty: int
    subject_id: int
    chapter_id: int
    answer: Optional[str]
    explanation: Optional[str]
    is_ai_generated: bool
    audit_status: str
    audit_reason: Optional[str]
    status: int
    created_at: datetime
    options: List[dict] = []

    # 仅管理员可见的字段
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    items: List[AuditQuestionResponse]
    total: int
    page: int
    page_size: int


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        if not v or not v.strip():
            raise ValueError('驳回原因不能为空')
        return v.strip()


class BatchAuditRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(None, max_length=500)


def _build_audit_response(question: Question, include_created_by: bool = False) -> AuditQuestionResponse:
    """构建审核响应对象"""
    return AuditQuestionResponse(
        id=question.id,
        content=question.content,
        question_type=question.question_type,
        difficulty=question.difficulty,
        subject_id=question.subject_id,
        chapter_id=question.chapter_id,
        answer=question.answer,
        explanation=question.explanation,
        is_ai_generated=question.is_ai_generated,
        audit_status=question.audit_status,
        audit_reason=question.audit_reason,
        status=question.status,
        created_by=question.created_by if include_created_by else None,
        created_at=question.created_at,
        options=[{
            "id": opt.id,
            "option_label": opt.option_label,
            "option_content": opt.option_content,
            "is_correct": opt.is_correct,
            "order": opt.order
        } for opt in question.options]
    )


@router.get("/pending", response_model=AuditListResponse)
def get_pending_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    status: Optional[str] = Query(None, description="审核状态: pending/approved/rejected"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    exam_type_id: Optional[int] = Query(None, description="考试科目ID"),
    current_user: User = Depends(require_permission('audit')),
    db: Session = Depends(get_db),
):
    """获取审核题目列表（支持按状态、题型、难度、考试科目等筛选）"""
    logger.info(f"[审核列表] status={status}, exam_type_id={exam_type_id}")

    query = db.query(Question).options(joinedload(Question.options))

    # 按审核状态筛选，默认只查待审核
    if status:
        query = query.filter(Question.audit_status == status)
    else:
        query = query.filter(Question.audit_status == "pending")

    if question_type:
        query = query.filter(Question.question_type == question_type)
    if difficulty is not None:
        query = query.filter(Question.difficulty == difficulty)
    if keyword:
        query = query.filter(Question.content.contains(keyword))
    if start_date:
        query = query.filter(Question.created_at >= start_date)
    if end_date:
        query = query.filter(Question.created_at <= f"{end_date} 23:59:59")
    if exam_type_id is not None:
        # questions.subject_id 关联到 exam_types.id
        query = query.filter(Question.subject_id == exam_type_id)

    total = query.count()
    questions = query.offset((page - 1) * page_size).limit(page_size).all()

    # 非管理员不显示 created_by
    include_created_by = current_user.role == UserRole.ADMIN
    items = [_build_audit_response(q, include_created_by) for q in questions]

    return AuditListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


# 注意：批量操作的路由必须放在 /{question_id} 之前，否则 /batch/approve 会被 /{question_id} 先匹配

@router.post("/batch/approve")
def batch_approve_questions(
    request: BatchAuditRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量审核通过 - 使用事务保证原子性"""
    logger.info(f"[批量通过] 收到请求: {request}")
    if not request.ids:
        raise HTTPException(status_code=400, detail="请选择要审核的题目")

    # 使用行锁防止并发问题
    questions = db.query(Question).filter(
        Question.id.in_(request.ids),
        Question.audit_status == "pending"
    ).with_for_update().all()

    if not questions:
        raise HTTPException(status_code=400, detail="没有待审核的题目")

    now = datetime.utcnow()
    question_ids = [q.id for q in questions]

    # 使用批量更新保证原子性
    db.query(Question).filter(
        Question.id.in_(question_ids)
    ).update({
        "audit_status": "approved",
        "audited_by": current_user.id,
        "audited_at": now,
        "status": 1
    }, synchronize_session=False)

    db.commit()
    approved_count = len(question_ids)

    logger.info(f"用户 {current_user.id} 批量通过了 {approved_count} 道题目: ids={question_ids}")
    return {"message": f"已通过 {approved_count} 道题目", "approved_count": approved_count}


@router.post("/batch/reject")
def batch_reject_questions(
    request: BatchAuditRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量审核驳回 - 使用事务保证原子性"""
    if not request.ids:
        raise HTTPException(status_code=400, detail="请选择要审核的题目")

    if not request.reason or not request.reason.strip():
        raise HTTPException(status_code=400, detail="请填写驳回原因")

    reason = request.reason.strip()

    # 使用行锁防止并发问题
    questions = db.query(Question).filter(
        Question.id.in_(request.ids),
        Question.audit_status == "pending"
    ).with_for_update().all()

    if not questions:
        raise HTTPException(status_code=400, detail="没有待审核的题目")

    now = datetime.utcnow()
    question_ids = [q.id for q in questions]

    # 使用批量更新保证原子性
    db.query(Question).filter(
        Question.id.in_(question_ids)
    ).update({
        "audit_status": "rejected",
        "audit_reason": reason,
        "audited_by": current_user.id,
        "audited_at": now,
        "status": 0
    }, synchronize_session=False)

    db.commit()
    rejected_count = len(question_ids)

    logger.info(f"用户 {current_user.id} 批量驳回了 {rejected_count} 道题目: ids={question_ids}, 原因={reason}")
    return {
        "message": f"已驳回 {rejected_count} 道题目",
        "rejected_count": rejected_count,
        "reason": reason
    }


@router.get("/{question_id}", response_model=AuditQuestionResponse)
def get_question_for_audit(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取题目审核详情"""
    question = db.query(Question).options(
        joinedload(Question.options)
    ).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    include_created_by = current_user.role == UserRole.ADMIN
    return _build_audit_response(question, include_created_by)


@router.post("/{question_id}/approve")
def approve_question(
    question_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审核通过题目"""
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    if question.audit_status != "pending":
        raise HTTPException(status_code=400, detail="该题目已审核过")

    now = datetime.utcnow()
    question.audit_status = "approved"
    question.audited_by = current_user.id
    question.audited_at = now
    question.status = 1

    db.commit()
    logger.info(f"用户 {current_user.id} 审核通过了题目: id={question_id}")

    return {"message": "审核通过", "question_id": question_id}


@router.post("/{question_id}/reject")
def reject_question(
    question_id: int,
    request: RejectRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审核驳回题目"""
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    if question.audit_status != "pending":
        raise HTTPException(status_code=400, detail="该题目已审核过")

    now = datetime.utcnow()
    question.audit_status = "rejected"
    question.audit_reason = request.reason
    question.audited_by = current_user.id
    question.audited_at = now
    question.status = 0

    db.commit()
    logger.info(f"用户 {current_user.id} 驳回了题目: id={question_id}, 原因={request.reason}")

    return {"message": "已驳回", "question_id": question_id, "reason": request.reason}


@router.get("/statistics/summary")
def get_audit_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取审核统计信息"""
    # 使用聚合查询获取所有统计
    from sqlalchemy import case

    total = db.query(func.count(Question.id)).filter(
        Question.is_ai_generated == True
    ).scalar()

    pending = db.query(func.count(Question.id)).filter(
        Question.is_ai_generated == True,
        Question.audit_status == "pending"
    ).scalar()

    approved = db.query(func.count(Question.id)).filter(
        Question.is_ai_generated == True,
        Question.audit_status == "approved"
    ).scalar()

    rejected = db.query(func.count(Question.id)).filter(
        Question.is_ai_generated == True,
        Question.audit_status == "rejected"
    ).scalar()

    pass_rate = round(approved / total * 100, 2) if total and total > 0 else 0

    return {
        "total_ai_questions": total or 0,
        "pending": pending or 0,
        "approved": approved or 0,
        "rejected": rejected or 0,
        "pass_rate": pass_rate
    }
