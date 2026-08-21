"""AI Templates Generation - question generation endpoints + shared helpers."""

import asyncio
import logging
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.knowledge import KnowledgePoint
from app.models.question import AICallLog, AIPromptTemplate, Subject
from app.models.user import User
from app.schemas.question import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    HybridGenerateRequest,
    HybridGenerateResponse,
)
from app.services.ai_question import (
    _call_ai_with_retry,
    _try_parse_questions_json,
    _verify_questions,
)
from app.services.hybrid_question_generator import (
    build_kp_info_list,
    build_question_plans,
    build_strategic_prompt,
    rule_generate_questions,
)
from app.utils.rate_limit import rate_limit_ai_gen
from app.utils.security import require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ai_call_log(
    db: Session,
    user_id: int | None,
    template_id: int | None,
    resp: "AIResponse",
    provider_config: dict | None = None,
) -> None:
    """Write an AICallLog entry. Safe no-op if required fields are missing."""
    try:
        from app.services.ai_provider import get_ai_provider

        provider_info = get_ai_provider().get_provider_info()
        provider_key = provider_info.get("key", "unknown")
        model = provider_info.get("default_model", "unknown")
    except Exception:
        provider_key = "unknown"
        model = "unknown"

    raw_usage = resp.raw_usage or {}
    cost = raw_usage.get("_estimated_cost_usd", 0.0)

    try:
        log_entry = AICallLog(
            user_id=user_id,
            template_id=template_id,
            provider=provider_key,
            model=model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            total_tokens=resp.total_tokens,
            cost=cost,
            call_status="failed" if resp.error_message else "success",
            error_message=resp.error_message,
            meta={
                "duration_ms": resp.duration_ms,
                "raw_usage": raw_usage,
            },
        )
        db.add(log_entry)
        db.commit()
    except Exception as exc:
        logger.warning(f"[AICallLog] 写入失败: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_knowledge_context(db: Session, knowledge_point_ids: List[int]) -> str:
    """Build context string from knowledge points.

    优先携带 content_excerpt（原文片段）+ description（摘要），让出题基于原文。
    """
    if not knowledge_point_ids:
        return ""
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(knowledge_point_ids)).all()
    parts = []
    for kp in kps:
        if kp.content_excerpt:
            # 有原文片段：摘要 + 原文参考
            parts.append(f"【{kp.name}】{kp.description or ''}\n\n原文参考：\n{kp.content_excerpt}")
        elif kp.description:
            parts.append(f"【{kp.name}】{kp.description}")
        else:
            parts.append(f"【{kp.name}】")
    return "\n".join(parts)


