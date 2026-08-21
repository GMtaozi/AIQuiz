"""AI Templates Async Tasks - background generation task management."""

import logging
import threading
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import AIPromptTemplate, GenerationTask, Subject
from app.models.user import User
from app.routers.ai_templates.generation import _write_ai_call_log
from app.schemas.question import AsyncGenerateRequest, AsyncTaskResponse, TaskProgressResponse
from app.services.ai_question import _call_ai_with_retry, _try_parse_questions_json, _verify_questions
from app.services.hybrid_question_generator import (
    build_kp_info_list,
    build_question_plans,
    rule_generate_questions,
)
from app.utils.rate_limit import rate_limit_ai_gen
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# 存储任务取消事件（全局字典，生产环境可换成 Redis）
_task_cancel_events: dict[int, threading.Event] = {}
_task_lock = threading.Lock()

# 评估 P1-2：并发出题任务上限，防止无界线程耗尽资源（完整解决方案是任务队列，此处先加护栏）
_MAX_CONCURRENT_TASKS = 20
_task_semaphore = threading.BoundedSemaphore(_MAX_CONCURRENT_TASKS)


def _get_subject_name(db: Session, subject_id: int | None) -> str:
    if not subject_id:
        return ""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    return subject.name if subject else ""


def _get_chapter_names(db: Session, chapter_ids: List[int]) -> List[str]:
    if not chapter_ids:
        return []
    from app.models.question import Chapter

    chapters = db.query(Chapter).filter(Chapter.id.in_(chapter_ids)).all()
    return [c.name for c in chapters if c.name]


def _check_task_ownership(task: GenerationTask, current_user: User) -> None:
    """校验任务归属（评估 P1-3 修复）：管理员可访问所有任务，其他用户只能访问自己的。

    返回 404（而非 403）以避免任务 ID 枚举。
    """
    if current_user.role != 1 and task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在")


def _execute_generation_task(task_id: int, req_dict: dict, user_id: int | None = None, cancel_event: threading.Event | None = None):
    """在后台线程中执行出题任务（独立 Session）"""
    from app.database import SessionLocal

    # 评估 P1-2：限制并发任务数（无界线程护栏）
    _task_semaphore.acquire()
    db = SessionLocal()
    try:
        task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        if not task:
            return

        task.status = "running"
        task.progress = 5
        db.commit()

        # 检查是否已被取消
        if cancel_event and cancel_event.is_set():
            task.status = "cancelled"
            task.error_message = "任务已被取消"
            db.commit()
            return

        from pydantic import BaseModel

        class HybridGenerateRequest(BaseModel):
            subject_id: int | None = None
            subject_name: str | None = None
            chapter_ids: List[int] | None = None
            chapter_names: List[str] | None = None
            knowledge_point_ids: List[int] | None = None
            knowledge_content: str | None = None
            question_types: List[str] | None = None
            count: int = 10
            difficulty: int = 3
            mode: str = "hybrid"
            template_id: int | None = None

        request = HybridGenerateRequest(**req_dict)

        task.progress = 10
        db.commit()

        # 如果选择了模板，查询模板内容
        template = None
        if request.template_id:
            template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == request.template_id).first()

        kp_info_list = build_kp_info_list(db, request.knowledge_point_ids)
        if not kp_info_list:
            task.status = "failed"
            task.error_message = "未找到有效的知识点"
            task.progress = 0
            db.commit()
            return

        task.progress = 15
        db.commit()

        plans = build_question_plans(kp_info_list, request.count, request.question_types)

        plan_summary = {
            "total_kps": len(kp_info_list),
            "type_distribution": {p.type_name: len(p.knowledge_points) for p in plans},
            "question_allocation": {p.type_name: p.total_count for p in plans},
        }

        rule_questions = []
        if request.mode in ("hybrid", "rule_only"):
            for plan in plans:
                if cancel_event and cancel_event.is_set():
                    break
                rqs = rule_generate_questions(plan)
                rule_questions.extend(rqs)
            task.progress = 40 if request.mode == "rule_only" else 30
            db.commit()

        ai_questions = []
        if request.mode in ("hybrid", "ai_only") and not (cancel_event and cancel_event.is_set()):
            import asyncio

            AI_BATCH_SIZE = 15
            max_total_time = min(30 + request.count * 2, 120)
            subject_name = request.subject_name or _get_subject_name(db, request.subject_id)
            chapter_names = request.chapter_names or _get_chapter_names(db, request.chapter_ids or [])

            async def _run_ai_generation():
                nonlocal ai_questions

                async def _ai_batch_call(batch_prompt: str, batch_label: str) -> list:
                    try:
                        result_text, _last_usage = await _call_ai_with_retry(
                            batch_prompt, max_tokens=8192, user_id=user_id
                        )
                        if _last_usage and _last_usage.total_tokens > 0:
                            _write_ai_call_log(
                                db=db,
                                user_id=user_id,
                                template_id=req_dict.get("template_id"),
                                resp=_last_usage,
                            )
                    except Exception as e:
                        logger.error(f"AI出题 [{batch_label}]: API调用异常: {e}")
                        return []
                    if result_text is None:
                        return []
                    questions_data = _try_parse_questions_json(result_text)
                    if not questions_data:
                        return []
                    processed = []
                    for q in questions_data:
                        processed.append(
                            {
                                "content": q.get("content", ""),
                                "answer": q.get("answer", ""),
                                "explanation": q.get("explanation", ""),
                                "question_type": q.get("question_type", "single_choice"),
                                "difficulty": q.get("difficulty", request.difficulty),
                                "subject_id": request.subject_id,
                                "chapter_id": request.chapter_ids[0] if request.chapter_ids else None,
                                "options": q.get("options"),
                            }
                        )
                    return processed

                # 分批并行调用
                batch_size = AI_BATCH_SIZE
                for i in range(0, len(plans), batch_size):
                    if cancel_event and cancel_event.is_set():
                        break
                    batch = plans[i : i + batch_size]
                    batch_prompts = []
                    for plan in batch:
                        prompt = build_strategic_prompt(
                            plan,
                            subject_name=subject_name,
                            chapter_names=chapter_names,
                            difficulty=request.difficulty,
                            template_prompt=template.prompt_template if template else None,
                        )
                        batch_prompts.append(prompt)

                    results = await asyncio.gather(
                        *[_ai_batch_call(p, f"batch-{i}-{j}") for j, p in enumerate(batch_prompts)],
                        return_exceptions=True,
                    )
                    for res in results:
                        if isinstance(res, list):
                            ai_questions.extend(res)

                    task.progress = min(30 + int(60 * (i + len(batch)) / max(len(plans), 1)), 90)
                    db.commit()

                # 启用题目校验：对 AI 生成的题目进行质量校验（在 async 上下文内执行）
                if ai_questions and request.knowledge_content and not (cancel_event and cancel_event.is_set()):
                    try:
                        ai_questions = await _verify_questions(
                            ai_questions,
                            request.knowledge_content,
                            request.question_types[0] if request.question_types else "single_choice",
                        )
                    except Exception as exc:
                        logger.warning(f"后台AI题目校验失败（不影响结果）: {exc}")

            asyncio.run(_run_ai_generation())

        # 检查是否被取消
        if cancel_event and cancel_event.is_set():
            task.status = "cancelled"
            task.error_message = "任务已被用户取消"
            db.commit()
            return

        # 合并结果
        all_questions = rule_questions + ai_questions
        seen = set()
        unique_questions = []
        for q in all_questions:
            key = q.get("content", "")[:50]
            if key not in seen:
                seen.add(key)
                unique_questions.append(q)

        task.status = "completed"
        task.progress = 100
        task.result = {
            "questions": unique_questions[: request.count],
            "total": len(unique_questions[: request.count]),
            "rule_count": len(rule_questions),
            "ai_count": len(ai_questions),
        }
        task.rule_questions = len(rule_questions)
        task.ai_questions = len(ai_questions)
        task.total_questions = len(unique_questions[: request.count])
        db.commit()

    except Exception as e:
        logger.error(f"后台出题任务失败: task_id={task_id}, error={e}")
        try:
            task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        # 清理取消事件
        if task_id in _task_cancel_events:
            with _task_lock:
                _task_cancel_events.pop(task_id, None)
        db.close()
        _task_semaphore.release()


