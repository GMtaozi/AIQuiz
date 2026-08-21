"""Observability: structured logging + optional Sentry integration.

Sentry DSN 为空时完全跳过（本地开发零依赖）；生产在 .env 配置 SENTRY_DSN 即启用。
"""
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    """最小 JSON 日志格式（无第三方依赖），便于日志采集器（Loki/ELK）解析。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(debug: bool = False, json_format: bool = False) -> None:
    """统一日志配置：root logger 级别与格式收敛，生产建议 LOG_JSON=true。"""
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # 高频访问日志噪音治理（访问日志交给 nginx/uvicorn 自身）
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def init_sentry(dsn: str, environment: str = "development") -> bool:
    """初始化 Sentry 错误追踪。DSN 为空或 SDK 未安装时优雅降级，返回是否启用。"""
    log = logging.getLogger(__name__)
    if not dsn:
        log.info("SENTRY_DSN 未配置，错误追踪未启用")
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.1,
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        log.info(f"Sentry 错误追踪已启用 (environment={environment})")
        return True
    except ImportError:
        log.warning("sentry-sdk 未安装（pip install 'sentry-sdk[fastapi]'），错误追踪未启用")
        return False
