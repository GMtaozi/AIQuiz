"""Global exception handlers with safe error responses.

Ensures no internal exception details leak to API consumers.
All unexpected errors return a generic 500 message while the full
traceback is logged server-side.
"""

import logging
import traceback as tb_module
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


# ---------- HTTPException passthrough (detail is already a safe string) ----------


class _SafeHTTPException(StarletteHTTPException):
    """HTTPException subclass — detail is treated as a safe user-facing string."""


# ---------- Global exception handlers ----------


def _safe_detail(detail: Any) -> str:
    """Coerce detail to a safe string (no raw exception objects)."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, (list, dict)):
        return str(detail)
    return str(detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Pass through HTTPException with standardised envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.status_code,
            message=_safe_detail(exc.detail),
            detail=_safe_detail(exc.detail),
        ).model_dump(),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Wrap 422 validation errors keeping the original detail array intact."""
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code=422,
            message="请求参数校验失败",
            detail=exc.errors(),
        ).model_dump(),
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log full traceback, return generic 500."""
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        tb_module.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=500,
            message="服务器内部错误",
            detail="服务器内部错误",
        ).model_dump(),
    )
