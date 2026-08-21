"""User Model"""

from sqlalchemy import JSON, Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.sql import func

from app.database import Base

# 默认角色菜单权限配置
ROLE_DEFAULT_PERMISSIONS = {
    1: [
        "ai-question",
        "audit",
        "auto-paper",
        "question-bank",
        "paper-management",
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
        "knowledge",
        "knowledge-bases",
    ],
    3: ["audit", "question-bank"],
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
