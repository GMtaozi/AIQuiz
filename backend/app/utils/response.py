"""Response utilities for unified API envelope."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.types import Message

from app.schemas.common import ApiResponse


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    """Build a successful API response dict."""
    return ApiResponse(code=200, message=message, data=data).model_dump()


def _is_already_wrapped(payload: Any) -> bool:
    """Check if payload already uses the standard envelope."""
    return isinstance(payload, dict) and "code" in payload and "message" in payload


async def _read_json_body(body: bytes) -> Any:
    """Parse JSON body bytes."""
    if not body:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


async def _consume_body(response: Response) -> bytes:
    """读取响应体（兼容 BaseHTTPMiddleware 返回的 _StreamingResponse）。"""
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is None:
        # 普通 Response：直接读 body 属性
        body = getattr(response, "body", b"")
        return body if isinstance(body, bytes) else b""

    chunks = []
    async for chunk in body_iterator:
        if chunk:
            chunks.append(chunk)
    return b"".join(chunks)


def _inherit_headers(new_response: Response, old_response: Response) -> None:
    """继承原响应头到新响应（raw 级操作，多值头如 Set-Cookie 安全）。

    跳过 content-length / content-type —— 它们由新响应根据实际 body 重新生成。
    若沿用旧 content-length，包装后 body 变长会触发
    uvicorn "Response content longer than Content-Length" 断连。
    """
    skip = {b"content-length", b"content-type"}
    existing = set(new_response.raw_headers)
    for key, value in old_response.headers.raw:
        if key.lower() not in skip and (key, value) not in existing:
            new_response.raw_headers.append((key, value))


async def wrap_response(request: Request, response: Response) -> Response:
    """Wrap successful JSON responses in the standard envelope.

    注意：在 Starlette BaseHTTPMiddleware 中，call_next 返回的一定是
    _StreamingResponse（响应体已被流式化），不能直接访问 .body 属性，
    必须消费 body_iterator 才能拿到完整响应体。

    Skips wrapping when:
    - status_code is not 2xx
    - content-type 不是 JSON
    - body is empty
    - body already has a top-level ``code`` field (already wrapped)
    """
    if response.status_code < 200 or response.status_code >= 300:
        return response

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        return response

    body = await _consume_body(response)
    if not body:
        # 空 body：重建原响应（保留已消费的流）
        empty = Response(status_code=response.status_code)
        _inherit_headers(empty, response)
        return empty

    payload = await _read_json_body(body)
    if payload is None or _is_already_wrapped(payload):
        # 非 JSON 或已封装：原样重建响应
        same = Response(
            content=body,
            status_code=response.status_code,
            media_type="application/json",
        )
        _inherit_headers(same, response)
        return same

    wrapped = ApiResponse(code=response.status_code, message="success", data=payload).model_dump()
    wrapped_response = JSONResponse(
        status_code=response.status_code,
        content=wrapped,
    )
    _inherit_headers(wrapped_response, response)
    return wrapped_response
