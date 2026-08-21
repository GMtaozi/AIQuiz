"""统一系统设置读取服务。

历史问题：system.py 存在三套并行的配置源——DEFAULT_SETTINGS（常量）、
MOCK_SETTINGS（常量，从不写入）、SystemSetting 表（PUT 写入但运行时不读），
导致管理员在 UI 修改的"登录锁定/密码强度/会话超时/角色权限/AI 服务商"等
全部不生效（只落库不消费）。

本模块作为唯一真相源：所有运行时读取都走 DB（DEFAULT_SETTINGS 仅作 DB 缺失时的
fallback），并加进程内缓存，在 PUT 写入时失效。对外提供三个签名不变的函数：
get_security_settings / get_ai_config / get_role_permissions_config，
约 25 个调用点零改动即可受益。

注意：不依赖 routers.system，避免分层倒置与循环导入。
"""

import json
import logging
import threading
import time
from typing import Any, Dict, List

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# 复用 system.py 的默认值定义作为 DB 缺失时的 fallback。
# 采用延迟导入避免在模块加载阶段引入 routers.system 的整条依赖链。
_DEFAULT_SETTINGS: Dict[str, Dict[str, Any]] | None = None

# 缓存（key -> 解析后的值）。写入时清空。None 表示未加载。
_cache: Dict[str, Any] | None = None
_cache_lock = threading.Lock()
# 评估 P2-18：缓存 TTL（秒）。多 worker 部署时，某个 worker 的 PUT 只失效本进程缓存；
# 加 TTL 后其他 worker 最长 _CACHE_TTL_SECONDS 内也会重新从 DB 加载，保证最终一致。
_CACHE_TTL_SECONDS = 60
_cache_loaded_at: float = 0.0


def _default_settings() -> Dict[str, Dict[str, Any]]:
    """延迟获取 DEFAULT_SETTINGS（来自 routers.system）。"""
    global _DEFAULT_SETTINGS
    if _DEFAULT_SETTINGS is None:
        from app.routers.system import DEFAULT_SETTINGS

        _DEFAULT_SETTINGS = DEFAULT_SETTINGS
    return _DEFAULT_SETTINGS


def _read_from_db(key: str) -> Any:
    """从 DB 读取单个 key（带缓存）。DB miss 时回落到 DEFAULT_SETTINGS。"""
    global _cache
    if _cache is None or time.time() - _cache_loaded_at > _CACHE_TTL_SECONDS:
        _load_cache()
    if key in _cache:
        return _cache[key]
    # 缓存未命中（理论上 _load_cache 已填满所有 key），回落默认值
    return _default_settings().get(key, {}).get("value")


def _load_cache() -> None:
    """一次性把全部 DB 设置读进内存缓存。DB 无记录的 key 用默认值填充。"""
    global _cache, _cache_loaded_at
    defaults = _default_settings()
    cache: Dict[str, Any] = {}
    try:
        db = SessionLocal()
        try:
            from app.models.system_setting import SystemSetting

            rows = {r.key: r for r in db.query(SystemSetting).all()}
            for key, cfg in defaults.items():
                row = rows.get(key)
                if row is None:
                    cache[key] = cfg["value"]
                else:
                    cache[key] = _coerce(row.value, row.type or cfg.get("type", "string"))
        finally:
            db.close()
    except Exception as e:
        # DB 不可用时全用默认值，保证服务可用
        logger.warning(f"读取系统设置失败，使用默认值: {e}")
        for key, cfg in defaults.items():
            cache[key] = cfg["value"]
    _cache = cache
    _cache_loaded_at = time.time()


def _coerce(value: str, type_hint: str) -> Any:
    """按 type 把 DB 里的字符串值还原为 Python 类型。"""
    if value is None:
        return None
    if type_hint == "json":
        try:
            result = json.loads(value) if value else []
            # json.loads 对简单字符串会保留外层引号（如 "minimax"），
            # 直接返回解析后的字符串即可，避免前端匹配时出现多余引号。
            if isinstance(result, str):
                return result
            return result
        except Exception:
            return []
    if type_hint == "boolean":
        return value in ("true", "True", "1", True)
    if type_hint == "number":
        try:
            return int(value)
        except Exception:
            try:
                return float(value)
            except Exception:
                return 0
    return value


def invalidate_cache() -> None:
    """清除缓存（PUT 设置后调用，下次读取会重新从 DB 加载）。"""
    global _cache
    _cache = None


def get_security_settings() -> Dict[str, Any]:
    """获取当前生效的安全设置（供其他模块使用）。

    现在读 DB（管理员在 UI 的修改生效），DB 缺失时回落 DEFAULT_SETTINGS。
    """
    return {
        "login_lock_enabled": _read_from_db("login_lock_enabled"),
        "login_lock_count": _read_from_db("login_lock_count"),
        "login_lock_duration": _read_from_db("login_lock_duration"),
        "password_strength_enabled": _read_from_db("password_strength_enabled"),
        "password_require_uppercase": _read_from_db("password_require_uppercase"),
        "password_require_lowercase": _read_from_db("password_require_lowercase"),
        "password_require_digit": _read_from_db("password_require_digit"),
        "password_require_special": _read_from_db("password_require_special"),
        "session_timeout": _read_from_db("session_timeout"),
        "operation_log_enabled": _read_from_db("operation_log_enabled"),
    }


def get_ai_config() -> Dict[str, Any]:
    """获取当前AI配置（供其他模块使用）。

    现在读 DB，PUT /ai-config 写入后经 invalidate_cache + reload_ai_provider
    即可让实际出题生效。
    """
    return {
        "provider": _read_from_db("ai_provider"),
        "model": _read_from_db("ai_model"),
        "api_key": _read_from_db("ai_api_key"),
        "api_url": _read_from_db("ai_api_url"),
        "timeout": _read_from_db("ai_timeout"),
    }


def get_role_permissions_config() -> Dict[int, List[str]]:
    """获取所有角色的菜单权限配置。

    现在读 DB，管理员在 UI 改的角色权限对登录时的权限下发生效。
    """
    defaults = _default_settings()
    return {
        1: _read_from_db("role_1_permissions") or defaults.get("role_1_permissions", {}).get("value", []),
        2: _read_from_db("role_2_permissions") or defaults.get("role_2_permissions", {}).get("value", []),
        3: _read_from_db("role_3_permissions") or defaults.get("role_3_permissions", {}).get("value", []),
    }
