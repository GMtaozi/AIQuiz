"""Redis 客户端单例（同步 + 异步）。

容错策略：Redis 不可用时返回 None，调用方据此降级（限流放行），保证
Redis 故障不影响核心业务。连接配置从 settings.redis_url 读取，密码可内嵌在 URL。

评估 P2-18：原实现 _unavailable 置位后永久降级（Redis 恢复后不再重连），
改为带时间戳的降级窗口（默认 30 秒后重试），兼顾故障容忍与自动恢复。
"""

import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)

_sync_client = None
_async_client = None
_unavailable = False  # 标记已尝试并失败，避免每次调用都重连
_unavailable_since: float = 0.0  # 降级开始时间戳
_DEGRADE_RETRY_SECONDS = 30  # 降级后多久重试一次连接


def _is_in_degrade_window() -> bool:
    """是否处于降级窗口内（窗口外允许重试连接）。"""
    global _unavailable_since
    if not _unavailable:
        return False
    return (time.time() - _unavailable_since) < _DEGRADE_RETRY_SECONDS


def _mark_available() -> None:
    global _unavailable, _unavailable_since
    _unavailable = False
    _unavailable_since = 0.0


def _mark_unavailable() -> None:
    global _unavailable, _unavailable_since
    _unavailable = True
    _unavailable_since = time.time()


def get_redis():
    """获取同步 Redis 客户端单例。不可用返回 None。"""
    global _sync_client, _unavailable
    if _is_in_degrade_window():
        return None
    if _sync_client is not None:
        return _sync_client
    try:
        import redis

        _sync_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _sync_client.ping()
        _mark_available()
        logger.info("Redis 连接成功")
        return _sync_client
    except Exception as e:
        _sync_client = None
        _mark_unavailable()
        logger.warning(f"Redis 不可用，限流将降级为放行（{_DEGRADE_RETRY_SECONDS}s 后重试）: {e}")
        return None


def get_async_redis():
    """获取异步 Redis 客户端单例。不可用返回 None。"""
    global _async_client
    if _is_in_degrade_window():
        return None
    if _async_client is not None:
        return _async_client
    try:
        import redis.asyncio as aioredis

        _async_client = aioredis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _mark_available()
        return _async_client
    except Exception as e:
        _async_client = None
        _mark_unavailable()
        logger.warning(f"异步 Redis 不可用: {e}")
        return None
