"""
Question-Related Models

Based on architecture documentation for the examination system:
- Subject, Chapter: Subject and chapter structure
- Question, QuestionOption: Question and its options
- ExamPaper, ExamPaperQuestion: Exam paper and question associations
- ExamRecord, UserAnswer: Exam records and user answers
- AIPromptTemplate, AICallLog: AI service integration
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subject(Base):
    """Subject model representing a subject/course."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapters: Mapped[list["Chapter"]] = relationship(back_populates="subject")


class ExamCategory(Base):
    """ExamCategory model representing a category of examination (考试种类，如软考、司法鉴定)."""

    __tablename__ = "exam_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ExamType(Base):
    """ExamType model representing a type/subject of examination (考试科目，如网络管理员、网络工程师)."""

    __tablename__ = "exam_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("exam_categories.id"), nullable=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)  # 关联的科目ID
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 级别：初级、中级、高级
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=120, nullable=False)  # minutes
    total_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    passing_score: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)
    question_types: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关联考试种类
    category: Mapped["ExamCategory | None"] = relationship("ExamCategory", foreign_keys=[category_id])
    # 关联科目
    subject: Mapped["Subject | None"] = relationship("Subject", foreign_keys=[subject_id])


class Chapter(Base):
    """Chapter model representing a chapter within a subject."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subject: Mapped["Subject"] = relationship(back_populates="chapters")
    questions: Mapped[list["Question"]] = relationship(back_populates="chapter")


class Question(Base):
    """Question model representing an exam question."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # single_choice, multiple_choice, true_false, essay
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1-5
    score: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 是否AI生成
    source: Mapped[str] = mapped_column(
        String(20), default="system", nullable=False
    )  # 来源：system=系统原有, ai=AI生成, import=手动导入
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 被试卷使用次数（用于去重）
    audit_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending/approved/rejected
    audit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # 驳回原因
    audited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 审核人
    audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 审核时间
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped["Chapter"] = relationship(back_populates="questions")
    auditor: Mapped["User"] = relationship("User", foreign_keys=[audited_by])
    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuestionOption(Base):
    """Question option model representing a choice in a question."""

    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    option_label: Mapped[str] = mapped_column(String(10), nullable=False)  # A, B, C, D
    option_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question: Mapped["Question"] = relationship(back_populates="options")


class ExamPaper(Base):
    """Exam paper model representing a complete exam."""

    __tablename__ = "exam_papers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    total_time: Mapped[int] = mapped_column(Integer, default=120, nullable=False)  # minutes
    passing_score: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft, published, archived
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    exam_records: Mapped[list["ExamRecord"]] = relationship(back_populates="exam_paper")
    exam_paper_questions: Mapped[list["ExamPaperQuestion"]] = relationship(
        back_populates="exam_paper", cascade="all, delete-orphan"
    )
    versions: Mapped[list["PaperVersion"]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class ExamPaperQuestion(Base):
    """Association model between exam paper and questions."""

    __tablename__ = "exam_paper_questions"
    __table_args__ = (Index("idx_exam_paper_question_unique", "exam_paper_id", "question_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    exam_paper_id: Mapped[int] = mapped_column(ForeignKey("exam_papers.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    exam_paper: Mapped["ExamPaper"] = relationship(back_populates="exam_paper_questions")
    question: Mapped["Question"] = relationship()


class ExamRecord(Base):
    """Exam record model representing a student's exam attempt."""

    __tablename__ = "exam_records"
    __table_args__ = (
        Index("idx_exam_record_user_status", "user_id", "status"),
        Index("idx_exam_record_paper_id", "exam_paper_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    exam_paper_id: Mapped[int] = mapped_column(ForeignKey("exam_papers.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress", nullable=False
    )  # in_progress, submitted, graded
    answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    exam_paper: Mapped["ExamPaper"] = relationship(back_populates="exam_records")
    user_answers: Mapped[list["UserAnswer"]] = relationship(back_populates="exam_record")


class UserAnswer(Base):
    """User answer model representing a student's answer to a question."""

    __tablename__ = "user_answers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    exam_record_id: Mapped[int] = mapped_column(ForeignKey("exam_records.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    answer_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    exam_record: Mapped["ExamRecord"] = relationship(back_populates="user_answers")
    grader: Mapped["User | None"] = relationship("User", foreign_keys=[graded_by])


class AIPromptTemplate(Base):
    """AI prompt template model for storing reusable AI prompts."""

    __tablename__ = "ai_prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)  # question_generation, grading, explanation
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(String(50), default="gpt-3.5-turbo", nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AICallLog(Base):
    """AI call log model for tracking AI API usage."""

    __tablename__ = "ai_call_logs"
    __table_args__ = (
        Index("idx_ai_call_log_user_id", "user_id"),
        Index("idx_ai_call_log_template_id", "template_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("ai_prompt_templates.id"), nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    call_status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GenerationTask(Base):
    """异步出题任务表 — 解决前端长时间等待问题"""

    __tablename__ = "generation_tasks"
    __table_args__ = (Index("idx_generation_task_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending → running → completed / failed
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 0-100
    mode: Mapped[str] = mapped_column(String(20), default="hybrid", nullable=False)
    # hybrid / rule_only / ai_only
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 出题参数快照
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 生成结果（题目列表 + 统计）
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 评估修复：total_questions 列此前缺失，但 tasks.py 读写该字段（任务进度接口 500）
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditLog(Base):
    """审核日志表 - 记录题目审核的完整审计轨迹"""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("idx_audit_log_question_id", "question_id"), Index("idx_audit_log_auditor_id", "auditor_id"))

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    auditor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # approved / rejected / reverted
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    question: Mapped["Question"] = relationship("Question", foreign_keys=[question_id])
    auditor: Mapped["User"] = relationship("User", foreign_keys=[auditor_id])
