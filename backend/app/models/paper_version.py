"""Paper Version Model - 试卷版本管理"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PaperVersion(Base):
    """试卷版本模型"""

    __tablename__ = "paper_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # 试卷配置快照
    config = Column(JSON, nullable=True)
    # 题目列表快照（简化版，用于对比）
    questions_snapshot = Column(JSON, nullable=True)
    # 变更日志
    change_log = Column(Text, nullable=True)
    # 创建人
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # 关系
    paper = relationship("ExamPaper", back_populates="versions")
    creator = relationship("User")
