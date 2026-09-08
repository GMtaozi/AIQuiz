"""Operation Log Model - Records system-wide critical business operations.

This model provides comprehensive audit trail for all key operations including:
- User authentication (login/logout/register)
- Paper management (create/publish/delete)
- Exam operations (start/submit)
- Knowledge base operations (create/upload)
- Question management (create/import)
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OperationLog(Base):
    """操作日志表 - 记录全系统关键业务操作。

    与 AuditLog（审核日志）独立存在：
    - AuditLog: 仅记录题目审核操作（approved/rejected/reverted）
    - OperationLog: 记录所有关键业务操作（登录/登出/创建/更新/删除/发布/提交/导出）
    """

    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("idx_operation_log_user_id", "user_id"),
        Index("idx_operation_log_action", "action"),
        Index("idx_operation_log_resource", "resource_type", "resource_id"),
        Index("idx_operation_log_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)  # 冗余存储，避免用户删除后丢失
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # login/logout/register/create/update/delete/publish/submit/export/upload/import
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # question/paper/exam/knowledge/user/system/notification
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)  # success/failure
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # 扩展信息
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
