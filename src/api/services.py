"""Service layer for task and queue management."""

import json
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import redis.asyncio as redis
from celery import Celery

from config import settings
from schemas import QueueStatus, TaskDetail, TaskState


class RedisService:
    """Redis service for task and queue management."""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False


class TaskService:
    """Service for managing tasks."""

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service.redis

    async def create_task(self, content: str) -> str:
        """Create a new task and queue it for processing."""
        task_id = str(uuid4())
        now = datetime.utcnow()

        task_data = {
            "task_id": task_id,
            "content": content,
            "state": TaskState.PENDING.value,
            "retry_count": 0,
            "max_retries": settings.max_retries,
            "last_error": "",
            "error_type": "",
            "retry_after": "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "completed_at": "",
            "result": "",
            "error_history": json.dumps([]),
        }

        # Store task metadata
        await self.redis.hset(f"task:{task_id}", mapping=task_data)

        # Queue in primary queue
        await self.redis.lpush("tasks:pending:primary", task_id)

        return task_id

    async def get_task(self, task_id: str) -> Optional[TaskDetail]:
        """Get task details by ID."""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return None

        # Parse JSON fields
        error_history = json.loads(task_data.get("error_history", "[]"))

        # Convert string dates back to datetime objects
        created_at = datetime.fromisoformat(task_data["created_at"])
        updated_at = datetime.fromisoformat(task_data["updated_at"])
        completed_at = (
            datetime.fromisoformat(task_data["completed_at"])
            if task_data.get("completed_at")
            else None
        )
        retry_after = (
            datetime.fromisoformat(task_data["retry_after"])
            if task_data.get("retry_after")
            else None
        )

        return TaskDetail(
            task_id=task_data["task_id"],
            state=TaskState(task_data["state"]),
            content=task_data["content"],
            retry_count=int(task_data["retry_count"]),
            max_retries=int(task_data["max_retries"]),
            last_error=task_data.get("last_error") or None,
            error_type=task_data.get("error_type") or None,
            retry_after=retry_after,
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
            result=task_data.get("result") or None,
            error_history=error_history,
        )

    async def retry_task(self, task_id: str, reset_retry_count: bool = False) -> bool:
        """Manually retry a failed task."""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return False

        current_state = task_data.get("state")
        if current_state not in [TaskState.FAILED.value, TaskState.DLQ.value]:
            return False

        # Update task state
        updates = {
            "state": TaskState.PENDING.value,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if reset_retry_count:
            updates["retry_count"] = 0

        await self.redis.hset(f"task:{task_id}", mapping=updates)

        # Queue in retry queue
        await self.redis.lpush("tasks:pending:retry", task_id)

        return True


class QueueService:
    """Service for managing queues and monitoring."""

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service.redis

    async def get_queue_status(self) -> QueueStatus:
        """Get comprehensive queue status."""
        # Get queue depths
        primary_depth = await self.redis.llen("tasks:pending:primary")
        retry_depth = await self.redis.llen("tasks:pending:retry")
        scheduled_count = await self.redis.zcard("tasks:scheduled")
        dlq_depth = await self.redis.llen("dlq:tasks")

        queues = {
            "primary": primary_depth,
            "retry": retry_depth,
            "scheduled": scheduled_count,
            "dlq": dlq_depth,
        }

        # Get task counts by state
        states = defaultdict(int)
        async for key in self.redis.scan_iter("task:*"):
            state = await self.redis.hget(key, "state")
            if state:
                states[state] += 1

        # Calculate adaptive retry ratio
        retry_ratio = self._calculate_adaptive_retry_ratio(retry_depth)

        return QueueStatus(
            queues=queues, states=dict(states), retry_ratio=retry_ratio
        )

    async def get_dlq_tasks(self, limit: int = 100) -> List[TaskDetail]:
        """Get tasks from dead letter queue."""
        task_ids = await self.redis.lrange("dlq:tasks", 0, limit - 1)
        tasks = []

        for task_id in task_ids:
            # Try to get from DLQ-specific storage first
            task_data = await self.redis.hgetall(f"dlq:task:{task_id}")
            if not task_data:
                # Fallback to regular task storage
                task_data = await self.redis.hgetall(f"task:{task_id}")

            if task_data:
                # Parse the task data similar to get_task method
                error_history = json.loads(task_data.get("error_history", "[]"))
                created_at = datetime.fromisoformat(task_data["created_at"])
                updated_at = datetime.fromisoformat(task_data["updated_at"])
                completed_at = (
                    datetime.fromisoformat(task_data["completed_at"])
                    if task_data.get("completed_at")
                    else None
                )
                retry_after = (
                    datetime.fromisoformat(task_data["retry_after"])
                    if task_data.get("retry_after")
                    else None
                )

                task_detail = TaskDetail(
                    task_id=task_data["task_id"],
                    state=TaskState(task_data["state"]),
                    content=task_data["content"],
                    retry_count=int(task_data["retry_count"]),
                    max_retries=int(task_data["max_retries"]),
                    last_error=task_data.get("last_error") or None,
                    error_type=task_data.get("error_type") or None,
                    retry_after=retry_after,
                    created_at=created_at,
                    updated_at=updated_at,
                    completed_at=completed_at,
                    result=task_data.get("result") or None,
                    error_history=error_history,
                )
                tasks.append(task_detail)

        return tasks

    def _calculate_adaptive_retry_ratio(self, retry_depth: int) -> float:
        """Calculate adaptive retry ratio based on queue pressure."""
        if retry_depth < settings.retry_queue_warning:
            return settings.default_retry_ratio  # Normal: 30%
        elif retry_depth < settings.retry_queue_critical:
            return 0.2  # Warning: 20%
        else:
            return 0.1  # Critical: 10%


class HealthService:
    """Service for health checks."""

    def __init__(self, redis_service: RedisService, celery_app: Celery):
        self.redis_service = redis_service
        self.celery_app = celery_app

    async def check_health(self) -> Dict[str, any]:
        """Perform comprehensive health check."""
        # Check Redis
        redis_ok = await self.redis_service.ping()

        # Check Celery workers
        try:
            active_workers = self.celery_app.control.inspect().active_queues()
            workers_ok = bool(active_workers)
        except Exception:
            workers_ok = False

        # Overall status
        status = "healthy" if redis_ok and workers_ok else "unhealthy"

        return {
            "status": status,
            "components": {
                "redis": redis_ok,
                "workers": workers_ok,
                "circuit_breaker": "unknown",  # Will be implemented later
            },
            "timestamp": datetime.utcnow(),
        }


# Global service instances (will be initialized in main.py)
redis_service: Optional[RedisService] = None
task_service: Optional[TaskService] = None
queue_service: Optional[QueueService] = None
health_service: Optional[HealthService] = None
