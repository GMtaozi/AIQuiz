"""智能组卷生成端点。

包含：自动组卷、A/B 卷、组卷进度。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User
from app.models.question import ExamPaper, ExamPaperQuestion, ExamType, Question
from app.routers.papers_generate.utils import (
    _select_questions_by_difficulty,
    select_questions_by_usage_priority,
)
from app.schemas.paper import (
    AutoGenerateRequest,
    PaperDetailResponse,
)
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()


def _validate_subject_and_filter_questions(db: Session, request) -> tuple:
    """验证科目并筛选题目
    
    Returns:
        tuple: (exam_type, actual_subject_id, available_questions)
    """
    exam_type = db.query(ExamType).filter(ExamType.id == request.subject_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="科目不存在")

    actual_subject_id = exam_type.subject_id

    query = db.query(Question).filter(
        Question.subject_id == actual_subject_id, Question.status == 1, Question.audit_status == "approved"
    )

    if request.knowledge_point_ids:
        all_questions = query.all()
        kp_ids_set = set(request.knowledge_point_ids)
        available_questions = [
            q
            for q in all_questions
            if q.meta
            and q.meta.get("knowledge_point_ids")
            and any(kp_id in kp_ids_set for kp_id in q.meta.get("knowledge_point_ids", []))
        ]
        if not available_questions:
            logger.warning(f"知识点过滤后无题目，将不使用知识点过滤。知识点IDs: {request.knowledge_point_ids}")
            available_questions = all_questions
    else:
        available_questions = query.all()

    return exam_type, actual_subject_id, available_questions


def _parse_type_config(request) -> dict:
    """解析题型配置（支持新旧格式）"""
    type_config_parsed = {}
    for qtype, config in request.question_type_config.items():
        if isinstance(config, dict):
            type_config_parsed[qtype] = {"count": config.get("count", 0), "score": config.get("score", 5.0)}
        else:
            type_config_parsed[qtype] = {"count": config, "score": 5.0}
    return type_config_parsed


def _create_paper_record(db: Session, request, current_user, questions: list, type_config_parsed: dict, paper_type: str, ab_group: str = None) -> ExamPaper:
    """创建试卷记录"""
    type_scores = {qtype: cfg["score"] for qtype, cfg in type_config_parsed.items()}
    actual_total_score = sum(type_scores.get(q.question_type, q.score) for q in questions)

    config = {
        "paper_type": paper_type,
        "knowledge_point_ids": request.knowledge_point_ids,
        "question_type_config": request.question_type_config,
        "difficulty_config": request.difficulty_config,
        "template_id": request.template_id,
        "actual_question_count": len(questions),
        "actual_total_score": actual_total_score,
    }
    if ab_group:
        config["ab_group"] = ab_group

    paper = ExamPaper(
        title=request.title if not ab_group else f"{request.title} ({ab_group}卷)",
        subject_id=request.subject_id,
        total_score=request.total_score,
        total_time=request.total_time,
        passing_score=request.passing_score,
        description=request.description or "",
        config=config,
        status="draft",
        created_by=current_user.id,
    )
    db.add(paper)
    db.flush()

    for order, q in enumerate(questions):
        configured_score = type_scores.get(q.question_type, q.score)
        epq = ExamPaperQuestion(exam_paper_id=paper.id, question_id=q.id, order=order, score=configured_score)
        db.add(epq)
        q.used_count = (q.used_count or 0) + 1

    return paper


def _reload_paper(db: Session, paper_id: int) -> ExamPaper:
    """重新加载试卷（带关联题目和选项）"""
    return (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_id)
        .first()
    )


@router.post("/auto-generate", response_model=PaperDetailResponse)
def auto_generate_paper(
    request: AutoGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """智能组卷 - 根据题型和难度配置自动选择题目生成试卷"""
    logger.info(f"用户 {current_user.id} 开始智能组卷: {request.title}")

    # 验证科目并筛选题目
    _exam_type, _actual_subject_id, available_questions = _validate_subject_and_filter_questions(db, request)

    # 解析题型配置
    type_config_parsed = _parse_type_config(request)

    # 验证总题目数量
    total_requested = sum(cfg["count"] for cfg in type_config_parsed.values())
    if len(available_questions) < total_requested:
        raise HTTPException(
            status_code=400, detail=f"题库中题目数量不足。请求: {total_requested}, 可用: {len(available_questions)}"
        )

    # 按题型分组
    questions_by_type = {}
    for q in available_questions:
        if q.question_type not in questions_by_type:
            questions_by_type[q.question_type] = []
        questions_by_type[q.question_type].append(q)

    # 按难度分组
    questions_by_difficulty = {"easy": [], "medium": [], "hard": []}
    for q in available_questions:
        if q.difficulty <= 2:
            questions_by_difficulty["easy"].append(q)
        elif q.difficulty == 3:
            questions_by_difficulty["medium"].append(q)
        else:
            questions_by_difficulty["hard"].append(q)

    # 按题型选择题目（智能分配：从各知识点均匀选取，不足时从其他知识点补充）
    selected_questions = []
    used_question_ids = set()
    shortage_info = []  # 记录不足的题型信息

    # 按题型分组后，再按知识点分组，便于均匀分配
    questions_by_kp_and_type = {}  # {kp_id: {qtype: [questions]}}

    for q in available_questions:
        if q.meta and q.meta.get("knowledge_point_ids"):
            for kp_id in q.meta.get("knowledge_point_ids", []):
                if kp_id not in questions_by_kp_and_type:
                    questions_by_kp_and_type[kp_id] = {}
                if q.question_type not in questions_by_kp_and_type[kp_id]:
                    questions_by_kp_and_type[kp_id][q.question_type] = []
                questions_by_kp_and_type[kp_id][q.question_type].append(q)

    # 记录每种题型配置的分数
    type_scores = {qtype: cfg["score"] for qtype, cfg in type_config_parsed.items()}

    for qtype, config in type_config_parsed.items():
        count = config["count"]
        if count <= 0:
            continue
        if qtype not in questions_by_type:
            shortage_info.append(f"{qtype}题型数量为0")
            continue

        # 获取该题型的所有可用题目（未使用的）
        all_available = [q for q in questions_by_type[qtype] if q.id not in used_question_ids]
        if not all_available:
            shortage_info.append(f"{qtype}无可用题目")
            continue

        # 按知识点题目数量占比分配
        # 统计每个知识点的题目数量
        kp_question_counts = {}
        kp_questions_by_kp = {}  # {kp_id: [questions]}
        for kp_id, type_dict in questions_by_kp_and_type.items():
            if qtype in type_dict:
                available_for_kp = [q for q in type_dict[qtype] if q.id not in used_question_ids]
                if available_for_kp:
                    kp_questions_by_kp[kp_id] = available_for_kp
                    kp_question_counts[kp_id] = len(available_for_kp)

        if not kp_questions_by_kp:
            shortage_info.append(f"{qtype}无可用题目")
            continue

        # 计算总题目数和每个知识点的占比
        total_kp_questions = sum(kp_question_counts.values())
        actual_count = min(count, total_kp_questions)

        if total_kp_questions < count:
            shortage_info.append(f"{qtype}请求{count}题但仅{total_kp_questions}题可用")

        # 按占比分配：从各知识点按题目数量占比选取
        selected_for_type = []
        remaining_count = actual_count

        for kp_id, questions in kp_questions_by_kp.items():
            if remaining_count <= 0:
                break
            # 计算该知识点应分配的题目数量（按占比）
            proportion = kp_question_counts[kp_id] / total_kp_questions
            allocate_count = min(int(actual_count * proportion), remaining_count, len(questions))
            # 从该知识点选取 - 优先选择使用次数少的题目
            selected = select_questions_by_usage_priority(questions, allocate_count)
            selected_for_type.extend(selected)
            remaining_count -= allocate_count

        # 如果还有剩余，优先选择使用次数少的题目补充
        if remaining_count > 0:
            used_ids = set(q.id for q in selected_for_type)
            remaining_questions = [q for q in all_available if q.id not in used_ids]
            if remaining_questions:
                more = select_questions_by_usage_priority(
                    remaining_questions, min(remaining_count, len(remaining_questions))
                )
                selected_for_type.extend(more)

        selected_questions.extend(selected_for_type)
        used_question_ids.update(q.id for q in selected_for_type)

    # B1/B2/B3: 检查题目数量是否满足需求，如果不足则尝试补充或报错
    total_requested = sum(cfg["count"] for cfg in type_config_parsed.values())
    if len(selected_questions) < total_requested:
        shortage_count = total_requested - len(selected_questions)
        logger.warning(
            f"智能组卷题目不足: 请求{total_requested}题，仅获取{len(selected_questions)}题，短缺{shortage_count}题"
        )

        # B3: 尝试从其他题型补充（降级策略：放宽题型限制）
        if shortage_info:
            # 按难度分组（不过滤题型）
            remaining_by_difficulty = {"easy": [], "medium": [], "hard": []}
            for q in available_questions:
                if q.id not in used_question_ids:
                    if q.difficulty <= 2:
                        remaining_by_difficulty["easy"].append(q)
                    elif q.difficulty == 3:
                        remaining_by_difficulty["medium"].append(q)
                    else:
                        remaining_by_difficulty["hard"].append(q)

            # 尝试从其他难度级别补充 - 优先选择使用次数少的题目
            supplemented = 0
            for diff_level, diff_questions in remaining_by_difficulty.items():
                if supplemented >= shortage_count:
                    break
                available_pool = [q for q in diff_questions if q.id not in used_question_ids]
                need = min(shortage_count - supplemented, len(available_pool))
                if need > 0:
                    chosen = select_questions_by_usage_priority(available_pool, need)
                    selected_questions.extend(chosen)
                    used_question_ids.update(q.id for q in chosen)
                    supplemented += len(chosen)
                    logger.info(f"从{diff_level}难度补充了{len(chosen)}题")

        # 再次检查
        if len(selected_questions) < total_requested:
            final_shortage = total_requested - len(selected_questions)
            shortage_detail = "; ".join(shortage_info) if shortage_info else "题目总数不足"
            raise HTTPException(
                status_code=400,
                detail=f"题库题目不足，无法满足组卷需求。请求: {total_requested}题, 可用: {len(selected_questions)}题, 短缺: {final_shortage}题。详细: {shortage_detail}",
            )

    # 创建试卷
    paper = _create_paper_record(db, request, current_user, selected_questions, type_config_parsed, "auto_generate")
    db.commit()
    paper = _reload_paper(db, paper.id)

    logger.info(
        f"用户 {current_user.id} 智能组卷完成: paper_id={paper.id}, "
        f"题目数={len(selected_questions)}"
    )

    # 生成短缺通知
    shortage_notice = None
    if shortage_info:
        # 提取题型配置中的题目数量
        total_requested = 0
        for config in request.question_type_config.values():
            if isinstance(config, dict):
                total_requested += config.get("count", 0)
            else:
                total_requested += config
        shortage_notice = f"注意：本次组卷请求{total_requested}题，实际生成{len(selected_questions)}题。部分题型数量不足，请管理员补充：{', '.join(shortage_info)}"
        logger.warning(shortage_notice)

    logger.info(f"[AUTO-GEN] paper_id={paper.id}, exam_paper_questions count={len(paper.exam_paper_questions)}")
    response = PaperDetailResponse.from_orm_with_status_int(paper)
    response.shortage_notice = shortage_notice
    return response


@router.post("/auto-generate-ab", response_model=dict)
def auto_generate_ab_papers(
    request: AutoGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """智能生成 A/B 平行卷 - 基于同一配置生成两份题目不重复的试卷"""
    logger.info(f"用户 {current_user.id} 开始智能组卷A/B卷: {request.title}")

    # 验证科目并筛选题目
    _exam_type, _actual_subject_id, available_questions = _validate_subject_and_filter_questions(db, request)

    # 解析题型配置
    type_config_parsed = _parse_type_config(request)
    total_requested = sum(cfg["count"] for cfg in type_config_parsed.values())

    # 检查题库是否足够生成两份试卷
    if len(available_questions) < total_requested * 2:
        raise HTTPException(
            status_code=400,
            detail=f"题库题目不足，无法生成A/B两卷。需要: {total_requested * 2}题, 可用: {len(available_questions)}题"
        )

    # 按题型分组
    questions_by_type = {}
    for q in available_questions:
        if q.question_type not in questions_by_type:
            questions_by_type[q.question_type] = []
        questions_by_type[q.question_type].append(q)

    # 生成A卷和B卷
    paper_a_questions = []
    paper_b_questions = []
    used_question_ids = set()

    for qtype, config in type_config_parsed.items():
        count = config["count"]
        if count <= 0:
            continue
        if qtype not in questions_by_type:
            continue

        # 获取该题型的所有可用题目
        all_available = [q for q in questions_by_type[qtype] if q.id not in used_question_ids]
        if len(all_available) < count * 2:
            raise HTTPException(
                status_code=400,
                detail=f"题型 {qtype} 题目不足，无法生成A/B两卷。需要: {count * 2}题, 可用: {len(all_available)}题"
            )

        # A卷：按难度比例选择
        a_questions = _select_questions_by_difficulty(
            all_available, count,
            request.difficulty_config,
            {"easy": [q for q in all_available if q.difficulty <= 2],
             "medium": [q for q in all_available if q.difficulty == 3],
             "hard": [q for q in all_available if q.difficulty >= 4]}
        )

        # B卷：从剩余题目中选择，确保难度分布一致
        remaining_after_a = [q for q in all_available if q.id not in [q.id for q in a_questions]]
        b_questions = _select_questions_by_difficulty(
            remaining_after_a, count,
            request.difficulty_config,
            {"easy": [q for q in remaining_after_a if q.difficulty <= 2],
             "medium": [q for q in remaining_after_a if q.difficulty == 3],
             "hard": [q for q in remaining_after_a if q.difficulty >= 4]}
        )

        paper_a_questions.extend(a_questions)
        paper_b_questions.extend(b_questions)
        used_question_ids.update(q.id for q in a_questions + b_questions)

    # 创建A卷
    paper_a = _create_paper_record(db, request, current_user, paper_a_questions, type_config_parsed, "auto_generate_ab", "A")

    # 创建B卷
    paper_b = _create_paper_record(db, request, current_user, paper_b_questions, type_config_parsed, "auto_generate_ab", "B")

    db.commit()

    # 重新加载
    paper_a = _reload_paper(db, paper_a.id)
    paper_b = _reload_paper(db, paper_b.id)

    logger.info(f"[AUTO-GEN-AB] A卷 paper_id={paper_a.id}, B卷 paper_id={paper_b.id}")

    return {
        "paper_a": PaperDetailResponse.from_orm_with_status_int(paper_a),
        "paper_b": PaperDetailResponse.from_orm_with_status_int(paper_b),
        "message": f"成功生成A/B两卷，各{len(paper_a_questions)}题"
    }


@router.get("/generate/{task_id}/progress")
def get_generate_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取组卷进度（用于异步组卷场景）"""
    # 目前是同步组卷，直接返回完成状态
    paper = db.query(ExamPaper).filter(ExamPaper.id == task_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"task_id": task_id, "status": "completed", "progress": 100, "paper_id": paper.id, "title": paper.title}
