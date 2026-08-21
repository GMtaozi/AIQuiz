"""Common schemas for unified API responses."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应结构"""

    code: int = 200
    message: str = "success"
    data: T | None = None

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    """验证错误详情"""

    loc: list[str | int] | None = None
    msg: str | None = None
    type: str | None = None


class ErrorResponse(BaseModel):
    """统一错误响应结构"""

    code: int
    message: str
    detail: Any = None

    model_config = ConfigDict(from_attributes=True)
