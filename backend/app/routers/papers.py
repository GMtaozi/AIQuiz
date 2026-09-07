"""Papers Router - CRUD for exam papers with fixed/random question selection

评估 P2-1：智能组卷/预览/大纲/A-B 卷端点已抽取到 papers_generate 模块。
"""

from datetime import datetime
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User
from app.models.question import Chapter, ExamPaper, ExamPaperQuestion, ExamType, Question, Subject
from app.routers.papers_generate import (
    DOCX_AVAILABLE,
    PDF_AVAILABLE,
    _generate_pdf_paper,
    _generate_word_paper,
)
from app.routers.papers_generate import (
    router as papers_generate_router,
)
from app.schemas.paper import (
    ExportPaperRequest,
    FixedQuestionItem,
    PaperCreateFixed,
    PaperCreateRandom,
    PaperCreateUnion,
    PaperDetailResponse,
    PaperListResponse,
    PaperResponse,
    PaperUpdate,
    RandomSelectionRules,
    SimilarityCheckRequest,
    SimilarityCheckResponse,
    SimilarQuestionPair,
)
from app.utils.security import get_current_user, require_teacher_or_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# 评估 P2-1/路由顺序修复：先生成组卷子路由（/auto-generate/*、/generate/{task_id}/progress
# 等静态/前缀路径）必须先于 /{paper_id} 注册，否则会被参数路由遮蔽（此前
# GET /generate/{task_id}/progress 被 GET /{paper_id} 遮蔽导致 422）。
router.include_router(papers_generate_router)

# Paper type constants
PAPER_TYPE_FIXED = 1
PAPER_TYPE_RANDOM = 2

# Paper status constants (using int as per user spec)
PAPER_STATUS_DRAFT = 0
PAPER_STATUS_PUBLISHED = 1
PAPER_STATUS_ARCHIVED = 2

STATUS_MAP_INT_TO_STR = {
    PAPER_STATUS_DRAFT: "draft",
    PAPER_STATUS_PUBLISHED: "published",
    PAPER_STATUS_ARCHIVED: "archived",
}
STATUS_MAP_STR_TO_INT = {
    "draft": PAPER_STATUS_DRAFT,
    "published": PAPER_STATUS_PUBLISHED,
    "archived": PAPER_STATUS_ARCHIVED,
}

# --- Schemas ---

# Update forward references
PaperCreateFixed.model_rebuild()
FixedQuestionItem.model_rebuild()
PaperCreateRandom.model_rebuild()
RandomSelectionRules.model_rebuild()

# --- Endpoints ---

