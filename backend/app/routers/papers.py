"""Papers Router - CRUD for exam papers with fixed/random question selection"""
import io
import logging
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.utils.security import get_current_user, require_teacher_or_admin
from app.models.question import ExamPaper, ExamPaperQuestion, Question, Subject, Chapter, ExamType
from app.models import User

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
        used = getattr(q, 'used_count', 0) or 0
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
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx 未安装，Word导出功能将不可用")

# 尝试导入 reportlab (用于PDF生成)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.platypus.flowables import HRFlowable
    PDF_AVAILABLE = True
    # 注册中文字体 - 尝试多种字体以适应不同系统
    import sys
    import os

    # 跨平台字体路径搜索
    font_paths = []

    if sys.platform == 'win32':
        # Windows 系统
        font_paths = [
            ('SimSun', 'C:/Windows/Fonts/simsun.ttc'),
            ('Microsoft YaHei', 'C:/Windows/Fonts/msyh.ttc'),
            ('SimHei', 'C:/Windows/Fonts/simhei.ttf'),
            ('KaiTi', 'C:/Windows/Fonts/kaiti.ttf'),
        ]
    elif sys.platform == 'darwin':
        # macOS 系统
        font_paths = [
            ('SimSun', '/System/Library/Fonts/PingFang.ttc'),
            ('SimSun', '/System/Library/Fonts/STHeiti Light.ttc'),
            ('SimSun', '/Library/Fonts/Arial Unicode.ttf'),
        ]
    else:
        # Linux 系统 - 多种常见字体路径
        font_paths = [
            # 文泉驿字体（最常用）
            ('SimSun', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'),
            ('SimSun', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'),
            # Ubuntu / Debian
            ('SimSun', '/usr/share/fonts/truetype/ubuntu/Ubuntu-LI.ttf'),
            # CentOS / RHEL
            ('SimSun', '/usr/share/fonts/google-droid/DroidSansFallbackFull.ttf'),
            # AR PL linux fonts
            ('SimSun', '/usr/share/fonts/truetype/arphic/uming.ttc'),
            ('SimHei', '/usr/share/fonts/truetype/arphic/bkai00mp.ttf'),
            # Noto Fonts (Google)
            ('SimSun', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
            ('SimHei', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),
        ]

    REGISTERED_FONTS = []
    for font_name, font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                REGISTERED_FONTS.append(font_name)
                logger.info(f"成功注册PDF中文字体: {font_name} from {font_path}")
                break  # 找到一个就够用了
            except Exception as e:
                logger.warning(f"注册字体 {font_name} 失败: {e}")
    if not REGISTERED_FONTS:
        logger.warning("未找到任何中文字体，PDF中文可能显示异常")
except ImportError:
    PDF_AVAILABLE = False
    REGISTERED_FONTS = []
    logger.warning("reportlab 未安装，PDF导出功能将不可用")

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
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any


class QuestionOptionSimpleResponse(BaseModel):
    id: int
    option_label: str
    option_content: str
    is_correct: bool
    order: int

    class Config:
        from_attributes = True


class QuestionInPaperResponse(BaseModel):
    id: int
    chapter_id: int
    subject_id: int
    question_type: str
    content: str
    difficulty: int
    score: float
    answer: Optional[str] = None
    explanation: Optional[str] = None
    options: List[QuestionOptionSimpleResponse] = []

    class Config:
        from_attributes = True


class ExamPaperQuestionResponse(BaseModel):
    id: int
    question_id: int
    order: int
    score: float
    question: QuestionInPaperResponse

    class Config:
        from_attributes = True


class PaperCreateFixed(BaseModel):
    """Create a fixed paper with explicitly selected questions."""
    title: str = Field(..., max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: Optional[str] = None
    questions: List["FixedQuestionItem"] = Field(..., min_length=1)


class FixedQuestionItem(BaseModel):
    question_id: int
    order: int = 0
    score: float = Field(..., ge=0)


class PaperCreateRandom(BaseModel):
    """Create a random paper with question selection rules."""
    title: str = Field(..., max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: Optional[str] = None
    rules: "RandomSelectionRules"


class RandomSelectionRules(BaseModel):
    """Rules for random question selection."""
    chapter_ids: Optional[List[int]] = None
    question_types: Optional[List[str]] = None
    difficulties: Optional[List[int]] = None
    count_per_type: Optional[dict[str, int]] = None
    total_count: int = Field(..., ge=1)


class PaperUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    total_time: Optional[int] = Field(None, ge=1)
    passing_score: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[int] = Field(None, description="0=draft, 1=published, 2=archived")


class PaperResponse(BaseModel):
    id: int
    title: str
    subject_id: int
    total_score: float
    total_time: int
    passing_score: float
    description: Optional[str] = None
    config: Optional[dict] = None
    status: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_status_int(cls, paper: ExamPaper) -> "PaperResponse":
        status_int = STATUS_MAP_STR_TO_INT.get(paper.status, PAPER_STATUS_DRAFT)
        return cls(
            id=paper.id,
            title=paper.title,
            subject_id=paper.subject_id,
            total_score=paper.total_score,
            total_time=paper.total_time,
            passing_score=paper.passing_score,
            description=paper.description,
            config=paper.config,
            status=status_int,
            created_by=paper.created_by,
            created_at=paper.created_at,
            updated_at=paper.updated_at,
        )


class PaperDetailResponse(BaseModel):
    id: int
    title: str
    subject_id: int
    total_score: float
    total_time: int
    passing_score: float
    description: Optional[str] = None
    config: Optional[dict] = None
    status: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    questions: List[ExamPaperQuestionResponse] = []
    shortage_notice: Optional[str] = None  # 题型短缺提示

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_status_int(cls, paper: ExamPaper) -> "PaperDetailResponse":
        status_int = STATUS_MAP_STR_TO_INT.get(paper.status, PAPER_STATUS_DRAFT)
        # 手动转换 ExamPaperQuestion ORM 对象为 ExamPaperQuestionResponse Pydantic 模型
        questions = []
        for epq in paper.exam_paper_questions:
            q = epq.question
            logger.info(f"[DEBUG] question id={q.id}, answer={q.answer}, explanation={q.explanation}")
            questions.append(ExamPaperQuestionResponse(
                id=epq.id,
                question_id=epq.question_id,
                order=epq.order,
                score=epq.score,
                question=QuestionInPaperResponse(
                    id=q.id,
                    chapter_id=q.chapter_id,
                    subject_id=q.subject_id,
                    question_type=q.question_type,
                    content=q.content,
                    difficulty=q.difficulty,
                    score=q.score,
                    answer=q.answer,
                    explanation=q.explanation,
                    options=[
                        QuestionOptionSimpleResponse(
                            id=opt.id,
                            option_label=opt.option_label,
                            option_content=opt.option_content,
                            is_correct=opt.is_correct,
                            order=opt.order
                        ) for opt in q.options
                    ] if q.options else []
                )
            ))
        return cls(
            id=paper.id,
            title=paper.title,
            subject_id=paper.subject_id,
            total_score=paper.total_score,
            total_time=paper.total_time,
            passing_score=paper.passing_score,
            description=paper.description,
            config=paper.config,
            status=status_int,
            created_by=paper.created_by,
            created_at=paper.created_at,
            updated_at=paper.updated_at,
            questions=questions,
        )


class PaperListResponse(BaseModel):
    items: List[PaperResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaperCreateUnion(BaseModel):
    """Union type for paper creation - fixed or random."""
    paper_type: int = Field(..., description="1=fixed, 2=random")
    title: str = Field(..., max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: Optional[str] = None
    # For fixed paper
    questions: Optional[List[FixedQuestionItem]] = None
    # For random paper
    rules: Optional[RandomSelectionRules] = None


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
    category_id: Optional[int] = Query(None, description="Filter by exam category"),
    subject_id: Optional[int] = None,
    status: Optional[int] = Query(None, description="0=draft, 1=published, 2=archived"),
    created_by: Optional[int] = None,
    keyword: Optional[str] = Query(None, description="Search in title"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List exam papers with pagination and filters."""
    query = db.query(ExamPaper)

    # 按考试种类过滤（需要联表查询exam_types）
    if category_id is not None:
        query = query.join(ExamType, ExamPaper.subject_id == ExamType.id).filter(
            ExamType.category_id == category_id
        )

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

    papers = query.order_by(ExamPaper.updated_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

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
                status_code=400,
                detail=f"Question {q.id} does not belong to subject {paper_data.subject_id}"
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
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == paper.id).first()

    return PaperDetailResponse.from_orm_with_status_int(paper)


def _create_random_paper(paper_data: PaperCreateUnion, db: Session, user_id: int) -> PaperDetailResponse:
    """Create a random paper with selection rules."""
    if not paper_data.rules:
        raise HTTPException(status_code=400, detail="Random paper requires rules")

    rules = paper_data.rules

    # Build query for question selection
    query = db.query(Question).filter(
        Question.subject_id == paper_data.subject_id,
        Question.status == "active"
    )

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
            detail=f"Not enough questions available. Required: {rules.total_count}, Available: {len(available_questions)}"
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
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == paper.id).first()

    return PaperDetailResponse.from_orm_with_status_int(paper)


@router.get("/{paper_id}", response_model=PaperDetailResponse)
def get_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an exam paper by ID with its questions."""
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == paper_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

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
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == paper_id).first()

    return PaperDetailResponse.from_orm_with_status_int(paper)


@router.delete("/{paper_id}", status_code=204)
def delete_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Delete an exam paper (hard delete from database)."""
    paper = db.query(ExamPaper).filter(ExamPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # 先删除关联的试卷题目
    db.query(ExamPaperQuestion).filter(ExamPaperQuestion.exam_paper_id == paper_id).delete()
    # 再删除试卷本身
    db.delete(paper)
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
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == paper_id).first()

    return PaperDetailResponse.from_orm_with_status_int(paper)


# ============ Auto Generate Endpoints ============

# 有效题型常量
VALID_QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "essay"}


class AutoGenerateRequest(BaseModel):
    """智能组卷请求"""
    title: str = Field(..., min_length=1, max_length=200)
    subject_id: int
    total_time: int = Field(default=120, ge=1)
    passing_score: float = Field(default=60.0, ge=0)
    description: Optional[str] = None
    template_id: Optional[int] = None
    knowledge_point_ids: Optional[List[int]] = None
    question_type_config: dict = Field(default_factory=dict)  # {"single_choice": 20, "multiple_choice": 10}
    difficulty_config: dict = Field(default_factory=dict)  # {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    total_score: float = Field(default=100.0, ge=0)

    @field_validator('question_type_config')
    @classmethod
    def validate_question_types(cls, v):
        for qtype in v.keys():
            if qtype not in VALID_QUESTION_TYPES:
                raise ValueError(f'无效的题型: {qtype}，有效值为: {VALID_QUESTION_TYPES}')
        for config in v.values():
            # 支持新旧格式: 旧格式 {"single_choice": 20}, 新格式 {"single_choice": {"count": 20, "score": 2}}
            if isinstance(config, dict):
                count = config.get("count", 0)
                if not isinstance(count, (int, float)) or count < 0:
                    raise ValueError('题目数量必须是非负数字')
            else:
                if not isinstance(config, (int, float)) or config < 0:
                    raise ValueError('题目数量必须是非负数字')
        return v

    @field_validator('difficulty_config')
    @classmethod
    def validate_difficulty_config(cls, v):
        valid_difficulties = {"easy", "medium", "hard"}
        for diff in v.keys():
            if diff not in valid_difficulties:
                raise ValueError(f'无效的难度: {diff}，有效值为: {valid_difficulties}')
        for ratio in v.values():
            if not isinstance(ratio, (int, float)) or ratio < 0:
                raise ValueError('难度配置值必须为非负数字')
        return v


class AutoGeneratePreviewRequest(BaseModel):
    """组卷预览请求"""
    subject_id: int
    knowledge_point_ids: Optional[List[int]] = None
    question_type_config: dict = Field(default_factory=dict)
    difficulty_config: dict = Field(default_factory=dict)
    total_score: float = 100.0

    @field_validator('question_type_config')
    @classmethod
    def validate_question_types(cls, v):
        for qtype in v.keys():
            if qtype not in VALID_QUESTION_TYPES:
                raise ValueError(f'无效的题型: {qtype}')
        return v


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
        Question.subject_id == actual_subject_id,
        Question.status == 1,
        Question.audit_status == "approved"
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
        "score_summary": {}
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


class DifficultyDistributionRequest(BaseModel):
    subject_id: int
    question_types: List[str] = []  # 要统计的题型列表
    knowledge_point_ids: List[int] = []  # 知识点ID列表


class DifficultyDistributionResponse(BaseModel):
    total: int = 0
    easy: int = 0
    medium: int = 0
    hard: int = 0
    easy_ratio: float = 0.0  # 可用比例
    medium_ratio: float = 0.0
    hard_ratio: float = 0.0
    suggestions: dict = {}  # 建议的难度分布（每种题型独立）
    by_question_type: dict = {}  # 按题型统计的难度分布


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
        Question.subject_id == actual_subject_id,
        Question.status == 1,
        Question.audit_status == "approved"
    )

    # 知识点过滤
    if request.knowledge_point_ids:
        all_questions = query.all()
        kp_ids_set = set(request.knowledge_point_ids)
        available_questions = [
            q for q in all_questions
            if q.meta and q.meta.get("knowledge_point_ids")
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
                "hard_ratio": hard_suggested
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
        by_question_type=by_question_type
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
        Question.subject_id == actual_subject_id,
        Question.status == 1,
        Question.audit_status == "approved"
    )

    # 如果指定了知识点，先用chapter_id初步过滤，再用meta中的knowledge_point_ids精细过滤
    if request.knowledge_point_ids:
        all_questions = query.all()
        # 从meta字段中解析knowledge_point_ids进行过滤
        kp_ids_set = set(request.knowledge_point_ids)
        available_questions = [
            q for q in all_questions
            if q.meta and q.meta.get("knowledge_point_ids")
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
            status_code=400,
            detail=f"题库中题目数量不足。请求: {total_requested}, 可用: {len(available_questions)}"
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
            allocate_count = min(
                int(actual_count * proportion),
                remaining_count,
                len(questions)
            )
            # 从该知识点选取 - 优先选择使用次数少的题目
            selected = select_questions_by_usage_priority(questions, allocate_count)
            selected_for_type.extend(selected)
            remaining_count -= allocate_count

        # 如果还有剩余，优先选择使用次数少的题目补充
        if remaining_count > 0:
            used_ids = set(q.id for q in selected_for_type)
            remaining_questions = [q for q in all_available if q.id not in used_ids]
            if remaining_questions:
                more = select_questions_by_usage_priority(remaining_questions, min(remaining_count, len(remaining_questions)))
                selected_for_type.extend(more)

        selected_questions.extend(selected_for_type)
        used_question_ids.update(q.id for q in selected_for_type)

    # B1/B2/B3: 检查题目数量是否满足需求，如果不足则尝试补充或报错
    total_requested = sum(cfg["count"] for cfg in type_config_parsed.values())
    if len(selected_questions) < total_requested:
        shortage_count = total_requested - len(selected_questions)
        logger.warning(f"智能组卷题目不足: 请求{total_requested}题，仅获取{len(selected_questions)}题，短缺{shortage_count}题")

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
                detail=f"题库题目不足，无法满足组卷需求。请求: {total_requested}题, 可用: {len(selected_questions)}题, 短缺: {final_shortage}题。详细: {shortage_detail}"
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
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == paper.id).first()

    logger.info(f"[AUTO-GEN] paper_id={paper.id}, exam_paper_questions count={len(paper.exam_paper_questions)}")
    response = PaperDetailResponse.from_orm_with_status_int(paper)
    response.shortage_notice = shortage_notice
    return response


def _select_questions_by_difficulty(
    available_questions: List[Question],
    count: int,
    difficulty_config: dict,
    questions_by_difficulty: dict
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

    return {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "paper_id": paper.id,
        "title": paper.title
    }


class ExportPaperRequest(BaseModel):
    paper_id: int
    format: str = "word"


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
    paper = db.query(ExamPaper).options(
        joinedload(ExamPaper.exam_paper_questions).joinedload(ExamPaperQuestion.question).joinedload(Question.options)
    ).filter(ExamPaper.id == request.paper_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 获取科目信息 - 试卷的 subject_id 关联的是 ExamType 表
    exam_type = db.query(ExamType).filter(ExamType.id == paper.subject_id).first()
    subject_name = exam_type.name if exam_type else "未知科目"

    # 按顺序排列题目
    sorted_questions = sorted(paper.exam_paper_questions, key=lambda x: x.order)

    # 题型名称映射
    q_type_names = {
        "single_choice": "单选题",
        "multiple_choice": "多选题",
        "true_false": "判断题",
        "essay": "简答题"
    }

    # 返回文件流
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote

    # 文件名使用ASCII字符，中文进行URL编码
    safe_title = quote(paper.title or 'paper', safe='')

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

    return StreamingResponse(
        iter([file_content]),
        media_type=media_type,
        headers=headers
    )


def _make_chinese_run(para, text, font_name='SimSun', bold=False, italic=False, font_size=Pt(11)):
    """创建一个支持中文的run"""
    run = para.add_run(text)
    run.font.name = font_name
    run.font.size = font_size
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    if bold:
        run.bold = True
    if italic:
        run.italic = True
    return run


def _generate_word_paper(paper, subject_name, sorted_questions, q_type_names):
    """生成Word试卷文档（职业考试风格：紧凑、选项内嵌、分题型分块）"""
    doc = Document()

    # 设置默认字体
    style = doc.styles['Normal']
    style.font.name = 'SimSun'
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')

    # ========== 试卷标题区 ==========
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(paper.title or "未命名试卷")
    run.font.size = Pt(22)
    run.bold = True
    run.font.name = 'SimSun'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')

    # ========== 试卷信息区 ==========
    info_para = doc.add_paragraph()
    info_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _make_chinese_run(info_para, f"科目：{subject_name}　　", font_size=Pt(12))
    _make_chinese_run(info_para, f"总分：{paper.total_score}分　　", font_size=Pt(12))
    _make_chinese_run(info_para, f"考试时间：{paper.total_time}分钟　　", font_size=Pt(12))
    _make_chinese_run(info_para, f"及格分数：{paper.passing_score}分", font_size=Pt(12))

    # ========== 注意事项区 ==========
    doc.add_paragraph()  # 空行
    notice_para = doc.add_paragraph()
    notice_run = notice_para.add_run("【注意事项】")
    notice_run.bold = True
    notice_run.font.name = 'SimSun'
    notice_run.font.size = Pt(11)
    notice_run._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')

    notice_content = doc.add_paragraph()
    notice_content.paragraph_format.left_indent = Pt(20)
    _make_chinese_run(notice_content, "1. 本试卷包含客观题和主观题，请将答案直接写在试卷相应位置上。", font_size=Pt(10))
    notice_content2 = doc.add_paragraph()
    notice_content2.paragraph_format.left_indent = Pt(20)
    _make_chinese_run(notice_content2, "2. 主观题请在红线框内作答，保持字迹清晰。", font_size=Pt(10))

    doc.add_paragraph()  # 空行

    # ========== 分割线 ==========
    line_para = doc.add_paragraph()
    line_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line_run = line_para.add_run("─" * 60)
    line_run.font.color.rgb = None
    line_run.font.size = Pt(9)

    doc.add_paragraph()  # 空行

    # ========== 题目区分题型分块输出 ==========
    questions_by_type = {}
    for epq in sorted_questions:
        qtype = epq.question.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(epq)

    # 题型顺序
    type_order = ["single_choice", "multiple_choice", "true_false", "essay", "blank", "short_answer"]

    section_num = 1

    for qtype in type_order:
        if qtype not in questions_by_type:
            continue
        questions = questions_by_type[qtype]
        if not questions:
            continue

        type_name = q_type_names.get(qtype, qtype)
        per_score = questions[0].score if questions else 0
        total_score_for_type = sum(epq.score for epq in questions)
        count_for_type = len(questions)

        # ========== 题型标题区 ==========
        section_title = doc.add_paragraph()
        section_run = section_title.add_run(f"{_get_chinese_num(section_num)}、{type_name}（共 {count_for_type} 题，每题 {per_score} 分，共 {total_score_for_type} 分）")
        section_run.bold = True
        section_run.font.name = 'SimSun'
        section_run.font.size = Pt(12)
        section_run._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
        section_title.paragraph_format.space_after = Pt(6)

        # ========== 该题型的所有题目 ==========
        q_index = 1  # 全局题号

        for epq in questions:
            q = epq.question

            # 题目内容（带题号）
            q_para = doc.add_paragraph()
            q_para.paragraph_format.space_after = Pt(3)
            _make_chinese_run(q_para, f"{q_index}. {q.content}", font_size=Pt(11))

            # 选项内嵌显示（选择题）- 紧凑排列
            if q.question_type in ("single_choice", "multiple_choice", "true_false"):
                options = sorted(q.options, key=lambda x: x.order) if q.options else []
                if options:
                    # 一行显示所有选项，更紧凑
                    opt_para = doc.add_paragraph()
                    opt_para.paragraph_format.left_indent = Pt(20)
                    opt_para.paragraph_format.space_after = Pt(6)
                    for opt in options:
                        _make_chinese_run(opt_para, f"[{opt.option_label}] {opt.option_content}   ", font_size=Pt(10))

            # 主观题添加作答区域提示
            if q.question_type in ("essay", "short_answer"):
                answer_space = doc.add_paragraph()
                answer_space.paragraph_format.left_indent = Pt(20)
                answer_space.paragraph_format.space_after = Pt(12)
                # 红色提示线
                answer_run = answer_space.add_run("答：")
                answer_run.font.name = 'SimSun'
                answer_run.font.size = Pt(11)
                answer_run._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')

            q_index += 1

        doc.add_paragraph()  # 题型之间空一行
        section_num += 1

    # ========== 版权水印 ==========
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_para.add_run("智题 AIQuiz © 2024-2026 | 本试卷题目为AI原创模拟题")
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = None
    footer_run.font.name = 'SimSun'
    footer_run._element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')

    return doc


def _get_chinese_num(num):
    """将数字转换为中文数字"""
    cn_nums = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    if num <= 10:
        return cn_nums[num]
    return str(num)


def _generate_pdf_paper(paper, subject_name, sorted_questions, q_type_names):
    """生成PDF试卷文档（职业考试风格：紧凑、选项内嵌、分题型分块）"""
    from reportlab.platypus import PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    # 使用第一个可用的中文字体
    chinese_font = REGISTERED_FONTS[0] if REGISTERED_FONTS else 'Helvetica'
    logger.info(f"生成PDF使用字体: {chinese_font}")

    # 创建PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # 创建样式
    styles = getSampleStyleSheet()

    # 标题样式
    title_style = ParagraphStyle(
        'ChineseTitle',
        parent=styles['Heading1'],
        fontName=chinese_font,
        fontSize=22,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    # 信息样式
    info_style = ParagraphStyle(
        'ChineseInfo',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=6,
    )

    # 注意事项标题样式
    notice_title_style = ParagraphStyle(
        'ChineseNoticeTitle',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=11,
        spaceBefore=12,
        spaceAfter=4,
    )

    # 注意事项内容样式
    notice_style = ParagraphStyle(
        'ChineseNotice',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=10,
        leftIndent=20,
        spaceAfter=3,
    )

    # 题型标题样式
    section_style = ParagraphStyle(
        'ChineseSection',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=12,
        leading=16,
        spaceBefore=15,
        spaceAfter=6,
    )

    # 题目样式
    question_style = ParagraphStyle(
        'ChineseQuestion',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=11,
        leading=15,
        spaceAfter=3,
    )

    # 选项样式（紧凑一行）
    option_style = ParagraphStyle(
        'ChineseOption',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=10,
        leading=14,
        leftIndent=20,
        spaceAfter=6,
    )

    # 主观题答题提示样式
    answer_hint_style = ParagraphStyle(
        'ChineseAnswerHint',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=10,
        leftIndent=20,
        spaceAfter=12,
    )

    # 构建内容
    story = []

    # ========== 试卷标题区 ==========
    story.append(Paragraph(paper.title or "未命名试卷", title_style))

    # ========== 试卷信息区 ==========
    info_text = f"科目：{subject_name}　　总分：{paper.total_score}分　　考试时间：{paper.total_time}分钟　　及格分数：{paper.passing_score}分"
    story.append(Paragraph(info_text, info_style))

    # ========== 注意事项区（根据实际题型动态生成）==========
    has_objective = any(qtype in questions_by_type for qtype in ["single_choice", "multiple_choice", "true_false"])
    has_subjective = any(qtype in questions_by_type for qtype in ["essay", "short_answer"])

    story.append(Spacer(1, 10))
    story.append(Paragraph("【注意事项】", notice_title_style))

    if has_objective and has_subjective:
        story.append(Paragraph("1. 本试卷包含客观题和主观题，请将答案直接写在试卷相应位置上。", notice_style))
        story.append(Paragraph("2. 主观题请在相应区域内作答，保持字迹清晰。", notice_style))
    elif has_objective:
        story.append(Paragraph("1. 本试卷均为客观题，请将答案直接写在试卷相应位置上。", notice_style))
    else:
        story.append(Paragraph("1. 本试卷均为主观题，请在相应区域内作答，保持字迹清晰。", notice_style))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=15))

    # 按题型分组
    questions_by_type = {}
    for epq in sorted_questions:
        qtype = epq.question.question_type
        if qtype not in questions_by_type:
            questions_by_type[qtype] = []
        questions_by_type[qtype].append(epq)

    # 题型顺序映射
    type_order = ["single_choice", "multiple_choice", "true_false", "essay", "blank", "short_answer"]

    section_num = 1

    for qtype in type_order:
        if qtype not in questions_by_type:
            continue
        questions = questions_by_type[qtype]
        if not questions:
            continue

        type_name = q_type_names.get(qtype, qtype)
        total_score_for_type = sum(epq.score for epq in questions)
        per_score = questions[0].score if questions else 0
        count_for_type = len(questions)

        # ========== 题型标题区 ==========
        section_title = f"{_get_chinese_num(section_num)}、{type_name}（共 {count_for_type} 题，每题 {per_score} 分，共 {total_score_for_type} 分）"
        story.append(Paragraph(section_title, section_style))

        q_index = 1

        # ========== 该题型的所有题目 ==========
        for epq in questions:
            q = epq.question

            # 题目内容
            question_text = f"{q_index}. {q.content}"
            story.append(Paragraph(question_text, question_style))

            # 选项内嵌显示（选择题）- 紧凑排列
            if q.question_type in ("single_choice", "multiple_choice", "true_false"):
                options = sorted(q.options, key=lambda x: x.order) if q.options else []
                if options:
                    # 一行显示所有选项
                    opt_text = "   ".join([f"[{opt.option_label}] {opt.option_content}" for opt in options])
                    story.append(Paragraph(opt_text, option_style))

            # 主观题添加作答提示
            if q.question_type in ("essay", "short_answer"):
                story.append(Paragraph("答：________________________", answer_hint_style))

            q_index += 1

        section_num += 1

    # ========== 版权水印 ==========
    footer_style = ParagraphStyle(
        'ChineseFooter',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=9,
        alignment=TA_CENTER,
        spaceBefore=20,
    )
    story.append(Paragraph("智题 AIQuiz © 2024-2026 | 本试卷题目为AI原创模拟题", footer_style))

    # 生成PDF
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer