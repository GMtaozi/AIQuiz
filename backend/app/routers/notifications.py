"""Notification Router - 通知模块"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse, NotificationStats
from app.utils.security import get_current_user

router = APIRouter(tags=["notifications"])


def create_notification(
    db: Session, notification_type: str, title: str, content: str, link: str = None, user_id: int = None
) -> Notification:
    """创建通知的辅助函数

    评估 P1-11 修复：原实现内部 db.commit() 会破坏外层事务原子性
    （审核批量流程中每写一条通知就提交一次，中途失败会残留半成品状态）。
    改为 flush，事务提交由调用方统一控制。

    扩展：创建通知后，根据通知类型决定是否发送邮件提醒。
    邮件发送失败不影响主流程（日志记录后降级）。
    """
    notification = Notification(user_id=user_id, type=notification_type, title=title, content=content, link=link)
    db.add(notification)
    db.flush()

    # 邮件通知（仅 warning/error/audit 类型，且需要知道用户邮箱）
    # 邮件发送失败不影响通知创建（best-effort）
    if user_id and notification_type in ("warning", "error", "audit"):
        try:
            _send_email_notification_async(db, user_id, title, content, notification_type)
        except Exception:
            pass  # 邮件发送失败不阻塞主流程

    return notification


def _send_email_notification_async(
    db: Session, user_id: int, title: str, content: str, notification_type: str
) -> None:
    """异步发送邮件通知（不阻塞主流程）

    注意：邮件发送是 best-effort，失败不影响通知创建。
    由于 create_notification 在事务 flush 阶段调用，邮件发送在事务提交前执行。
    如果后续事务回滚，邮件可能已发送但通知未持久化，这是可接受的（邮件内容仍有效）。
    """
    try:
        from app.models.user import User
        from app.services.email_service import send_email_notification

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.email:
            return

        send_email_notification(
            user_email=user.email,
            title=title,
            content=content,
            notification_type=notification_type,
        )
    except Exception as e:
        # 邮件发送失败不影响主流程
        import logging

        logging.getLogger(__name__).warning(f"邮件通知发送失败（不影响通知创建）: {e}")


@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: bool | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取当前用户的所有通知"""
    query = db.query(Notification).filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    notifications = query.order_by(desc(Notification.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return notifications


@router.get("/stats", response_model=NotificationStats)
def get_notification_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """获取通知统计信息"""
    from app.models.question import GenerationTask, Question

    # 统计待审核题目数
    pending_audit = db.query(func.count(Question.id)).filter(Question.audit_status == "pending").scalar() or 0

    # AI任务统计
    ai_tasks_completed = (
        db.query(func.count(GenerationTask.id)).filter(GenerationTask.status == "completed").scalar() or 0
    )

    ai_tasks_failed = db.query(func.count(GenerationTask.id)).filter(GenerationTask.status == "failed").scalar() or 0

    # 总通知数和未读数
    total = (
        db.query(func.count(Notification.id))
        .filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
        .scalar()
        or 0
    )

    unread = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.is_read == False, (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
        )
        .scalar()
        or 0
    )

    return NotificationStats(
        total=total,
        unread=unread,
        pending_audit=pending_audit,
        ai_tasks_completed=ai_tasks_completed,
        ai_tasks_failed=ai_tasks_failed,
    )


@router.put("/{notification_id}/read")
def mark_as_read(notification_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """标记单条通知为已读"""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None)),
        )
        .first()
    )

    if not notification:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    db.commit()
    return {"message": "已标记为已读"}


@router.put("/read-all")
def mark_all_as_read(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """标记所有通知为已读"""
    db.query(Notification).filter(
        Notification.is_read == False, (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
    ).update({"is_read": True})
    db.commit()
    return {"message": "已全部标记为已读"}


@router.delete("/{notification_id}")
def delete_notification(notification_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """删除通知"""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None)),
        )
        .first()
    )

    if not notification:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="通知不存在")

    db.delete(notification)
    db.commit()
    return {"message": "删除成功"}