@router.get("/", response_model=PaperListResponse)
def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: int | None = Query(None, description="Filter by exam category"),
    subject_id: int | None = None,
    status: int | None = Query(None, description="0=draft, 1=published, 2=archived"),
    created_by: int | None = None,
    keyword: str | None = Query(None, description="Search in title"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List exam papers with pagination and filters."""
    query = db.query(ExamPaper)

    # 按考试种类过滤（需要联表查询exam_types）
    if category_id is not None:
        query = query.join(ExamType, ExamPaper.subject_id == ExamType.id).filter(ExamType.category_id == category_id)

    if subject_id is not None:
        query = query.filter(ExamPaper.subject_id == subject_id)
    if status is not None:
        status_str = STATUS_MAP_INT_TO_STR.get(status)
        if status_str:
            query = query.filter(ExamPaper.status == status_str)
    if created_by is not None:
        query = query.filter(ExamPaper.created_by == created_by)
    if keyword:
        query = query.filter(ExamPaper.title.contains(keyword))

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    papers = query.order_by(ExamPaper.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return PaperListResponse(
        items=[PaperResponse.from_orm_with_status_int(p) for p in papers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

@router.post("/", response_model=PaperDetailResponse, status_code=201)
def create_paper(
    paper_data: PaperCreateUnion,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Create a new exam paper.

    - **paper_type=1 (fixed)**: Provide explicit `questions` list with question_id, order, score
    - **paper_type=2 (random)**: Provide `rules` for random question selection
    """
    # Validate subject exists
    subject = db.query(Subject).filter(Subject.id == paper_data.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    user_id = current_user.id

    if paper_data.paper_type == PAPER_TYPE_FIXED:
        return _create_fixed_paper(paper_data, db, user_id)
    elif paper_data.paper_type == PAPER_TYPE_RANDOM:
        return _create_random_paper(paper_data, db, user_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid paper_type: must be 1 (fixed) or 2 (random)")

def _create_fixed_paper(paper_data: PaperCreateUnion, db: Session, user_id: int) -> PaperDetailResponse:
    """Create a fixed paper with explicitly selected questions."""
    if not paper_data.questions:
        raise HTTPException(status_code=400, detail="Fixed paper requires questions list")

    # Validate all question IDs and calculate total score
    question_ids = [q.question_id for q in paper_data.questions]
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    question_map = {q.id: q for q in questions}

    if len(questions) != len(question_ids):
        found_ids = set(question_map.keys())
        missing = set(question_ids) - found_ids
        raise HTTPException(status_code=404, detail=f"Questions not found: {missing}")

    # Verify all questions belong to the same subject
    for q in questions:
        if q.subject_id != paper_data.subject_id:
            raise HTTPException(
                status_code=400, detail=f"Question {q.id} does not belong to subject {paper_data.subject_id}"
            )

    total_score = sum(q.score for q in paper_data.questions)

    # Create paper
    paper = ExamPaper(
        title=paper_data.title,
        subject_id=paper_data.subject_id,
        total_score=total_score,
        total_time=paper_data.total_time,
        passing_score=paper_data.passing_score,
        description=paper_data.description,
        config={"paper_type": PAPER_TYPE_FIXED},
        status="draft",
        created_by=user_id,
    )
    db.add(paper)
    db.flush()

    # Create paper-question associations
    for q_item in paper_data.questions:
        epq = ExamPaperQuestion(
            exam_paper_id=paper.id,
            question_id=q_item.question_id,
            order=q_item.order,
            score=q_item.score,
        )
        db.add(epq)

    db.commit()
    db.refresh(paper)

    # Reload with questions
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

    return PaperDetailResponse.from_orm_with_status_int(paper)

def _create_random_paper(paper_data: PaperCreateUnion, db: Session, user_id: int) -> PaperDetailResponse:
    """Create a random paper with selection rules."""
    if not paper_data.rules:
        raise HTTPException(status_code=400, detail="Random paper requires rules")

    rules = paper_data.rules

    # Build query for question selection
    # 注意：Question.status 是 Integer 列（1=启用），不能用字符串 "active" 比较
    query = db.query(Question).filter(Question.subject_id == paper_data.subject_id, Question.status == 1)

    if rules.chapter_ids:
        query = query.filter(Question.chapter_id.in_(rules.chapter_ids))
    if rules.question_types:
        query = query.filter(Question.question_type.in_(rules.question_types))
    if rules.difficulties:
        query = query.filter(Question.difficulty.in_(rules.difficulties))

    available_questions = query.all()

    if len(available_questions) < rules.total_count:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough questions available. Required: {rules.total_count}, Available: {len(available_questions)}",
        )

    # Select random questions
    import random

    selected = random.sample(available_questions, rules.total_count)

    # Calculate total score
    total_score = sum(q.score for q in selected)

    # Store rules in config
    config = {
        "paper_type": PAPER_TYPE_RANDOM,
        "rules": {
            "chapter_ids": rules.chapter_ids,
            "question_types": rules.question_types,
            "difficulties": rules.difficulties,
            "count_per_type": rules.count_per_type,
            "total_count": rules.total_count,
        },
        "selected_question_ids": [q.id for q in selected],
    }

    # Create paper
    paper = ExamPaper(
        title=paper_data.title,
        subject_id=paper_data.subject_id,
        total_score=total_score,
        total_time=paper_data.total_time,
        passing_score=paper_data.passing_score,
        description=paper_data.description,
        config=config,
        status="draft",
        created_by=user_id,
    )
    db.add(paper)
    db.flush()

    # Create paper-question associations
    for order, q in enumerate(selected):
        epq = ExamPaperQuestion(
            exam_paper_id=paper.id,
            question_id=q.id,
            order=order,
            score=q.score,
        )
        db.add(epq)

    db.commit()
    db.refresh(paper)

    # Reload with questions
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

    return PaperDetailResponse.from_orm_with_status_int(paper)

@router.get("/{paper_id}", response_model=PaperDetailResponse)
def get_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an exam paper by ID with its questions."""
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_id)
        .first()
    )

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # 评估 P1-10 修复：未发布（草稿/归档）试卷仅创建者/管理员可见，
    # 防止任意登录用户遍历 paper_id 读取他人草稿卷的答案与解析
    if paper.status != "published" and current_user.role != 1 and paper.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该试卷")

    return PaperDetailResponse.from_orm_with_status_int(paper)

@router.put("/{paper_id}", response_model=PaperDetailResponse)
def update_paper(
    paper_id: int,
    paper_data: PaperUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Update an exam paper. Cannot update questions of a published paper."""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.status == "published":
        raise HTTPException(status_code=400, detail="Cannot update a published paper")

    update_data = paper_data.model_dump(exclude_unset=True)

    # Convert status int to string if provided
    if "status" in update_data and update_data["status"] is not None:
        status_str = STATUS_MAP_INT_TO_STR.get(update_data["status"])
        if status_str:
            update_data["status"] = status_str

    # Recalculate total_score if questions changed (only for draft papers)
    if "questions" in update_data and paper.status == "draft":
        raise HTTPException(status_code=400, detail="Use dedicated endpoint to modify questions on draft papers")

    for field, value in update_data.items():
        if field != "questions":
            setattr(paper, field, value)

    db.commit()
    db.refresh(paper)

    # Reload with questions
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_id)
        .first()
    )

    return PaperDetailResponse.from_orm_with_status_int(paper)

