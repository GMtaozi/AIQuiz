"""Redis-backed rate limiting utilities with graceful degradation."""

import logging

from fastapi import Depends, HTTPException, Request, status

from app.services.redis_client import get_redis
from app.services.settings_service import get_security_settings
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

# ---------- Login brute-force protection ----------


def _get_login_lock_config() -> tuple[int, int]:
    """Get login lock config from settings: (max_attempts, lockout_duration_seconds)"""
    settings = get_security_settings()
    if not settings.get("login_lock_enabled", True):
        return 0, 0  # Disabled
    max_attempts = settings.get("login_lock_count", 5)
    lockout_duration = settings.get("login_lock_duration", 30) * 60
    return max_attempts, lockout_duration


def check_login_rate_limit(username: str) -> None:
    """
    Raise HTTPException(429) if the account is locked due to too many failed attempts.
    Uses Redis INCR+EXPIRE with a per-username key.
    Gracefully passes through when Redis is unavailable.
    """
    max_attempts, lockout_duration = _get_login_lock_config()
    if max_attempts <= 0:
        return  # Rate limiting disabled via settings

    redis = get_redis()
    if redis is None:
        # Graceful degradation: allow the request when Redis is down
        logger.debug("[RateLimit] Redis unavailable; login rate limit skipped")
        return

    key = f"login:attempts:{username}"
    try:
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, lockout_duration)
        if count > max_attempts:
            lock_minutes = lockout_duration // 60
            logger.warning(f"[RateLimit] Account {username} locked after {count} attempts")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录失败次数过多，请{lock_minutes}分钟后再试",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"[RateLimit] Redis error for login check: {exc}; allowing")


def record_login_failure(username: str) -> None:
    """Record a failed login attempt (increment counter in Redis)."""
    max_attempts, lockout_duration = _get_login_lock_config()
    if max_attempts <= 0:
        return

    redis = get_redis()
    if redis is None:
        logger.debug("[RateLimit] Redis unavailable; failure not recorded")
        return

    key = f"login:attempts:{username}"
    try:
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, lockout_duration)
        logger.debug(f"[RateLimit] Recorded failure for {username}, count={count}")
    except Exception as exc:
        logger.warning(f"[RateLimit] Redis error recording failure: {exc}")


def record_login_success(username: str) -> None:
    """Clear the failed-attempt counter on successful login."""
    redis = get_redis()
    if redis is None:
        logger.debug("[RateLimit] Redis unavailable; success clear skipped")
        return

    key = f"login:attempts:{username}"
    try:
        redis.delete(key)
        logger.debug(f"[RateLimit] Cleared failures for {username}")
    except Exception as exc:
        logger.warning(f"[RateLimit] Redis error clearing success: {exc}")


# ---------- AI generation per-user rate limit ----------


def rate_limit_ai_gen(
    request: Request,
    current_user=Depends(get_current_user),
) -> None:
    """
    FastAPI dependency: limit each authenticated user to 5 AI generations per minute.
    Reads the limit from settings (ai_gen_rate_limit_per_minute), default 5.
    Passes through when Redis is unavailable.

    评估 P1-1 修复：原实现读取 request.state.user，但全代码库没有任何地方给
    request.state 赋值，导致限流永远放行。改为直接依赖 get_current_user。
    """
    # Default limit
    limit = 5

    # Try to read user-specific limit from settings if available
    try:
        settings = get_security_settings()
        limit = settings.get("ai_gen_rate_limit_per_minute", 5)
    except Exception:
        pass  # Fall back to default

    if current_user is None:
        return  # Unauthenticated; let auth dependency handle it

    user_id = getattr(current_user, "id", None)
    if user_id is None:
        return

    redis = get_redis()
    if redis is None:
        logger.debug("[RateLimit] Redis unavailable; AI gen rate limit skipped")
        return

    key = f"ai:gen:{user_id}"
    try:
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 60)
        if count > limit:
            logger.warning(f"[RateLimit] AI gen rate limit exceeded for user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"AI出题过于频繁，请1分钟后再试（每分钟最多{limit}次）",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"[RateLimit] Redis error for AI gen limit: {exc}; allowing")
