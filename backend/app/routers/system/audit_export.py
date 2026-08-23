"""审计日志导出（CSV）—— 企业合规刚需。

安全要点：
- 公式注入防护：= + - @ 开头的单元格内容前置单引号（复用 P1-13 结论）
- UTF-8 BOM：保证 Excel 直接打开中文不乱码
- 仅管理员可导出；导出动作写入操作日志
"""
import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import AuditLog
from app.utils.security import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

_CSV_HEADERS = ["ID", "题目ID", "审核人", "动作", "原状态", "新状态", "原因", "IP", "User-Agent", "时间"]

_ACTION_ZH = {"approved": "通过", "rejected": "驳回", "reverted": "撤销"}


def _safe_cell(value) -> str:
    """公式注入防护：可能被 Excel 当公式的开头字符前置单引号。"""
    if value is None:
        return ""
    s = str(value)
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


@router.get("/audit-logs/export")
def export_audit_logs(
    start_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """流式导出审核日志 CSV（管理员）。"""

    query = db.query(AuditLog)
    try:
        if start_date:
            query = query.filter(AuditLog.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(AuditLog.created_at <= datetime.fromisoformat(end_date + "T23:59:59"))
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="日期格式无效，应为 YYYY-MM-DD")

    def _rows():
        # BOM：Excel 识别 UTF-8
        yield b"\xef\xbb\xbf"
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_CSV_HEADERS)
        yield buf.getvalue().encode("utf-8")

        for log in query.order_by(AuditLog.id).yield_per(500):
            buf.seek(0)
            buf.truncate()
            writer.writerow(
                [
                    _safe_cell(log.id),
                    _safe_cell(log.question_id),
                    _safe_cell(log.auditor_id),
                    _safe_cell(_ACTION_ZH.get(log.action, log.action)),
                    _safe_cell(log.old_status),
                    _safe_cell(log.new_status),
                    _safe_cell(log.reason),
                    _safe_cell(log.ip_address),
                    _safe_cell(log.user_agent),
                    _safe_cell(log.created_at.isoformat() if log.created_at else ""),
                ]
            )
            yield buf.getvalue().encode("utf-8")

    filename = f"audit_logs_{datetime.now():%Y%m%d_%H%M%S}.csv"
    logger.info(f"[审计导出] 管理员 {current_user.username} 导出审核日志 -> {filename}")
    return StreamingResponse(
        _rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