@router.delete("/{paper_id}", status_code=204)
def delete_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Archive an exam paper (soft delete)."""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.status = "archived"
    db.commit()
    return None

@router.post("/{paper_id}/publish", response_model=PaperDetailResponse)
def publish_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Publish an exam paper (change status from draft to published). Teacher/admin only."""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.status == "published":
        raise HTTPException(status_code=400, detail="Paper is already published")

    if paper.status == "archived":
        raise HTTPException(status_code=400, detail="Cannot publish an archived paper")

    # Check that paper has at least one question
    if not paper.exam_paper_questions:
        raise HTTPException(status_code=400, detail="Paper must have at least one question")

    paper.status = "published"
    db.commit()
    db.refresh(paper)

    # Reload with questions
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_id)
        .first()
    )

    return PaperDetailResponse.from_orm_with_status_int(paper)

# ============ Auto Generate Endpoints ============

# 有效题型常量
VALID_QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "essay"}

@router.post("/export")
def export_paper(
    request: ExportPaperRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出试卷为Word或PDF文档
    - Word格式：不包含答案和解析（用于打印给学生做）
    - PDF格式：包含答案和解析
    """
    if request.format not in ("word", "pdf"):
        raise HTTPException(status_code=400, detail="不支持的导出格式，仅支持 word 和 pdf")

    if request.format == "word" and not DOCX_AVAILABLE:
        raise HTTPException(status_code=500, detail="Word导出功能未安装，请联系管理员")

    if request.format == "pdf" and not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF导出功能未安装，请联系管理员")

    # 获取试卷详情
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == request.paper_id)
        .first()
    )

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 获取科目信息 - 试卷的 subject_id 关联的是 ExamType 表
    exam_type = db.query(ExamType).filter(ExamType.id == paper.subject_id).first()
    subject_name = exam_type.name if exam_type else "未知科目"

    # 按顺序排列题目
    sorted_questions = sorted(paper.exam_paper_questions, key=lambda x: x.order)

    # 题型名称映射
    q_type_names = {"single_choice": "单选题", "multiple_choice": "多选题", "true_false": "判断题", "essay": "简答题"}

    # 返回文件流
    from urllib.parse import quote

    # 文件名使用ASCII字符，中文进行URL编码
    safe_title = quote(paper.title or "paper", safe="")

    if request.format == "word":
        # 生成Word文档
        doc = _generate_word_paper(paper, subject_name, sorted_questions, q_type_names)

        # 保存到字节流
        doc_bytes = io.BytesIO()
        doc.save(doc_bytes)
        doc_bytes.seek(0)

        filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        file_content = doc_bytes.getvalue()
    else:
        # 生成PDF文档
        pdf_buffer = _generate_pdf_paper(paper, subject_name, sorted_questions, q_type_names)
        filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        media_type = "application/pdf"
        file_content = pdf_buffer.getvalue()

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
    }

    return StreamingResponse(iter([file_content]), media_type=media_type, headers=headers)

@router.get("/{paper_id}/analysis")
def get_paper_analysis(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取试卷分析报告 - 知识点覆盖度、难度分布、题型统计"""
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_id)
        .first()
    )

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    sorted_questions = sorted(paper.exam_paper_questions, key=lambda x: x.order)

    # 基础统计
    total_questions = len(sorted_questions)
    total_score = paper.total_score
    actual_total_score = sum(epq.score for epq in sorted_questions)

    # 题型统计
    type_stats = {}
    for epq in sorted_questions:
        qtype = epq.question.question_type
        if qtype not in type_stats:
            type_stats[qtype] = {"count": 0, "score": 0}
        type_stats[qtype]["count"] += 1
        type_stats[qtype]["score"] += epq.score

    # 难度统计
    difficulty_stats = {"easy": 0, "medium": 0, "hard": 0}
    for epq in sorted_questions:
        diff = epq.question.difficulty
        if diff <= 2:
            difficulty_stats["easy"] += 1
        elif diff == 3:
            difficulty_stats["medium"] += 1
        else:
            difficulty_stats["hard"] += 1

    # 知识点统计
    knowledge_point_stats = {}
    for epq in sorted_questions:
        kp_ids = []
        if epq.question.meta and epq.question.meta.get("knowledge_point_ids"):
            kp_ids = epq.question.meta.get("knowledge_point_ids", [])
        
        for kp_id in kp_ids:
            if kp_id not in knowledge_point_stats:
                knowledge_point_stats[kp_id] = {"count": 0, "score": 0}
            knowledge_point_stats[kp_id]["count"] += 1
            knowledge_point_stats[kp_id]["score"] += epq.score

    # 计算覆盖率（如果配置了知识点）
    coverage_rate = 0
    selected_kp_ids = []
    if paper.config and paper.config.get("knowledge_point_ids"):
        selected_kp_ids = paper.config.get("knowledge_point_ids", [])
        if selected_kp_ids:
            covered_kp_ids = set(knowledge_point_stats.keys())
            selected_kp_set = set(selected_kp_ids)
            coverage_rate = len(covered_kp_ids & selected_kp_set) / len(selected_kp_set) * 100

    # 预估完成时间（简单估算：单选题1分钟/题，多选题2分钟/题，判断题0.5分钟/题，简答题5分钟/题）
    time_estimates = {
        "single_choice": 1,
        "multiple_choice": 2,
        "true_false": 0.5,
        "essay": 5
    }
    estimated_time = sum(
        time_estimates.get(epq.question.question_type, 2)
        for epq in sorted_questions
    )

    # ========== 高级分析指标 ==========

    # 1. 区分度 (discrimination_index): 0-10
    # 基于难度分布的离散程度：中等+难题占比越高、简单题占比越低，区分度越高
    if total_questions > 0:
        raw_discrimination = (
            difficulty_stats["hard"] * 1.0
            + difficulty_stats["medium"] * 0.6
            - difficulty_stats["easy"] * 0.3
        ) / total_questions
        discrimination_index = round(max(0.0, min(10.0, raw_discrimination * 10)), 2)
    else:
        discrimination_index = 0.0

    # 2. 预估通过率 (predicted_pass_rate): 0-100
    # 基于难度分布和及格线/总分的相对位置
    if total_questions > 0 and total_score > 0:
        easy_ratio = difficulty_stats["easy"] / total_questions
        medium_ratio = difficulty_stats["medium"] / total_questions
        hard_ratio = difficulty_stats["hard"] / total_questions

        # 基础通过率 70%，按难度分布调整
        predicted_pass_rate = 70 + (easy_ratio * 15) - (hard_ratio * 25)
        predicted_pass_rate = max(0.0, min(100.0, round(predicted_pass_rate, 1)))
    else:
        predicted_pass_rate = 0.0

    # 3. 知识点掌握度 (knowledge_mastery)
    # 每个知识点的题目数量 + 平均难度 + 掌握度评级
    knowledge_mastery = []
    for kp_id, stats in knowledge_point_stats.items():
        count = stats["count"]
        score = stats["score"]

        # 收集该知识点下所有题目的难度
        kp_questions = []
        for epq in sorted_questions:
            kp_ids_in_question = []
            if epq.question.meta and epq.question.meta.get("knowledge_point_ids"):
                kp_ids_in_question = epq.question.meta.get("knowledge_point_ids", [])
            if kp_id in kp_ids_in_question:
                kp_questions.append(epq.question.difficulty)

        if kp_questions:
            avg_difficulty = sum(kp_questions) / len(kp_questions)
        else:
            avg_difficulty = 3.0  # 默认中等难度

        # 掌握度评级
        if avg_difficulty <= 2.0 and count >= 3:
            mastery_level = "high"
        elif avg_difficulty <= 3.0 or count >= 2:
            mastery_level = "medium"
        else:
            mastery_level = "low"

        knowledge_mastery.append({
            "knowledge_point_id": kp_id,
            "count": count,
            "score": score,
            "avg_difficulty": round(avg_difficulty, 1),
            "mastery_level": mastery_level
        })

    # 4. 综合质量分 (quality_score): 0-100
    # 综合覆盖率、难度平衡度、区分度、题型丰富度
    quality_score = 0.0
    if total_questions > 0:
        # 覆盖率得分 (0-100)
        coverage_score = min(100.0, coverage_rate * 1.2)

        # 难度平衡度得分 (0-100)
        # 理想分布：easy 30%, medium 50%, hard 20%
        ideal = {"easy": 30.0, "medium": 50.0, "hard": 20.0}
        actual = {
            "easy": difficulty_stats["easy"] / total_questions * 100,
            "medium": difficulty_stats["medium"] / total_questions * 100,
            "hard": difficulty_stats["hard"] / total_questions * 100,
        }
        difficulty_balance_score = 100 - (
            abs(actual["easy"] - ideal["easy"])
            + abs(actual["medium"] - ideal["medium"])
            + abs(actual["hard"] - ideal["hard"])
        ) / 3
        difficulty_balance_score = max(0.0, min(100.0, round(difficulty_balance_score, 1)))

        # 区分度得分 (0-100)
        discrimination_score = min(100.0, max(0.0, discrimination_index * 10))

        # 题型丰富度得分 (0-100)
        type_count = len(type_stats)
        type_richness_score = min(100.0, (type_count / 4) * 100)

        # 加权综合
        quality_score = round(
            coverage_score * 0.30
            + difficulty_balance_score * 0.25
            + discrimination_score * 0.25
            + type_richness_score * 0.20,
            1
        )
        quality_score = max(0.0, min(100.0, quality_score))

    return {
        "paper_id": paper.id,
        "paper_title": paper.title,
        "total_questions": total_questions,
        "total_score": total_score,
        "actual_total_score": actual_total_score,
        "estimated_time": round(estimated_time, 1),
        "coverage_rate": round(coverage_rate, 1),
        "selected_knowledge_points": selected_kp_ids,
        "covered_knowledge_points": list(knowledge_point_stats.keys()),
        "type_stats": type_stats,
        "difficulty_stats": difficulty_stats,
        "knowledge_point_stats": knowledge_point_stats,
        "difficulty_distribution": {
            "easy": round(difficulty_stats["easy"] / total_questions * 100, 1) if total_questions > 0 else 0,
            "medium": round(difficulty_stats["medium"] / total_questions * 100, 1) if total_questions > 0 else 0,
            "hard": round(difficulty_stats["hard"] / total_questions * 100, 1) if total_questions > 0 else 0,
        },
        "score_distribution": {
            qtype: stats["score"]
            for qtype, stats in type_stats.items()
        },
        # 高级分析指标
        "discrimination_index": discrimination_index,
        "predicted_pass_rate": predicted_pass_rate,
        "knowledge_mastery": knowledge_mastery,
        "quality_score": quality_score,
    }

