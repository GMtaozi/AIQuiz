"""智能组卷预览和分析端点。

包含：预览、难度分布、AI 大纲。
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.question import Chapter, ExamType, Question, Subject
from app.schemas.paper import (
    AutoGeneratePreviewRequest,
    DifficultyDistributionRequest,
    DifficultyDistributionResponse,
    PaperOutlineRequest,
    PaperOutlineResponse,
    PaperOutlineSection,
)
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


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
