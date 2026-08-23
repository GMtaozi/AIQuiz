"""ARQ Worker - AI 出题后台任务队列。

替代原 threading.Thread 方案（评估 P1-2 遗留）：
- 任务持久化于 Redis 队列，进程重启不丢、支持多副本部署
- max_jobs 提供并发上限（替代原 BoundedSemaphore）
- job_timeout 提供单任务硬超时
- on_startup 回收悬挂任务（重启后 pending/running 置为 failed）

本地开发启动 worker（与 API 分离进程）:
    cd backend && arq app.worker.WorkerSettings

Docker 部署由 compose 中的 worker 服务自动运行。
"""
import asyncio
import logging
from typing import Callable, List

import redis as redis_sync
from arq import func
from arq.connections import RedisSettings

from app.config import settings

logger = logging.getLogger(__name__)

# 取消标志的 Redis key 前缀（跨进程软取消：任务在检查点轮询该 key）
_CANCEL_KEY_PREFIX = "aiquiz:cancel:task:"
_CANCEL_TTL_SECONDS = 3600


def get_sync_redis() -> redis_sync.Redis:
    """同步 Redis 客户端（取消标志读写专用；worker 线程内无法复用 async 连接）。"""
    return redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)


def set_cancel_flag(task_id: int) -> bool:
    """设置取消标志（API 侧调用）。返回是否成功。"""
    try:
        client = get_sync_redis()
        client.set(f"{_CANCEL_KEY_PREFIX}{task_id}", "1", ex=_CANCEL_TTL_SECONDS)
        return True
    except Exception as e:
        logger.error(f"设置取消标志失败 task_id={task_id}: {e}")
        return False


def clear_cancel_flag(task_id: int) -> None:
    try:
        get_sync_redis().delete(f"{_CANCEL_KEY_PREFIX}{task_id}")
    except Exception:
        pass


def _make_cancel_checker(task_id: int) -> Callable[[], bool]:
    """构造任务内部使用的取消检查函数（每次检查新建短连接，避免线程安全问题）。"""

    def _check() -> bool:
        try:
            return bool(get_sync_redis().exists(f"{_CANCEL_KEY_PREFIX}{task_id}"))
        except Exception:
            return False  # Redis 故障时不误杀任务

    return _check


async def run_generation_task(ctx, task_id: int, req_dict: dict, user_id: int | None = None) -> None:
    """ARQ 任务入口：在线程中执行同步出题逻辑，不阻塞 worker 事件循环。"""
    from app.routers.ai_templates.task_runner import execute_generation_task

    await asyncio.to_thread(
        execute_generation_task,
        task_id,
        req_dict,
        user_id,
        _make_cancel_checker(task_id),
    )


async def recover_stale_tasks(ctx) -> None:
    """worker 启动时回收悬挂任务：pending/running → failed。

    NOTE: 当前按单 worker 部署设计；若未来多副本部署，需改为基于
    ARQ job 注册表或心跳时间戳的精确回收。
    """
    from app.database import SessionLocal
    from app.models.question import GenerationTask

    db = SessionLocal()
    try:
        stale = (
            db.query(GenerationTask)
            .filter(GenerationTask.status.in_(["pending", "running"]))
            .all()
        )
        for task in stale:
            task.status = "failed"
            task.error_message = "服务重启导致任务中断，请重新发起"
        db.commit()
        if stale:
            logger.warning(f"已回收 {len(stale)} 个悬挂任务")
    finally:
        db.close()


class WorkerSettings:
    """arq CLI 入口: arq app.worker.WorkerSettings"""

    functions = [func(run_generation_task, name="run_generation_task")]
    on_startup = recover_stale_tasks

    # NOTE: 必须是类属性（RedisSettings 实例），ARQ 内部直接访问 .host 等字段
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # 并发出题上限（对应原 BoundedSemaphore(20)）
    max_jobs = 20
    # 单任务硬超时 15 分钟（AI 批量调用 + 校验的最坏情况）
    job_timeout = 900
    health_check_interval = 30
