"""Knowledge Point Model - 知识点数据模型"""
from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Boolean,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.question import Subject


class KnowledgePoint(Base):
    """知识点模型"""
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(50), default="default", nullable=False)  # default, soft_exam, judicial_exam
    exam_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 考试类型代码，如 RUANKAO, JSSFJD
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)  # 科目ID
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1=active, 0=inactive
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 自我关联的父节点
    parent: Mapped["KnowledgePoint | None"] = relationship(
        "KnowledgePoint",
        remote_side=[id],
        back_populates="children",
        foreign_keys=[parent_id]
    )
    # 子节点
    children: Mapped[list["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        back_populates="parent",
        foreign_keys=[parent_id],
        cascade="all, delete-orphan"
    )
    # 创建者
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('idx_knowledge_category', 'category'),
        Index('idx_knowledge_exam_type', 'exam_type'),
        Index('idx_knowledge_parent_id', 'parent_id'),
    )