def _build_knowledge_groups(db: Session, knowledge_point_ids: List[int], max_chars_per_group: int = 6000) -> List[Tuple[str, List[int]]]:
    """Build knowledge groups ensuring all points are covered.

    max_chars_per_group 调大到 6000（excerpt 比纯 description 更长，适当放宽以保证每块语义完整）。

    Returns:
        List of (group_text, knowledge_point_ids_for_group) tuples.
    """
    if not knowledge_point_ids:
        return [("", [])]

    kps = db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(knowledge_point_ids)).all()
    if not kps:
        return [("", [])]

    # Sort by order to ensure related points stay in the same group
    kps.sort(key=lambda kp: (kp.order or 0, kp.id))

    point_strs = []
    for kp in kps:
        if kp.content_excerpt:
            point_strs.append((f"【{kp.name}】{kp.description or ''}\n\n原文参考：\n{kp.content_excerpt}", kp.id))
        elif kp.description:
            point_strs.append((f"【{kp.name}】{kp.description}", kp.id))
        else:
            point_strs.append((f"【{kp.name}】", kp.id))

    groups = []
    current_group = ""
    current_ids = []
    for ps, kp_id in point_strs:
        if len(current_group) + len(ps) + 1 > max_chars_per_group and current_group:
            groups.append((current_group.strip(), current_ids))
            current_group = ""
            current_ids = []
        current_group += ps + "\n"
        current_ids.append(kp_id)
    if current_group:
        groups.append((current_group.strip(), current_ids))

    return groups if groups else [("", [])]


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate_questions_endpoint(
    request: GenerateQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
    _rate_limit: None = Depends(rate_limit_ai_gen),
):
    """Generate questions using AI with retry and circuit breaker"""
    if request.template_id:
        template = db.query(AIPromptTemplate).filter(AIPromptTemplate.id == request.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    else:
        template = None

    # 构建知识点分组（每组携带该组对应的知识点 ID）
    if request.knowledge_point_ids:
        knowledge_groups = _build_knowledge_groups(db, request.knowledge_point_ids, max_chars_per_group=4000)
    elif request.knowledge_content:
        knowledge_groups = [(request.knowledge_content[:4000], request.knowledge_point_ids or [])]
    else:
        knowledge_groups = [("", [])]

    total_questions = []
    group_count = len(knowledge_groups)

    # 总超时控制
    max_total_time = min(30 + request.count * 2, 120)
    ai_start_time = asyncio.get_event_loop().time()
    ai_timed_out = False

    async def _ai_batch_call(batch_prompt: str, batch_label: str) -> list:
        try:
            result_text, _last_usage = await _call_ai_with_retry(batch_prompt, max_tokens=8192, user_id=current_user.id)
            if _last_usage and _last_usage.total_tokens > 0:
                _write_ai_call_log(
                    db=db,
                    user_id=current_user.id,
                    template_id=request.template_id,
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

    for group_idx, (kp_content, group_kp_ids) in enumerate(knowledge_groups):
        if ai_timed_out:
            break

        context = _build_knowledge_context(db, group_kp_ids)
        subject_name = request.subject_name or _get_subject_name(db, request.subject_id)
        chapter_names = request.chapter_names or _get_chapter_names(db, request.chapter_ids or [])
        prompt = build_strategic_prompt(
            None,
            subject_name=subject_name,
            chapter_names=chapter_names,
            difficulty=request.difficulty,
            template_prompt=template.prompt_template if template else None,
        )

        try:
            questions = await asyncio.wait_for(_ai_batch_call(prompt, f"group-{group_idx}"), timeout=60)
            total_questions.extend(questions)
        except TimeoutError:
            ai_timed_out = True
            break

    rule_questions = []
    if not ai_timed_out:
        kp_list = build_kp_info_list(db, request.knowledge_point_ids or [])
        if kp_list:
            plans = build_question_plans(kp_list, request.count - len(total_questions), request.question_types)
            for plan in plans:
                rqs = rule_generate_questions(plan)
                rule_questions.extend(rqs)

    all_questions = total_questions + rule_questions
    seen = set()
    unique_questions = []
    for q in all_questions:
        key = q.get("content", "")[:50]
        if key not in seen:
            seen.add(key)
            unique_questions.append(q)

    final_questions = unique_questions[: request.count]
    return GenerateQuestionsResponse(
        success=True,
        questions=final_questions,
        total_generated=len(final_questions),
        rule_count=len(rule_questions),
        ai_count=len(total_questions),
        message=f"成功生成 {len(final_questions)} 道题目",
    )


@router.post("/hybrid-generate", response_model=HybridGenerateResponse)
async def hybrid_generate_endpoint(
    request: HybridGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
    _rate_limit: None = Depends(rate_limit_ai_gen),
):
    """混合出题：规则引擎做策略规划，AI按策略灵活执行"""
    if request.mode not in ("hybrid", "rule_only", "ai_only"):
        request.mode = "hybrid"

    if request.knowledge_point_ids:
        knowledge_groups = _build_knowledge_groups(db, request.knowledge_point_ids, max_chars_per_group=4000)
    elif request.knowledge_content:
        knowledge_groups = [(request.knowledge_content[:4000], request.knowledge_point_ids or [])]
    else:
        knowledge_groups = [("", [])]

    rule_questions = []
    ai_questions = []

    kp_info_list = []
    plans = []
    if request.mode in ("hybrid", "rule_only", "ai_only"):
        kp_info_list = build_kp_info_list(db, request.knowledge_point_ids or [])
        if kp_info_list:
            plans = build_question_plans(kp_info_list, request.count, request.question_types)

    if request.mode in ("hybrid", "rule_only"):
        for plan in plans:
            rqs = rule_generate_questions(plan)
            rule_questions.extend(rqs)

    if request.mode in ("hybrid", "ai_only"):
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
                        batch_prompt, max_tokens=8192, user_id=current_user.id
                    )
                    if _last_usage and _last_usage.total_tokens > 0:
                        _write_ai_call_log(
                            db=db,
                            user_id=current_user.id,
                            template_id=request.template_id,
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

            batch_size = AI_BATCH_SIZE
            for i in range(0, len(plans), batch_size):
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

        await asyncio.wait_for(_run_ai_generation(), timeout=max_total_time)

        # 启用题目校验：对 AI 生成的题目进行质量校验
        if ai_questions and request.knowledge_content:
            try:
                ai_questions = await _verify_questions(
                    ai_questions,
                    request.knowledge_content,
                    request.question_types[0] if request.question_types else "single_choice",
                )
            except Exception as exc:
                logger.warning(f"AI题目校验失败（不影响结果）: {exc}")

    all_questions = rule_questions + ai_questions
    seen = set()
    unique_questions = []
    for q in all_questions:
        key = q.get("content", "")[:50]
        if key not in seen:
            seen.add(key)
            unique_questions.append(q)

    final_questions = unique_questions[: request.count]
    return HybridGenerateResponse(
        success=True,
        questions=final_questions,
        total_generated=len(final_questions),
        rule_count=len(rule_questions),
        ai_count=len(ai_questions),
        message=f"混合出题完成，共生成 {len(final_questions)} 道题目",
    )
