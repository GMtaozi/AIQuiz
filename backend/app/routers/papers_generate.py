"""智能组卷路由（评估 P2-1：从 papers.py 抽取的生成/组卷端点）。

包含：智能组卷预览、难度分布、AI 大纲、自动组卷、A/B 卷、组卷进度。
"""

import logging
import random
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User
from app.models.question import Chapter, ExamPaper, ExamPaperQuestion, ExamType, Question, Subject
from app.schemas.paper import (
    AutoGeneratePreviewRequest,
    AutoGenerateRequest,
    DifficultyDistributionRequest,
    DifficultyDistributionResponse,
    PaperDetailResponse,
    PaperOutlineRequest,
    PaperOutlineResponse,
    PaperOutlineSection,
)
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()


def select_questions_by_usage_priority(question_pool: list, count: int) -> list:
    """根据使用次数优先级选择题目

    优先选择使用次数少的题目，同时保持随机性：
    1. 按使用次数分组
    2. 优先从低使用次数组选择
    3. 同组内随机选择
    """
    if count <= 0 or not question_pool:
        return []
    if len(question_pool) <= count:
        return question_pool

    # 按使用次数分组
    by_usage = {}
    for q in question_pool:
        used = getattr(q, "used_count", 0) or 0
        if used not in by_usage:
            by_usage[used] = []
        by_usage[used].append(q)

    selected = []
    remaining = count

    # 从低使用次数到高使用次数依次选择
    for used_count in sorted(by_usage.keys()):
        if remaining <= 0:
            break
        pool = by_usage[used_count]
        # 从该组中选择，最多选完该组或剩余需求
        take = min(remaining, len(pool))
        if take == len(pool):
            selected.extend(pool)
        else:
            selected.extend(random.sample(pool, take))
        remaining -= take

    # 如果还不够（应该不会发生），从剩余池中随机补充
    if remaining > 0:
        selected_ids = {q.id for q in selected}
        remaining_pool = [q for q in question_pool if q.id not in selected_ids]
        if remaining_pool:
            selected.extend(random.sample(remaining_pool, min(remaining, len(remaining_pool))))

    return selected

# 尝试导入 python-docx
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx 未安装，Word导出功能将不可用")

# 评估 P2-1：Word/PDF 导出逻辑已抽取到 app.services.paper_doc_exporter（含字体注册/P2-16 配置化）
from app.services.paper_doc_exporter import (
    PDF_AVAILABLE,
    REGISTERED_FONTS,
    _generate_pdf_paper,
    _generate_word_paper,
    _get_chinese_num,
    _make_chinese_run,
)

