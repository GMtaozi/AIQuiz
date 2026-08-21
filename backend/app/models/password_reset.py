"""Password Reset Request Model - 密码重置请求表"""

from sqlalchemy import Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.sql import func

from app.database import Base


class PasswordResetRequest(Base):
    __tablename__ = "password_reset_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), nullable=False, index=True)  # 申请重置的用户名
    status = Column(SmallInteger, default=0, nullable=False)  # 0=待处理, 1=已处理
    admin_id = Column(Integer, nullable=True)  # 处理的管理员ID
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)  # 处理时间
