"""User Model"""

from sqlalchemy import JSON, Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.sql import func

from app.database import Base

# 默认角色菜单权限配置（全系统唯一权威来源；
# security.py 的 require_permission 与登录响应下发均以此为准）
ROLE_DEFAULT_PERMISSIONS = {
    1: [
        "ai-question",
        "audit",
        "auto-paper",
        "question-bank",
        "paper-management",
        "template-market",
        "knowledge",
        "knowledge-bases",
        "settings",
        "user-permission",
    ],
    2: [
        "ai-question",
        "audit",
        "auto-paper",
        "question-bank",
        "paper-management",
        "template-market",
        "knowledge",
        "knowledge-bases",
    ],
    # 学生：面向考试场景（参加考试/查成绩走 get_current_user + 名单归属校验，
    # 不依赖菜单权限）。管理端菜单一律不放行；未来学生端页面上线后在此追加
    # （如 "exam", "exam-records"）。
    3: [],
}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SmallInteger, default=3, server_default="3")
    status = Column(SmallInteger, default=1, server_default="1")
    menu_permissions = Column(JSON, nullable=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
