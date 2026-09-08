"""Audit Router - 试题审核模块"""

from datetime import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, update
from sqlalchemy.orm import Session, joinedload

from app.constants import UserRole
from app.database import get_db
from app.models.question import AuditLog, Question
from app.models.user import User
from app.schemas.audit import (
    AuditListResponse,
    AuditLogResponse,
    AuditQuestionResponse,
    BatchAuditRequest,
    RejectRequest,
)
from app.utils.security import get_current_user, require_permission, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audit"])


def _create_audit_log(db: Session, question_id: int, auditor_id: int, action: str, old_status: str | None, new_status: str, reason: str | None = None, ip_address: str | None = None, user_agent: str | None = None):
    """创建审核日志"""
    log = AuditLog(
        question_id=question_id,
        auditor_id=auditor_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)


def _notify_question_creator(db: Session, question_id: int, creator_id: int, action: str, reason: str | None = None):
    """通知题目创建者"""
    from app.routers.notifications import create_notification

    action_text = "通过" if action == "approved" else "驳回"
    title = f"题目审核{action_text}通知"
    content = f"您创建的题目（ID: {question_id}）已被{action_text}"
    if reason:
        content += f"，原因：{reason}"

    create_notification(
        db=db,
        notification_type="audit",
        title=title,
        content=content,
        link=f"/questions/{question_id}",
        user_id=creator_id,
    )


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
        options=[
            {
                "id": opt.id,
                "option_label": opt.option_label,
                "option_content": opt.option_content,
                "is_correct": opt.is_correct,
                "order": opt.order,
            }
            for opt in question.options
        ],
    )


@router.get("/pending", response_model=AuditListResponse)
def get_pending_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    question_type: str | None = None,
    difficulty: int | None = None,
    status: str | None = Query(None, description="审核状态: pending/approved/rejected"),
    keyword: str | None = Query(None, description="关键词搜索"),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    exam_type_id: int | None = Query(None, description="考试科目ID"),
    current_user: User = Depends(require_permission("audit")),
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

    return AuditListResponse(items=items, total=total, page=page, page_size=page_size)


# 注意：批量操作的路由必须放在 /{question_id} 之前，否则 /batch/approve 会被 /{question_id} 先匹配


