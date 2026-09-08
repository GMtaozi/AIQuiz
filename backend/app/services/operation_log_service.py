"""Operation Log Service - Business logic for operation log management.

Provides functions to:
- Record operation logs
- Query operation logs with filters
- Export operation logs to CSV
"""

import csv
import io
import logging
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog
from app.models.user import User

logger = logging.getLogger(__name__)

# Action constants for consistency
class OperationAction:
    """操作类型常量"""
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    SUBMIT = "submit"
    START = "start"
    EXPORT = "export"
    IMPORT = "import"
    UPLOAD = "upload"
    ARCHIVE = "archive"
    GRADE = "grade"
    REFRESH = "refresh"
    FORGOT_PASSWORD = "forgot_password"


class ResourceType:
    """资源类型常量"""
    USER = "user"
    QUESTION = "question"
    PAPER = "paper"
    EXAM = "exam"
    KNOWLEDGE = "knowledge"
    KNOWLEDGE_BASE = "knowledge_base"
    SYSTEM = "system"
    NOTIFICATION = "notification"
    TEMPLATE = "template"


def log_operation(
    db: Session,
    user: User,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    description: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> OperationLog:
    """记录操作日志。

    Args:
        db: 数据库会话
        user: 操作用户
        action: 操作类型 (login/logout/create/update/delete/publish/submit/export/upload/import)
        resource_type: 资源类型 (question/paper/exam/knowledge/user/system)
        resource_id: 资源ID（可选）
        description: 操作描述（可选）
        ip_address: 客户端IP（可选）
        user_agent: 客户端UA（可选）
        status: 操作状态 (success/failure)
        details: 扩展信息字典（可选）

    Returns:
        创建的 OperationLog 实例
    """
    log_entry = OperationLog(
        user_id=user.id,
        username=user.username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        details=details,
    )
    db.add(log_entry)
    # 不立即 commit，由调用方统一 commit（保持与业务操作同一事务）
    db.flush()
    return log_entry


def query_logs(
    db: Session,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OperationLog], int]:
    """查询操作日志（支持分页和过滤）。

    Args:
        db: 数据库会话
        user_id: 按用户ID过滤
        action: 按操作类型过滤
        resource_type: 按资源类型过滤
        resource_id: 按资源ID过滤
        status: 按状态过滤 (success/failure)
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        keyword: 关键字搜索（匹配 description 和 username）
        page: 页码（从1开始）
        page_size: 每页数量

    Returns:
        (日志列表, 总数) 元组
    """
    query = db.query(OperationLog)

    if user_id is not None:
        query = query.filter(OperationLog.user_id == user_id)
    if action is not None:
        query = query.filter(OperationLog.action == action)
    if resource_type is not None:
        query = query.filter(OperationLog.resource_type == resource_type)
    if resource_id is not None:
        query = query.filter(OperationLog.resource_id == resource_id)
    if status is not None:
        query = query.filter(OperationLog.status == status)
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(OperationLog.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date + "T23:59:59")
            query = query.filter(OperationLog.created_at <= end_dt)
        except ValueError:
            pass
    if keyword:
        escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            (OperationLog.description.ilike(f"%{escaped_keyword}%", escape="\\"))
            | (OperationLog.username.ilike(f"%{escaped_keyword}%", escape="\\"))
        )

    total = query.count()
    logs = (
        query.order_by(desc(OperationLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return logs, total


def export_logs_csv(
    db: Session,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None,
) -> StreamingResponse:
    """导出操作日志为 CSV 文件（流式响应）。

    安全要点：
    - 公式注入防护：= + - @ 开头的单元格内容前置单引号
    - UTF-8 BOM：保证 Excel 直接打开中文不乱码

    Args:
        db: 数据库会话
        其他过滤参数同 query_logs

    Returns:
        StreamingResponse with CSV content
    """
    query = db.query(OperationLog)

    if user_id is not None:
        query = query.filter(OperationLog.user_id == user_id)
    if action is not None:
        query = query.filter(OperationLog.action == action)
    if resource_type is not None:
        query = query.filter(OperationLog.resource_type == resource_type)
    if resource_id is not None:
        query = query.filter(OperationLog.resource_id == resource_id)
    if status is not None:
        query = query.filter(OperationLog.status == status)
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(OperationLog.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date + "T23:59:59")
            query = query.filter(OperationLog.created_at <= end_dt)
        except ValueError:
            pass
    if keyword:
        escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            (OperationLog.description.ilike(f"%{escaped_keyword}%", escape="\\"))
            | (OperationLog.username.ilike(f"%{escaped_keyword}%", escape="\\"))
        )

    _CSV_HEADERS = ["ID", "用户ID", "用户名", "操作", "资源类型", "资源ID", "描述", "IP地址", "状态", "详情", "时间"]

    def _safe_cell(value: Any) -> str:
        """公式注入防护：可能被 Excel 当公式的开头字符前置单引号。"""
        if value is None:
            return ""
        s = str(value)
        if s.startswith(("=", "+", "-", "@")):
            return "'" + s
        return s

    def _rows():
        # BOM：Excel 识别 UTF-8
        yield b"\xef\xbb\xbf"
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_CSV_HEADERS)
        yield buf.getvalue().encode("utf-8")

        for log in query.order_by(OperationLog.id).yield_per(500):
            buf.seek(0)
            buf.truncate()
            writer.writerow(
                [
                    _safe_cell(log.id),
                    _safe_cell(log.user_id),
                    _safe_cell(log.username),
                    _safe_cell(log.action),
                    _safe_cell(log.resource_type),
                    _safe_cell(log.resource_id),
                    _safe_cell(log.description),
                    _safe_cell(log.ip_address),
                    _safe_cell(log.status),
                    _safe_cell(str(log.details) if log.details else ""),
                    _safe_cell(log.created_at.isoformat() if log.created_at else ""),
                ]
            )
            yield buf.getvalue().encode("utf-8")

    filename = f"operation_logs_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        _rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def get_log_by_id(db: Session, log_id: int) -> OperationLog | None:
    """根据ID获取单条操作日志。

    Args:
        db: 数据库会话
        log_id: 日志ID

    Returns:
        OperationLog 实例或 None
    """
    return db.query(OperationLog).filter(OperationLog.id == log_id).first()


def get_user_recent_logs(db: Session, user_id: int, limit: int = 10) -> list[OperationLog]:
    """获取用户最近的操作日志。

    Args:
        db: 数据库会话
        user_id: 用户ID
        limit: 返回数量限制

    Returns:
        OperationLog 列表
    """
    return (
        db.query(OperationLog)
        .filter(OperationLog.user_id == user_id)
        .order_by(desc(OperationLog.created_at))
        .limit(limit)
        .all()
    )


def get_resource_logs(
    db: Session,
    resource_type: str,
    resource_id: int,
    limit: int = 50,
) -> list[OperationLog]:
    """获取特定资源的操作日志。

    Args:
        db: 数据库会话
        resource_type: 资源类型
        resource_id: 资源ID
        limit: 返回数量限制

    Returns:
        OperationLog 列表
    """
    return (
        db.query(OperationLog)
        .filter(
            OperationLog.resource_type == resource_type,
            OperationLog.resource_id == resource_id,
        )
        .order_by(desc(OperationLog.created_at))
        .limit(limit)
        .all()
    )
