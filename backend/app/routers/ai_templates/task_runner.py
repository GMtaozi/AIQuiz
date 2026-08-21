"""AI 出题任务的同步执行体。

由 app/worker.py 的 ARQ 任务在线程中调用（asyncio.to_thread），
独立 DB Session，通过 check_cancelled 回调实现跨进程软取消。
"""
import asyncio
import logging
from typing import Callable, List

from sqlalchemy.orm import Session

from app.models.question import AIPromptTemplate, GenerationTask, Subject
from app.routers.ai_templates.generation import _write_ai_call_log
from app.services.ai_question import _call_ai_with_retry, _try_parse_questions_json, _verify_questions
from app.services.hybrid_question_generator import (
    build_kp_info_list,
    build_question_plans,
    build_strategic_prompt,
    rule_generate_questions,
)

logger = logging.getLogger(__name__)


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


def execute_generation_task(
    task_id: int,
    req_dict: dict,
    user_id: int | None = None,
    check_cancelled: Callable[[], bool] | None = None,
):
    """执行出题任务（独立 Session，运行于 worker 线程）。

    check_cancelled: 跨进程取消检查回调（Redis 标志），在各个检查点轮询。
    """
    from pydantic import BaseModel

    from app.database import SessionLocal

    def _cancelled() -> bool:
        return bool(check_cancelled and check_cancelled())

    db = SessionLocal()
    try:
        task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        if not task:
            return

        task.status = "running"
        task.progress = 5
        db.commit()

        # 检查是否已被取消
        if _cancelled():
            task.status = "cancelled"
            task.error_message = "任务已被取消"
            db.commit()
            return

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

        rule_questions = []
        if request.mode in ("hybrid", "rule_only"):
            for plan in plans:
                if _cancelled():
                    break
                rqs = rule_generate_questions(plan)
                rule_questions.extend(rqs)
            task.progress = 40 if request.mode == "rule_only" else 30
            db.commit()

        ai_questions = []
        if request.mode in ("hybrid", "ai_only") and not _cancelled():
            AI_BATCH_SIZE = 15
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
                    if _cancelled():
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
                if ai_questions and request.knowledge_content and not _cancelled():
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
        if _cancelled():
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
        db.close()
