"""Knowledge Point Model - 知识点数据模型

三层架构：
- KnowledgeBase（知识库）：归属容器，存全文 + 元数据
- KnowledgeEntry（知识条目）：原文分块，1000-3000 字/块，按章节切分
- KnowledgePoint（知识点）：细粒度知识节点，树形结构，出题单元
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeBase(Base):
    """知识库模型 - 知识的归属容器，存储原始文档全文与元数据。"""

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(50), default="default", nullable=False)  # default, soft_exam, judicial_exam
    exam_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 考试类型代码，如 RUANKAO, JSSFJD
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)  # private/shared/public
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 原始文件名
    source_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # 解析后全文
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1=active, 0=inactive
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关联条目（按章节切分的原文块）
    entries: Mapped[list["KnowledgeEntry"]] = relationship(
        "KnowledgeEntry", back_populates="knowledge_base", cascade="all, delete-orphan", foreign_keys="KnowledgeEntry.knowledge_base_id"
    )
    # 关联知识点（从该知识库提取出的知识点树）
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        "KnowledgePoint", back_populates="knowledge_base", foreign_keys="KnowledgePoint.knowledge_base_id"
    )
    # 创建者
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_kb_category", "category"),
        Index("idx_kb_exam_type", "exam_type"),
    )


class KnowledgeEntry(Base):
    """知识条目模型 - 原文分块，每块 1000-3000 字，按章节/标题切分。"""

    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 分块正文，1000-3000 字
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_location: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 章节/页码定位，如 "第3章" / "## 数据结构基础"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 所属知识库
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", back_populates="entries", foreign_keys=[knowledge_base_id]
    )
    # 从该条目提取的知识点
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        "KnowledgePoint", back_populates="entry", foreign_keys="KnowledgePoint.entry_id"
    )


class KnowledgePoint(Base):
    """知识点模型"""

    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(
        String(50), default="default", nullable=False
    )  # default, soft_exam, judicial_exam
    exam_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 考试类型代码，如 RUANKAO, JSSFJD
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)  # 科目ID
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)  # 原文片段，出题时携带给 LLM
    knowledge_base_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_bases.id"), nullable=True, index=True
    )  # 所属知识库
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_entries.id"), nullable=True, index=True
    )  # 来源条目（原文分块）
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1=active, 0=inactive
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 自我关联的父节点
    parent: Mapped["KnowledgePoint | None"] = relationship(
        "KnowledgePoint", remote_side=[id], back_populates="children", foreign_keys=[parent_id]
    )
    # 子节点
    children: Mapped[list["KnowledgePoint"]] = relationship(
        "KnowledgePoint", back_populates="parent", foreign_keys=[parent_id], cascade="all, delete-orphan"
    )
    # 所属知识库
    knowledge_base: Mapped["KnowledgeBase | None"] = relationship(
        "KnowledgeBase", back_populates="knowledge_points", foreign_keys=[knowledge_base_id]
    )
    # 来源条目
    entry: Mapped["KnowledgeEntry | None"] = relationship(
        "KnowledgeEntry", back_populates="knowledge_points", foreign_keys=[entry_id]
    )
    # 创建者
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_knowledge_category", "category"),
        Index("idx_knowledge_exam_type", "exam_type"),
    )
