"""License 授权管理 API（仅管理员）。"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.services.license_service import license_service
from app.utils.security import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


class LicenseUploadRequest(BaseModel):
    content: str  # 授权文件完整 JSON 内容


@router.get("/license")
def get_license(current_user=Depends(require_admin)):
    """当前授权状态（模式/客户/到期/特性/试用剩余天数）。"""
    return license_service.state


@router.post("/license/upload")
def upload_license(
    body: LicenseUploadRequest,
    request: Request,
    current_user=Depends(require_admin),
):
    """上传新授权文件：验签通过才落盘并热生效，无需重启。"""
    from app.services.license_service import parse_license_file

    payload, err = parse_license_file(body.content)
    if payload is None:
        raise HTTPException(status_code=400, detail=f"授权文件无效: {err}")

    path = settings.license_file
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body.content)
    except OSError as e:
        logger.error(f"授权文件写入失败: {e}")
        raise HTTPException(status_code=500, detail="授权文件写入失败，请检查服务器文件权限")

    state = license_service.reload()
    # 审计日志
    from app.routers.system.users import _log_operation

    _log_operation(current_user, f"更新了商业授权: licensee={state.get('licensee')}, mode={state.get('mode')}")
    return {"message": "授权已更新并生效", "license": state}