def _compute_text_similarity(text_a: str, text_b: str) -> float:
    """简单文本相似度：基于最长公共子串比例和共有词比例"""
    if not text_a or not text_b:
        return 0.0

    text_a = text_a.strip().lower()
    text_b = text_b.strip().lower()

    # 计算共有字符数（简单版）
    common_chars = sum(1 for c in text_a if c in text_b)
    max_len = max(len(text_a), len(text_b))
    if max_len == 0:
        return 0.0
    char_similarity = common_chars / max_len

    # 计算共有词比例
    words_a = set(text_a.split())
    words_b = set(text_b.split())
    if words_a and words_b:
        word_overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    else:
        word_overlap = 0.0

    # 综合相似度
    return round((char_similarity * 0.4 + word_overlap * 0.6), 3)

@router.post("/{paper_id}/similarity-check", response_model=SimilarityCheckResponse)
def check_question_similarity(
    paper_id: int,
    request: SimilarityCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """题目相似度检测：检查试卷中是否存在相似/重复题目

    基于以下维度判断相似度：
    1. 知识点重叠度（相同知识点数量 / 并集数量）
    2. 题型一致性
    3. 内容文本相似度

    返回相似度超过阈值的题目对
    """
    paper = (
        db.query(ExamPaper)
        .options(
            joinedload(ExamPaper.exam_paper_questions)
            .joinedload(ExamPaperQuestion.question)
            .joinedload(Question.options)
        )
        .filter(ExamPaper.id == paper_id)
        .first()
    )

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    sorted_questions = sorted(paper.exam_paper_questions, key=lambda x: x.order)

    if len(sorted_questions) < 2:
        return SimilarityCheckResponse(
            paper_id=paper_id,
            total_checked=len(sorted_questions),
            similar_pairs_count=0,
            similar_pairs=[],
            message="题目数量不足，无需检测"
        )

    # 构建题目信息列表
    questions_info = []
    for epq in sorted_questions:
        q = epq.question
        kp_ids = []
        if q.meta and q.meta.get("knowledge_point_ids"):
            kp_ids = q.meta.get("knowledge_point_ids", [])

        questions_info.append({
            "id": q.id,
            "content": q.content or "",
            "question_type": q.question_type,
            "knowledge_point_ids": kp_ids,
        })

    # 两两比较
    similar_pairs = []
    total_checked = len(questions_info)

    for i in range(total_checked):
        for j in range(i + 1, total_checked):
            q_a = questions_info[i]
            q_b = questions_info[j]

            # 题型必须相同
            if q_a["question_type"] != q_b["question_type"]:
                continue

            # 计算知识点重叠度
            kp_a = set(q_a["knowledge_point_ids"])
            kp_b = set(q_b["knowledge_point_ids"])
            kp_union = kp_a | kp_b
            kp_overlap = kp_a & kp_b

            if len(kp_union) == 0:
                kp_similarity = 0.0
            else:
                kp_similarity = len(kp_overlap) / len(kp_union)

            # 计算内容相似度
            content_similarity = _compute_text_similarity(q_a["content"], q_b["content"])

            # 综合相似度（知识点权重40%，内容权重60%）
            overall_similarity = round(kp_similarity * 0.4 + content_similarity * 0.6, 3)

            if overall_similarity >= request.threshold:
                # 生成相似原因说明
                reasons = []
                if kp_similarity >= 0.5:
                    overlap_ids = list(kp_overlap)
                    reasons.append(f"知识点重叠({len(kp_overlap)}/{len(kp_union)})")
                if content_similarity >= 0.3:
                    reasons.append("内容相似")
                if not reasons:
                    reasons.append(f"综合相似度{overall_similarity}")

                similar_pairs.append(SimilarQuestionPair(
                    question_a_id=q_a["id"],
                    question_a_content=q_a["content"][:200],
                    question_b_id=q_b["id"],
                    question_b_content=q_b["content"][:200],
                    question_type=q_a["question_type"],
                    knowledge_point_ids=list(kp_overlap),
                    similarity_score=overall_similarity,
                    similarity_reason="；".join(reasons)
                ))

    # 按相似度降序排序
    similar_pairs.sort(key=lambda x: x.similarity_score, reverse=True)

    message = None
    if not similar_pairs:
        message = f"未发现相似度超过 {request.threshold} 的题目对，试卷质量良好"

    return SimilarityCheckResponse(
        paper_id=paper_id,
        total_checked=total_checked,
        similar_pairs_count=len(similar_pairs),
        similar_pairs=similar_pairs,
        message=message
    )

