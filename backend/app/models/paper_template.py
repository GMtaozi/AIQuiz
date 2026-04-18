"""Paper Template Model"""
from sqlalchemy import Column, Integer, String, Text, SmallInteger, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base


class PaperTemplate(Base):
    """试卷模板模型"""
    __tablename__ = "paper_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    # 题目分布配置 (JSON格式)
    question_distribution = Column(JSON, nullable=True)
    # 总分
    total_score = Column(Integer, default=100)
    # 考试时长(分钟)
    duration = Column(Integer, default=120)
    # 状态: 0=禁用, 1=启用
    status = Column(SmallInteger, default=1)
    # 是否删除
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
