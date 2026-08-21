"""Notification Model - 通知表"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)  # null表示系统通知
    type = Column(String(20), default="info", nullable=False)  # info/success/warning/error
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    link = Column(String(500), nullable=True)  # 点击跳转链接
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
