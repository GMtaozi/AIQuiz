"""AI Templates Async Tasks - background generation task management.

任务执行由 ARQ 队列承载（app/worker.py），本模块只负责：
创建任务记录 → 入队 → 取消（Redis 标志）→ 进度查询。
"""

import asyncio
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.question import GenerationTask
from app.models.user import User
from app.schemas.question import AsyncGenerateRequest, AsyncTaskResponse, TaskProgressResponse
from app.utils.rate_limit import rate_limit_ai_gen
from app.utils.security import get_current_user, require_teacher_or_admin
from app.worker import set_cancel_flag

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_task_ownership(task: GenerationTask, current_user: User) -> None:
    """校验任务归属（评估 P1-3 修复）：管理员可访问所有任务，其他用户只能访问自己的。

    返回 404（而非 403）以避免任务 ID 枚举。
    """
    if current_user.role != 1 and task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在")


def _enqueue_generation_task(task_id: int, req_dict: dict, user_id: int | None) -> None:
    """将出题任务投入 ARQ 队列（同步路由内通过临时事件循环调用）。

    失败时抛出异常，由调用方将任务标记为 failed（不静默卡 pending）。
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    async def _run():
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            # _job_id 幂等：同一任务不会被重复入队
            await pool.enqueue_job(
                "run_generation_task",
                task_id,
                req_dict,
                user_id,
                _job_id=f"gen_task_{task_id}",
            )
        finally:
            await pool.aclose()

    asyncio.run(_run())


def _create_task(db: Session, user_id: int, mode: str, params: dict) -> GenerationTask:
    task = GenerationTask(user_id=user_id, status="pending", progress=0, mode=mode, params=params)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _dispatch_or_fail(db: Session, task: GenerationTask, req_dict: dict, user_id: int | None) -> None:
    """入队；队列不可用时把任务置为 failed 并返回 503。"""
    try:
        _enqueue_generation_task(task.id, req_dict, user_id)
    except Exception as e:
        logger.error(f"任务入队失败 task_id={task.id}: {e}")
        task.status = "failed"
        task.error_message = "任务队列暂不可用，请稍后重试"
        db.commit()
        raise HTTPException(status_code=503, detail="任务队列暂不可用，请稍后重试")


@router.post("/hybrid-generate-async", response_model=AsyncTaskResponse)
def hybrid_generate_async(
    request: AsyncGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
    _rate_limit: None = Depends(rate_limit_ai_gen),
):
    """异步出题：立即返回任务ID，ARQ worker 后台执行，前端轮询进度"""
    task = _create_task(db, current_user.id, request.mode, request.model_dump())
    _dispatch_or_fail(db, task, request.model_dump(), current_user.id)

    return AsyncTaskResponse(
        task_id=task.id,
        status="pending",
        message=f"出题任务已创建（模式: {request.mode}）",
    )


@router.post("/task/{task_id}/cancel")
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Cancel a running generation task.（跨进程软取消：写入 Redis 标志）"""
    task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_task_ownership(task, current_user)

    if task.status in ("completed", "failed", "cancelled"):
        return {"message": f"任务已处于终态: {task.status}，无需取消"}

    if set_cancel_flag(task_id):
        return {"message": "取消信号已发送，任务将在下一检查点停止"}
    return {"message": "取消服务暂不可用（Redis 连接失败），请稍后重试"}


@router.post("/task/{task_id}/regenerate", response_model=AsyncTaskResponse)
def regenerate_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
    _rate_limit: None = Depends(rate_limit_ai_gen),
):
    """根据已有任务参数重新生成一道新任务"""
    original = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="原任务不存在")

    _check_task_ownership(original, current_user)

    params = dict(original.params or {})
    params.setdefault("mode", "hybrid")
    params.setdefault("count", 10)
    params.setdefault("difficulty", 3)

    new_task = _create_task(db, current_user.id, params.get("mode", "hybrid"), params)
    _dispatch_or_fail(db, new_task, params, current_user.id)

    return AsyncTaskResponse(
        task_id=new_task.id,
        status="pending",
        message=f"已根据任务 {task_id} 创建重新生成任务",
    )


@router.get("/task/{task_id}/progress", response_model=TaskProgressResponse)
def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get task progress"""
    task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_task_ownership(task, current_user)

    return TaskProgressResponse(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        mode=task.mode,
        rule_questions=task.rule_questions,
        ai_questions=task.ai_questions,
        total_questions=task.total_questions,
        error_message=task.error_message or "",
        questions=task.result.get("questions", []) if task.result else [],
    )


@router.get("/tasks", response_model=List[dict])
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List generation tasks"""
    query = db.query(GenerationTask)
    if current_user.role != 1:  # non-admin sees own tasks
        query = query.filter(GenerationTask.user_id == current_user.id)
    total = query.count()
    tasks = query.order_by(GenerationTask.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": t.id,
                "status": t.status,
                "progress": t.progress,
                "mode": t.mode,
                "total_questions": t.total_questions,
                "error_message": t.error_message,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