@router.post("/auto-generate/preview")
def preview_auto_generate(
    request: AutoGeneratePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预览智能组卷结果（不保存）"""
    # 前端发送的是 exam_types.id，需要转换为 exam_types.subject_id 来查询题目
    exam_type = db.query(ExamType).filter(ExamType.id == request.subject_id).first()
    if exam_type:
        actual_subject_id = exam_type.subject_id
    else:
        actual_subject_id = request.subject_id

    # 根据配置筛选题目
    query = db.query(Question).filter(
        Question.subject_id == actual_subject_id, Question.status == 1, Question.audit_status == "approved"
    )

    if request.knowledge_point_ids:
        # 假设 Question 有 chapter_id，关联到知识点
        query = query.filter(Question.chapter_id.in_(request.knowledge_point_ids))

    questions = query.all()

    # 按题型和难度分类统计
    preview = {
        "total_available": len(questions),
        "by_type": {},
        "by_difficulty": {"easy": 0, "medium": 0, "hard": 0},
        "score_summary": {},
    }

    for q in questions:
        # 按题型统计
        qtype = q.question_type
        if qtype not in preview["by_type"]:
            preview["by_type"][qtype] = {"count": 0, "total_score": 0}
        preview["by_type"][qtype]["count"] += 1
        preview["by_type"][qtype]["total_score"] += q.score

        # 按难度统计
        if q.difficulty <= 2:
            preview["by_difficulty"]["easy"] += 1
        elif q.difficulty == 3:
            preview["by_difficulty"]["medium"] += 1
        else:
            preview["by_difficulty"]["hard"] += 1

    return preview

@router.post("/difficulty-distribution", response_model=DifficultyDistributionResponse)
def get_difficulty_distribution(
    request: DifficultyDistributionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定条件下题库的难度分布，用于智能组卷时自动调整难度配比

    根据知识点和题型筛选可用题目，返回各难度档位的数量和建议配比
    每种题型独立计算难度分布建议
    """
    import random

    # 前端发送的是 exam_types.id，需要转换为 exam_types.subject_id 来查询题目
    exam_type = db.query(ExamType).filter(ExamType.id == request.subject_id).first()
    if exam_type:
        actual_subject_id = exam_type.subject_id
    else:
        actual_subject_id = request.subject_id

    # 构建查询
    query = db.query(Question).filter(
        Question.subject_id == actual_subject_id, Question.status == 1, Question.audit_status == "approved"
    )

    # 知识点过滤
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
    else:
        available_questions = query.all()

    # 题型过滤
    if request.question_types:
        available_questions = [q for q in available_questions if q.question_type in request.question_types]

    # 统计总体难度分布
    easy = sum(1 for q in available_questions if q.difficulty <= 2)
    medium = sum(1 for q in available_questions if q.difficulty == 3)
    hard = sum(1 for q in available_questions if q.difficulty >= 4)
    total = easy + medium + hard

    # 计算可用比例
    easy_ratio = (easy / total * 100) if total > 0 else 0
    medium_ratio = (medium / total * 100) if total > 0 else 0
    hard_ratio = (hard / total * 100) if total > 0 else 0

    # 按题型统计难度分布
    question_types_in_bank = set(q.question_type for q in available_questions)
    by_question_type = {}
    suggestions = {}

    for qtype in request.question_types:
        type_questions = [q for q in available_questions if q.question_type == qtype]
        type_easy = sum(1 for q in type_questions if q.difficulty <= 2)
        type_medium = sum(1 for q in type_questions if q.difficulty == 3)
        type_hard = sum(1 for q in type_questions if q.difficulty >= 4)
        type_total = type_easy + type_medium + type_hard

        # 计算该题型在题库中的实际比例
        type_easy_ratio = (type_easy / type_total * 100) if type_total > 0 else 0
        type_medium_ratio = (type_medium / type_total * 100) if type_total > 0 else 0
        type_hard_ratio = (type_hard / type_total * 100) if type_total > 0 else 0

        by_question_type[qtype] = {
            "total": type_total,
            "easy": type_easy,
            "medium": type_medium,
            "hard": type_hard,
            "easy_ratio": round(type_easy_ratio, 1),
            "medium_ratio": round(type_medium_ratio, 1),
            "hard_ratio": round(type_hard_ratio, 1),
        }

        # 生成该题型的建议配比
        # 如果题库中某难度没有题目，则该难度比例为0
        if type_total == 0:
            suggestions[qtype] = {"easy_ratio": 0, "medium_ratio": 0, "hard_ratio": 0}
        else:
            # 随机生成，但基于实际题目分布情况，确保 medium > easy > hard
            # 根据实际题目是否存在来决定范围
            min_hard = 10 if type_hard > 0 else 0
            max_hard = 35 if type_hard > 0 else 0
            min_easy = 15 if type_easy > 0 else 0
            max_easy = 40 if type_easy > 0 else 0

            if type_hard == 0:
                # 没有难题，hard=0
                hard_suggested = 0
                if type_easy == 0:
                    # 只有中等题
                    easy_suggested = 0
                    medium_suggested = 100
                else:
                    # 没有难题，easy 和 medium 随机分配
                    # medium 至少 50%
                    medium_suggested = random.randint(50, 80)
                    easy_suggested = 100 - medium_suggested
            elif type_easy == 0:
                # 没有简单题，只有 medium 和 hard
                hard_suggested = random.randint(20, 40)
                medium_suggested = 100 - hard_suggested
                easy_suggested = 0
            else:
                # 三种难度都有，随机分配
                hard_suggested = random.randint(min_hard, max_hard)
                max_easy = min(max_easy, 100 - hard_suggested - 40)  # 确保 medium 有至少40%空间
                if max_easy < min_easy:
                    max_easy = min_easy
                easy_suggested = random.randint(min_easy, max_easy)
                medium_suggested = 100 - hard_suggested - easy_suggested

            suggestions[qtype] = {
                "easy_ratio": easy_suggested,
                "medium_ratio": medium_suggested,
                "hard_ratio": hard_suggested,
            }

    return DifficultyDistributionResponse(
        total=total,
        easy=easy,
        medium=medium,
        hard=hard,
        easy_ratio=round(easy_ratio, 1),
        medium_ratio=round(medium_ratio, 1),
        hard_ratio=round(hard_ratio, 1),
        suggestions=suggestions,
        by_question_type=by_question_type,
    )

@router.post("/outline", response_model=PaperOutlineResponse)
def generate_paper_outline(
    request: PaperOutlineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 辅助试卷大纲：基于科目/知识点树生成章节级出题计划

    返回结构化的试卷大纲，包含：
    - 章节名称
    - 关联知识点ID列表
    - 建议题型、题数、分值
    - 生成建议（如知识点覆盖、难度分布）
    """
    # 验证科目
    exam_type = db.query(ExamType).filter(ExamType.id == request.subject_id).first()
    if exam_type:
        actual_subject_id = exam_type.subject_id
    else:
        actual_subject_id = request.subject_id

    subject = db.query(Subject).filter(Subject.id == actual_subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 查询该科目下的可用知识点（优先使用前端指定的知识点）
    if request.knowledge_point_ids:
        kp_query = db.query(Chapter).filter(
            Chapter.subject_id == actual_subject_id,
            Chapter.id.in_(request.knowledge_point_ids)
        )
    else:
        kp_query = db.query(Chapter).filter(Chapter.subject_id == actual_subject_id)

    knowledge_points = kp_query.all()

    # 查询该科目下各题型的可用题目数量
    type_stats = {}
    for qtype in ["single_choice", "multiple_choice", "true_false", "essay"]:
        q = db.query(Question).filter(
            Question.subject_id == actual_subject_id,
            Question.question_type == qtype,
            Question.status == 1,
            Question.audit_status == "approved"
        )
        if request.knowledge_point_ids:
            q = q.filter(Question.chapter_id.in_(request.knowledge_point_ids))
        type_stats[qtype] = q.count()

    # 构建大纲：将知识点按父级分组为章节
    sections: List[PaperOutlineSection] = []
    suggestions: List[str] = []

    # 如果用户预设了章节结构，直接使用
    if request.sections:
        total_allocated_score = 0.0
        for section in request.sections:
            section_name = section.get("name", "未命名章节")
            section_kp_ids = section.get("knowledge_point_ids", [])
            section_type = section.get("question_type", "single_choice")
            section_count = section.get("count", 0)
            section_score = section.get("score", 0)

            sections.append(PaperOutlineSection(
                section_name=section_name,
                knowledge_point_ids=section_kp_ids,
                question_type=section_type,
                count=section_count,
                score=section_score
            ))
            total_allocated_score += section_score

        # 检查分值是否匹配
        if abs(total_allocated_score - request.total_score) > 0.01:
            suggestions.append(
                f"当前章节总分 {total_allocated_score} 分，与目标总分 {request.total_score} 分不一致，请调整"
            )
    else:
        # 自动生成大纲：按知识点分组
        # 获取知识点树结构
        all_kps = db.query(Chapter).filter(Chapter.subject_id == actual_subject_id).all()
        kp_map = {kp.id: kp for kp in all_kps}

        # 找出顶级知识点（没有父级或父级不在当前集合中）
        root_kps = []
        for kp in knowledge_points:
            if kp.parent_id is None or kp.parent_id not in kp_map:
                root_kps.append(kp)

        if not root_kps:
            # 如果没有明确的层级结构，将所有知识点作为一个章节
            root_kps = knowledge_points

        # 按题型分配章节
        type_names = {
            "single_choice": "单选题",
            "multiple_choice": "多选题",
            "true_false": "判断题",
            "essay": "简答题"
        }

        # 计算总分和题数
        total_questions = 0
        type_allocation = {
            "single_choice": {"count": 0, "score": 2},
            "multiple_choice": {"count": 0, "score": 4},
            "true_false": {"count": 0, "score": 2},
            "essay": {"count": 0, "score": 8}
        }

        # 根据可用题目数量分配
        available_types = [t for t in type_stats.keys() if type_stats[t] > 0]
        if not available_types:
            available_types = ["single_choice", "true_false", "essay"]

        # 简单的均匀分配策略
        per_section = max(1, len(root_kps) // len(available_types) + 1)
        type_idx = 0
        for kp in root_kps:
            qtype = available_types[type_idx % len(available_types)]
            count = min(per_section, type_stats[qtype])
            if count <= 0:
                continue
            score = count * type_allocation[qtype]["score"]
            sections.append(PaperOutlineSection(
                section_name=f"{kp.name}（{type_names[qtype]}）",
                knowledge_point_ids=[kp.id],
                question_type=qtype,
                count=count,
                score=score
            ))
            total_questions += count
            type_idx += 1

        # 生成建议
        if total_questions == 0:
            suggestions.append("该科目下暂无已审核通过的题目，请先添加题目")
        else:
            suggestions.append(f"建议共 {total_questions} 题，总分 {request.total_score} 分")
            if len(knowledge_points) == 0:
                suggestions.append("未选择知识点，建议选择具体知识点以提升组卷精准度")
            if type_stats.get("essay", 0) == 0:
                suggestions.append("题库中暂无简答题，如需主观题请先补充")

    return PaperOutlineResponse(
        subject_id=actual_subject_id,
        total_score=request.total_score,
        total_time=request.total_time,
        sections=sections,
        suggestions=suggestions,
        message="大纲生成成功，确认后可用于智能组卷"
    )

@router.post("/auto-generate", response_model=PaperDetailResponse)
def auto_generate_paper(
    request: AutoGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """智能组卷 - 根据题型和难度配置自动选择题目生成试卷"""
    logger.info(f"用户 {current_user.id} 开始智能组卷: {request.title}")

    # 验证科目：前端发送的是 exam_types.id
    exam_type = db.query(ExamType).filter(ExamType.id == request.subject_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 用 exam_type.subject_id 来查询题目（对应 subjects.id）
    actual_subject_id = exam_type.subject_id

    # 构建基础查询
    query = db.query(Question).filter(
        Question.subject_id == actual_subject_id, Question.status == 1, Question.audit_status == "approved"
    )

    # 如果指定了知识点，先用chapter_id初步过滤，再用meta中的knowledge_point_ids精细过滤
    if request.knowledge_point_ids:
        all_questions = query.all()
        # 从meta字段中解析knowledge_point_ids进行过滤
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

    # 解析题型配置（支持新旧格式）
    # 新格式: {"single_choice": {"count": 20, "score": 2}}
    # 旧格式: {"single_choice": 20}
    type_config_parsed = {}
    for qtype, config in request.question_type_config.items():
        if isinstance(config, dict):
            type_config_parsed[qtype] = {"count": config.get("count", 0), "score": config.get("score", 5.0)}
        else:
            type_config_parsed[qtype] = {"count": config, "score": 5.0}

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

    # 验证总分（使用配置的分数）
    total_selected_score = sum(type_scores.get(q.question_type, q.score) for q in selected_questions)

    # 创建试卷
    paper = ExamPaper(
        title=request.title,
        subject_id=request.subject_id,
        total_score=request.total_score,
        total_time=request.total_time,
        passing_score=request.passing_score,
        description=request.description or "",
        config={
            "paper_type": "auto_generate",
            "knowledge_point_ids": request.knowledge_point_ids,
            "question_type_config": request.question_type_config,
            "difficulty_config": request.difficulty_config,
            "template_id": request.template_id,
            "actual_question_count": len(selected_questions),
            "actual_total_score": total_selected_score,
        },
        status="draft",
        created_by=current_user.id,
    )
    db.add(paper)
    db.flush()

    # 创建题目关联 - 使用配置的分数而非题目原始分数
    for order, q in enumerate(selected_questions):
        # 使用该题型配置的分数
        configured_score = type_scores.get(q.question_type, q.score)
        epq = ExamPaperQuestion(
            exam_paper_id=paper.id,
            question_id=q.id,
            order=order,
            score=configured_score,
        )
        db.add(epq)

    # 更新题目的使用次数（优先使用次数少的题目）
    for q in selected_questions:
        q.used_count = (q.used_count or 0) + 1

    db.commit()
    db.refresh(paper)

    logger.info(
        f"用户 {current_user.id} 智能组卷完成: paper_id={paper.id}, "
        f"题目数={len(selected_questions)}, 实际总分={total_selected_score}"
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

    # 重新加载
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper.id)
        .first()
    )

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

    # 验证科目
    exam_type = db.query(ExamType).filter(ExamType.id == request.subject_id).first()
    if not exam_type:
        raise HTTPException(status_code=404, detail="科目不存在")

    actual_subject_id = exam_type.subject_id

    # 构建基础查询
    query = db.query(Question).filter(
        Question.subject_id == actual_subject_id, Question.status == 1, Question.audit_status == "approved"
    )

    # 知识点过滤
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

    # 解析题型配置
    type_config_parsed = {}
    for qtype, config in request.question_type_config.items():
        if isinstance(config, dict):
            type_config_parsed[qtype] = {"count": config.get("count", 0), "score": config.get("score", 5.0)}
        else:
            type_config_parsed[qtype] = {"count": config, "score": 5.0}

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
    paper_a = ExamPaper(
        title=f"{request.title} (A卷)",
        subject_id=request.subject_id,
        total_score=request.total_score,
        total_time=request.total_time,
        passing_score=request.passing_score,
        description=request.description or "",
        config={
            "paper_type": "auto_generate_ab",
            "ab_group": "A",
            "knowledge_point_ids": request.knowledge_point_ids,
            "question_type_config": request.question_type_config,
            "difficulty_config": request.difficulty_config,
            "template_id": request.template_id,
            "actual_question_count": len(paper_a_questions),
            "actual_total_score": sum(type_config_parsed.get(q.question_type, {}).get("score", q.score) for q in paper_a_questions),
        },
        status="draft",
        created_by=current_user.id,
    )
    db.add(paper_a)
    db.flush()

    for order, q in enumerate(paper_a_questions):
        configured_score = type_config_parsed.get(q.question_type, {}).get("score", q.score)
        epq = ExamPaperQuestion(exam_paper_id=paper_a.id, question_id=q.id, order=order, score=configured_score)
        db.add(epq)
        q.used_count = (q.used_count or 0) + 1

    # 创建B卷
    paper_b = ExamPaper(
        title=f"{request.title} (B卷)",
        subject_id=request.subject_id,
        total_score=request.total_score,
        total_time=request.total_time,
        passing_score=request.passing_score,
        description=request.description or "",
        config={
            "paper_type": "auto_generate_ab",
            "ab_group": "B",
            "knowledge_point_ids": request.knowledge_point_ids,
            "question_type_config": request.question_type_config,
            "difficulty_config": request.difficulty_config,
            "template_id": request.template_id,
            "actual_question_count": len(paper_b_questions),
            "actual_total_score": sum(type_config_parsed.get(q.question_type, {}).get("score", q.score) for q in paper_b_questions),
        },
        status="draft",
        created_by=current_user.id,
    )
    db.add(paper_b)
    db.flush()

    for order, q in enumerate(paper_b_questions):
        configured_score = type_config_parsed.get(q.question_type, {}).get("score", q.score)
        epq = ExamPaperQuestion(exam_paper_id=paper_b.id, question_id=q.id, order=order, score=configured_score)
        db.add(epq)
        q.used_count = (q.used_count or 0) + 1

    db.commit()

    # 重新加载
    paper_a = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_a.id)
        .first()
    )
    paper_b = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_b.id)
        .first()
    )

    logger.info(f"[AUTO-GEN-AB] A卷 paper_id={paper_a.id}, B卷 paper_id={paper_b.id}")

    return {
        "paper_a": PaperDetailResponse.from_orm_with_status_int(paper_a),
        "paper_b": PaperDetailResponse.from_orm_with_status_int(paper_b),
        "message": f"成功生成A/B两卷，各{len(paper_a_questions)}题"
    }

def _select_questions_by_difficulty(
    available_questions: List[Question], count: int, difficulty_config: dict, questions_by_difficulty: dict
) -> List[Question]:
    """根据难度配置比例从可用题目中选择题目

    Args:
        available_questions: 该题型可用的题目列表
        count: 需要选择的题目数量
        difficulty_config: 难度配置 {"easy": 0.3, "medium": 0.5, "hard": 0.2}
        questions_by_difficulty: 按难度分组的题目 {"easy": [...], "medium": [...], "hard": [...]}

    Returns:
        选中的题目列表
    """
    if not difficulty_config:
        return random.sample(available_questions, count)

    # 计算各难度需要选择的数量
    difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
    ratio_sum = sum(difficulty_config.values())

    for diff, ratio in difficulty_config.items():
        difficulty_counts[diff] = int(count * ratio / ratio_sum)

    # 确保总数正确，分配余数
    actual_total = sum(difficulty_counts.values())
    remainder = count - actual_total
    if remainder > 0:
        # 将余数分配给中等难度
        difficulty_counts["medium"] += remainder

    selected = []
    available_by_diff = {
        "easy": [q for q in available_questions if q.difficulty <= 2],
        "medium": [q for q in available_questions if q.difficulty == 3],
        "hard": [q for q in available_questions if q.difficulty >= 4],
    }

    for diff, need_count in difficulty_counts.items():
        if need_count <= 0:
            continue
        candidates = available_by_diff.get(diff, [])
        # 过滤掉已选中的
        candidates = [q for q in candidates if q not in selected]
        if len(candidates) < need_count:
            # 如果该难度不足，从其他难度补充
            shortfall = need_count - len(candidates)
            selected.extend(candidates)
            # 从其他难度补充
            for other_diff, other_candidates in available_by_diff.items():
                if other_diff == diff:
                    continue
                other_available = [q for q in other_candidates if q not in selected]
                supplement = min(shortfall, len(other_available))
                selected.extend(random.sample(other_available, supplement))
                shortfall -= supplement
                if shortfall <= 0:
                    break
        else:
            selected.extend(random.sample(candidates, need_count))

    # 如果还有不足（极端情况下），用随机补充
    if len(selected) < count:
        remaining = [q for q in available_questions if q not in selected]
        selected.extend(random.sample(remaining, count - len(selected)))

    return selected[:count]

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