@router.post("/hybrid-generate-async", response_model=AsyncTaskResponse)
def hybrid_generate_async(
    request: AsyncGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
    _rate_limit: None = Depends(rate_limit_ai_gen),
):
    """异步出题：立即返回任务ID，后台执行，前端轮询进度

    评估 P2-3：函数体无任何 await（仅同步 DB + 线程启动），由 async def 改为
    同步 def，FastAPI 自动调度到线程池，避免阻塞事件循环。
    """
    task = GenerationTask(
        user_id=current_user.id,
        status="pending",
        progress=0,
        mode=request.mode,
        params=request.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    req_dict = request.model_dump()
    cancel_event = threading.Event()
    with _task_lock:
        _task_cancel_events[task.id] = cancel_event
    thread = threading.Thread(
        target=_execute_generation_task,
        args=(task.id, req_dict, current_user.id, cancel_event),
        daemon=True,
    )
    thread.start()

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
    """Cancel a running generation task.（评估 P2-3：同步 def，无 await 需求）"""
    task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_task_ownership(task, current_user)

    if task.status in ("completed", "failed", "cancelled"):
        return {"message": f"任务已处于终态: {task.status}，无需取消"}

    cancel_event = _task_cancel_events.get(task_id)
    if cancel_event:
        cancel_event.set()
        return {"message": "取消信号已发送，任务将在下一检查点停止"}
    return {"message": "任务执行太快，取消事件未注册（极短任务可直接忽略）"}


@router.post("/task/{task_id}/regenerate", response_model=AsyncTaskResponse)
def regenerate_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
    _rate_limit: None = Depends(rate_limit_ai_gen),
):
    """根据已有任务参数重新生成一道新任务（评估 P2-3：同步 def，无 await 需求）"""
    original = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="原任务不存在")

    _check_task_ownership(original, current_user)

    params = dict(original.params or {})
    params.setdefault("mode", "hybrid")
    params.setdefault("count", 10)
    params.setdefault("difficulty", 3)

    new_task = GenerationTask(
        user_id=current_user.id,
        status="pending",
        progress=0,
        mode=params.get("mode", "hybrid"),
        params=params,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    cancel_event = threading.Event()
    with _task_lock:
        _task_cancel_events[new_task.id] = cancel_event
    thread = threading.Thread(
        target=_execute_generation_task,
        args=(new_task.id, params, current_user.id, cancel_event),
        daemon=True,
    )
    thread.start()

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