@router.post("/batch/approve")
def batch_approve_questions(
    request: BatchAuditRequest,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量审核通过 - 使用事务保证原子性"""
    logger.info(f"[批量通过] 收到请求: {request}")
    if not request.ids:
        raise HTTPException(status_code=400, detail="请选择要审核的题目")

    # 使用行锁防止并发问题
    questions = (
        db.query(Question)
        .filter(Question.id.in_(request.ids), Question.audit_status == "pending")
        .with_for_update()
        .all()
    )

    if not questions:
        raise HTTPException(status_code=400, detail="没有待审核的题目")

    now = datetime.utcnow()
    question_ids = [q.id for q in questions]

    # 使用批量更新保证原子性
    db.query(Question).filter(Question.id.in_(question_ids)).update(
        {"audit_status": "approved", "audited_by": current_user.id, "audited_at": now, "status": 1},
        synchronize_session=False,
    )

    # 批量创建审核日志 + 通知创建者
    for q in questions:
        _create_audit_log(db, q.id, current_user.id, "approved", "pending", "approved")
        if q.created_by and q.created_by != current_user.id:
            _notify_question_creator(db, q.id, q.created_by, "approved")

    db.commit()
    approved_count = len(question_ids)

    logger.info(f"用户 {current_user.id} 批量通过了 {approved_count} 道题目: ids={question_ids}")
    return {"message": f"已通过 {approved_count} 道题目", "approved_count": approved_count}


@router.post("/batch/reject")
def batch_reject_questions(
    request: BatchAuditRequest,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """批量审核驳回 - 使用事务保证原子性"""
    if not request.ids:
        raise HTTPException(status_code=400, detail="请选择要审核的题目")

    if not request.reason or not request.reason.strip():
        raise HTTPException(status_code=400, detail="请填写驳回原因")

    reason = request.reason.strip()

    # 使用行锁防止并发问题
    questions = (
        db.query(Question)
        .filter(Question.id.in_(request.ids), Question.audit_status == "pending")
        .with_for_update()
        .all()
    )

    if not questions:
        raise HTTPException(status_code=400, detail="没有待审核的题目")

    now = datetime.utcnow()
    question_ids = [q.id for q in questions]

    # 使用批量更新保证原子性
    db.query(Question).filter(Question.id.in_(question_ids)).update(
        {
            "audit_status": "rejected",
            "audit_reason": reason,
            "audited_by": current_user.id,
            "audited_at": now,
            "status": 0,
        },
        synchronize_session=False,
    )

    # 批量创建审核日志 + 通知创建者
    for q in questions:
        _create_audit_log(db, q.id, current_user.id, "rejected", "pending", "rejected", reason)
        if q.created_by and q.created_by != current_user.id:
            _notify_question_creator(db, q.id, q.created_by, "rejected", reason)

    db.commit()
    rejected_count = len(question_ids)

    logger.info(f"用户 {current_user.id} 批量驳回了 {rejected_count} 道题目: ids={question_ids}, 原因={reason}")
    return {"message": f"已驳回 {rejected_count} 道题目", "rejected_count": rejected_count, "reason": reason}


@router.get("/{question_id}", response_model=AuditQuestionResponse)
def get_question_for_audit(
    question_id: int,
    current_user: User = Depends(require_permission("audit")),
    db: Session = Depends(get_db),
):
    """获取题目审核详情"""
    question = db.query(Question).options(joinedload(Question.options)).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    include_created_by = current_user.role == UserRole.ADMIN
    return _build_audit_response(question, include_created_by)


@router.post("/{question_id}/approve")
def approve_question(
    question_id: int,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """审核通过题目"""
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    if question.audit_status != "pending":
        raise HTTPException(status_code=400, detail="该题目已审核过")

    now = datetime.utcnow()
    old_status = question.audit_status
    question.audit_status = "approved"
    question.audited_by = current_user.id
    question.audited_at = now
    question.status = 1

    # 创建审核日志
    _create_audit_log(db, question_id, current_user.id, "approved", old_status, "approved")
    # 通知创建者
    if question.created_by and question.created_by != current_user.id:
        _notify_question_creator(db, question_id, question.created_by, "approved")

    db.commit()
    logger.info(f"用户 {current_user.id} 审核通过了题目: id={question_id}")

    return {"message": "审核通过", "question_id": question_id}


@router.post("/{question_id}/reject")
def reject_question(
    question_id: int,
    request: RejectRequest,
    current_user: User = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    """审核驳回题目"""
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    if question.audit_status != "pending":
        raise HTTPException(status_code=400, detail="该题目已审核过")

    now = datetime.utcnow()
    old_status = question.audit_status
    question.audit_status = "rejected"
    question.audit_reason = request.reason
    question.audited_by = current_user.id
    question.audited_at = now
    question.status = 0

    # 创建审核日志
    _create_audit_log(db, question_id, current_user.id, "rejected", old_status, "rejected", request.reason)
    # 通知创建者
    if question.created_by and question.created_by != current_user.id:
        _notify_question_creator(db, question_id, question.created_by, "rejected", request.reason)

    db.commit()
    logger.info(f"用户 {current_user.id} 驳回了题目: id={question_id}, 原因={request.reason}")

    return {"message": "已驳回", "question_id": question_id, "reason": request.reason}


@router.get("/{question_id}/logs", response_model=List[AuditLogResponse])
def get_question_audit_logs(
    question_id: int,
    current_user: User = Depends(require_permission("audit")),
    db: Session = Depends(get_db),
):
    """获取题目的审核历史日志"""
    logs = db.query(AuditLog).filter(AuditLog.question_id == question_id).order_by(AuditLog.created_at.desc()).all()
    return logs


@router.get("/statistics/summary")
def get_audit_statistics(
    current_user: User = Depends(require_permission("audit")),
    db: Session = Depends(get_db),
):
    """获取审核统计信息"""
    # 使用聚合查询获取所有统计
    from sqlalchemy import case

    total = db.query(func.count(Question.id)).filter(Question.is_ai_generated == True).scalar()

    pending = (
        db.query(func.count(Question.id))
        .filter(Question.is_ai_generated == True, Question.audit_status == "pending")
        .scalar()
    )

    approved = (
        db.query(func.count(Question.id))
        .filter(Question.is_ai_generated == True, Question.audit_status == "approved")
        .scalar()
    )

    rejected = (
        db.query(func.count(Question.id))
        .filter(Question.is_ai_generated == True, Question.audit_status == "rejected")
        .scalar()
    )

    pass_rate = round(approved / total * 100, 2) if total and total > 0 else 0

    return {
        "total_ai_questions": total or 0,
        "pending": pending or 0,
        "approved": approved or 0,
        "rejected": rejected or 0,
        "pass_rate": pass_rate,
    }
