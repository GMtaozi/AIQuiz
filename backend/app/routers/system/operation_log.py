"""Operation Log Router - 操作日志查询与导出端点。

端点：
- GET /api/system/operation-logs - 查询操作日志（admin）
- GET /api/system/operation-logs/export - 导出 CSV（admin）
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.operation_log import OperationLog
from app.services.operation_log_service import (
    OperationAction,
    ResourceType,
    export_logs_csv,
    query_logs,
)
from app.utils.security import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/operation-logs")
def list_operation_logs(
    user_id: int | None = Query(None, description="按用户ID过滤"),
    action: str | None = Query(None, description="按操作类型过滤"),
    resource_type: str | None = Query(None, description="按资源类型过滤"),
    resource_id: int | None = Query(None, description="按资源ID过滤"),
    status: str | None = Query(None, description="按状态过滤 (success/failure)"),
    start_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    keyword: str | None = Query(None, description="关键字搜索（描述/用户名）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """查询操作日志（管理员）。

    支持按用户、操作类型、资源类型、时间范围、关键字过滤。
    """
    logs, total = query_logs(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    # 序列化响应
    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": log.username,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "status": log.status,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/operation-logs/export")
def export_operation_logs(
    user_id: int | None = Query(None, description="按用户ID过滤"),
    action: str | None = Query(None, description="按操作类型过滤"),
    resource_type: str | None = Query(None, description="按资源类型过滤"),
    resource_id: int | None = Query(None, description="按资源ID过滤"),
    status: str | None = Query(None, description="按状态过滤"),
    start_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    keyword: str | None = Query(None, description="关键字搜索"),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """导出操作日志为 CSV（管理员）。

    返回 UTF-8 BOM 编码的 CSV 文件，Excel 可直接打开不乱码。
    公式注入防护：= + - @ 开头的内容前置单引号。
    """
    logger.info(
        f"[操作日志导出] 管理员 {current_user.username} 导出操作日志"
    )
    return export_logs_csv(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
    )


@router.get("/operation-logs/actions")
def list_action_types(
    current_user=Depends(require_admin),
):
    """获取所有操作类型枚举值（用于前端筛选下拉框）。"""
    return {
        "actions": [
            {"value": OperationAction.LOGIN, "label": "登录"},
            {"value": OperationAction.LOGOUT, "label": "登出"},
            {"value": OperationAction.REGISTER, "label": "注册"},
            {"value": OperationAction.CREATE, "label": "创建"},
            {"value": OperationAction.UPDATE, "label": "更新"},
            {"value": OperationAction.DELETE, "label": "删除"},
            {"value": OperationAction.PUBLISH, "label": "发布"},
            {"value": OperationAction.UNPUBLISH, "label": "取消发布"},
            {"value": OperationAction.SUBMIT, "label": "提交"},
            {"value": OperationAction.START, "label": "开始"},
            {"value": OperationAction.EXPORT, "label": "导出"},
            {"value": OperationAction.IMPORT, "label": "导入"},
            {"value": OperationAction.UPLOAD, "label": "上传"},
            {"value": OperationAction.ARCHIVE, "label": "归档"},
            {"value": OperationAction.GRADE, "label": "批改"},
            {"value": OperationAction.REFRESH, "label": "刷新令牌"},
            {"value": OperationAction.FORGOT_PASSWORD, "label": "忘记密码"},
        ],
        "resource_types": [
            {"value": ResourceType.USER, "label": "用户"},
            {"value": ResourceType.QUESTION, "label": "题目"},
            {"value": ResourceType.PAPER, "label": "试卷"},
            {"value": ResourceType.EXAM, "label": "考试"},
            {"value": ResourceType.KNOWLEDGE, "label": "知识点"},
            {"value": ResourceType.KNOWLEDGE_BASE, "label": "知识库"},
            {"value": ResourceType.SYSTEM, "label": "系统"},
            {"value": ResourceType.NOTIFICATION, "label": "通知"},
            {"value": ResourceType.TEMPLATE, "label": "模板"},
        ],
        "statuses": [
            {"value": "success", "label": "成功"},
            {"value": "failure", "label": "失败"},
        ],
    }
