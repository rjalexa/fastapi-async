# src/api/services.py
"""Service layer for task and queue management."""

import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import redis.asyncio as redis
from celery import Celery

from config import settings
from schemas import QueueStatus, TaskDetail, TaskState, QueueName, QUEUE_KEY_MAP


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

    async def increment_state_counter(self, state: str, amount: int = 1) -> int:
        """Increment a task state counter."""
        key = f"metrics:tasks:state:{state.lower()}"
        return await self.redis.incrby(key, amount)

    async def decrement_state_counter(self, state: str, amount: int = 1) -> int:
        """Decrement a task state counter."""
        key = f"metrics:tasks:state:{state.lower()}"
        return await self.redis.decrby(key, amount)

    async def get_state_counter(self, state: str) -> int:
        """Get current value of a task state counter."""
        key = f"metrics:tasks:state:{state.lower()}"
        value = await self.redis.get(key)
        return int(value) if value else 0

    async def get_all_state_counters(self) -> Dict[str, int]:
        """Get all task state counters."""
        counters = {}
        for state in ["pending", "active", "completed", "failed", "scheduled", "dlq"]:
            counters[state] = await self.get_state_counter(state)
        return counters

    async def update_state_counters(self, old_state: Optional[str], new_state: str) -> None:
        """Atomically update state counters when a task changes state."""
        async with self.redis.pipeline(transaction=True) as pipe:
            if old_state and old_state.lower() != new_state.lower():
                await pipe.decrby(f"metrics:tasks:state:{old_state.lower()}", 1)
            await pipe.incrby(f"metrics:tasks:state:{new_state.lower()}", 1)
            await pipe.execute()

    async def publish_queue_update(self, update_data: Dict) -> None:
        """Publish queue update to Redis pub/sub channel."""
        await self.redis.publish("queue-updates", json.dumps(update_data))


class TaskService:
    """Service for managing tasks."""

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service.redis
        self.redis_service = redis_service

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

        # Use Redis transaction to ensure atomicity
        async with self.redis.pipeline(transaction=True) as pipe:
            # Store task metadata and queue in primary queue atomically
            await pipe.hset(f"task:{task_id}", mapping=task_data)
            await pipe.lpush(QUEUE_KEY_MAP[QueueName.PRIMARY], task_id)
            # Increment pending counter
            await pipe.incrby("metrics:tasks:state:pending", 1)
            await pipe.execute()

        # Publish queue update for real-time UI
        primary_depth = await self.redis.llen(QUEUE_KEY_MAP[QueueName.PRIMARY])
        pending_count = await self.redis_service.get_state_counter("pending")
        
        await self.redis_service.publish_queue_update({
            "type": "task_created",
            "task_id": task_id,
            "queue_depths": {
                "primary": primary_depth
            },
            "state_counts": {
                "pending": pending_count
            },
            "timestamp": now.isoformat()
        })

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
        await self.redis.lpush(QUEUE_KEY_MAP[QueueName.RETRY], task_id)

        return True

    async def requeue_orphaned_tasks(self) -> Dict[str, any]:
        """Find and re-queue orphaned tasks."""
        found_count = 0
        requeued_count = 0
        errors = []

        try:
            # Get all task IDs from all queues to check what's already queued
            queued_task_ids = set()
            
            # Check primary queue
            primary_tasks = await self.redis.lrange(QUEUE_KEY_MAP[QueueName.PRIMARY], 0, -1)
            queued_task_ids.update(primary_tasks)
            
            # Check retry queue
            retry_tasks = await self.redis.lrange(QUEUE_KEY_MAP[QueueName.RETRY], 0, -1)
            queued_task_ids.update(retry_tasks)
            
            # Check scheduled queue (sorted set)
            scheduled_tasks = await self.redis.zrange(QUEUE_KEY_MAP[QueueName.SCHEDULED], 0, -1)
            queued_task_ids.update(scheduled_tasks)
            
            # Check DLQ
            dlq_tasks = await self.redis.lrange(QUEUE_KEY_MAP[QueueName.DLQ], 0, -1)
            queued_task_ids.update(dlq_tasks)

            # Scan all task keys to find orphaned ones
            async for key in self.redis.scan_iter("task:*"):
                task_id = key.split(":", 1)[1]  # Extract task_id from "task:uuid"
                
                # Get task state
                task_state = await self.redis.hget(key, "state")
                
                if task_state == TaskState.PENDING.value and task_id not in queued_task_ids:
                    found_count += 1
                    
                    try:
                        # Re-queue the orphaned task in primary queue
                        await self.redis.lpush(QUEUE_KEY_MAP[QueueName.PRIMARY], task_id)
                        
                        # Update the task's updated_at timestamp
                        await self.redis.hset(key, "updated_at", datetime.utcnow().isoformat())
                        
                        requeued_count += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to requeue task {task_id}: {str(e)}"
                        errors.append(error_msg)

            return {
                "found": found_count,
                "requeued": requeued_count,
                "errors": errors,
                "message": f"Found {found_count} orphaned tasks, successfully requeued {requeued_count}"
            }

        except Exception as e:
            errors.append(f"Error during orphaned task scan: {str(e)}")
            return {
                "found": found_count,
                "requeued": requeued_count,
                "errors": errors,
                "message": f"Partial completion due to error: {str(e)}"
            }

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task and all its associated data from the system."""
        try:
            # Use Redis transaction to ensure atomicity
            async with self.redis.pipeline(transaction=True) as pipe:
                # Delete the main task hash
                await pipe.delete(f"task:{task_id}")
                
                # Delete any corresponding dead-letter queue hash
                await pipe.delete(f"dlq:task:{task_id}")
                
                # Remove the task_id from all potential list-based queues
                await pipe.lrem(QUEUE_KEY_MAP[QueueName.PRIMARY], 0, task_id)
                await pipe.lrem(QUEUE_KEY_MAP[QueueName.RETRY], 0, task_id)
                await pipe.lrem(QUEUE_KEY_MAP[QueueName.DLQ], 0, task_id)
                
                # Remove the task_id from the scheduled sorted set
                await pipe.zrem(QUEUE_KEY_MAP[QueueName.SCHEDULED], task_id)
                
                await pipe.execute()
            
            return True
        except Exception:
            return False

    async def get_task_ids_by_status(self, status: TaskState, limit: Optional[int] = None) -> List[str]:
        """Get a list of task IDs filtered by their status."""
        task_ids = []
        count = 0
        
        try:
            async for key in self.redis.scan_iter("task:*"):
                # Check if we've reached the limit
                if limit is not None and count >= limit:
                    break
                
                # Get task state
                task_state = await self.redis.hget(key, "state")
                
                if task_state == status.value:
                    # Extract task_id from "task:uuid" format
                    task_id = key.split(":", 1)[1]
                    task_ids.append(task_id)
                    count += 1
            
            return task_ids
        except Exception:
            return []


class QueueService:
    """Service for managing queues and monitoring."""

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service.redis
        self.redis_service = redis_service

    async def get_queue_status(self) -> QueueStatus:
        """Get comprehensive queue status using efficient counters."""
        # Get queue depths using centralized key mapping
        primary_depth = await self.redis.llen(QUEUE_KEY_MAP[QueueName.PRIMARY])
        retry_depth = await self.redis.llen(QUEUE_KEY_MAP[QueueName.RETRY])
        scheduled_count = await self.redis.zcard(QUEUE_KEY_MAP[QueueName.SCHEDULED])
        dlq_depth = await self.redis.llen(QUEUE_KEY_MAP[QueueName.DLQ])

        queues = {
            QueueName.PRIMARY.value: primary_depth,
            QueueName.RETRY.value: retry_depth,
            QueueName.SCHEDULED.value: scheduled_count,
            QueueName.DLQ.value: dlq_depth,
        }

        # Get task counts by state using efficient counters
        states = await self.redis_service.get_all_state_counters()
        
        # Convert to uppercase keys to match TaskState enum values
        states_upper = {k.upper(): v for k, v in states.items()}

        # Calculate adaptive retry ratio
        retry_ratio = self._calculate_adaptive_retry_ratio(retry_depth)

        return QueueStatus(queues=queues, states=states_upper, retry_ratio=retry_ratio)

    async def get_dlq_tasks(self, limit: int = 100) -> List[TaskDetail]:
        """Get tasks from dead letter queue."""
        task_ids = await self.redis.lrange(QUEUE_KEY_MAP[QueueName.DLQ], 0, limit - 1)
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

    async def list_tasks_in_queue(self, queue_name: str, limit: int = 10) -> List[str]:
        """Get a list of task IDs from a specific queue."""
        # Convert string queue name to enum for lookup
        try:
            queue_enum = QueueName(queue_name)
        except ValueError:
            return []
        
        queue_key = QUEUE_KEY_MAP.get(queue_enum)
        if not queue_key:
            return []

        if queue_enum == QueueName.SCHEDULED:
            # Scheduled queue is a sorted set
            return await self.redis.zrange(queue_key, 0, limit - 1)
        else:
            # Other queues are lists
            return await self.redis.lrange(queue_key, 0, limit - 1)

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

    def __init__(self, redis_service: RedisService, celery_app: Optional[Celery] = None):
        self.redis_service = redis_service
        self.celery_app = celery_app

    async def check_health(self) -> Dict[str, any]:
        """Perform comprehensive health check."""
        # Check Redis
        redis_ok = await self.redis_service.ping()

        # Check workers through Redis heartbeat mechanism
        workers_ok = await self._check_workers_via_redis()

        # Overall status
        status = "healthy" if redis_ok and workers_ok else "unhealthy"

        return {
            "status": status,
            "components": {
                "redis": redis_ok,
                "workers": workers_ok,
            },
            "note": "Use /api/v1/workers/ for detailed circuit breaker status",
            "timestamp": datetime.utcnow(),
        }

    async def _check_workers_via_redis(self) -> bool:
        """Check worker health via Redis heartbeat keys."""
        try:
            # Look for worker heartbeat keys that should be updated regularly
            # Workers should set heartbeat keys like "worker:heartbeat:{worker_id}"
            heartbeat_keys = []
            async for key in self.redis_service.redis.scan_iter("worker:heartbeat:*"):
                heartbeat_keys.append(key)
            
            if not heartbeat_keys:
                # No heartbeat keys found - workers might not be running
                return False
            
            # Check if any heartbeat is recent (within last 60 seconds)
            import time
            current_time = time.time()
            recent_heartbeats = 0
            
            for key in heartbeat_keys:
                try:
                    heartbeat_time = await self.redis_service.redis.get(key)
                    if heartbeat_time:
                        heartbeat_timestamp = float(heartbeat_time)
                        if current_time - heartbeat_timestamp < 60:  # Within last 60 seconds
                            recent_heartbeats += 1
                except (ValueError, TypeError):
                    continue
            
            return recent_heartbeats > 0
            
        except Exception:
            # If we can't check heartbeats, fall back to checking if queues are being processed
            return await self._check_queue_activity()

    async def _check_queue_activity(self) -> bool:
        """Fallback: Check if queues show signs of being processed."""
        try:
            # Check if there are any tasks in ACTIVE state (being processed)
            active_count = 0
            async for key in self.redis_service.redis.scan_iter("task:*"):
                state = await self.redis_service.redis.hget(key, "state")
                if state == TaskState.ACTIVE.value:
                    active_count += 1
                    if active_count > 0:  # Found at least one active task
                        return True
            
            # If no active tasks, check if we have any completed tasks recently
            # This indicates workers were active recently
            recent_completions = 0
            import time
            current_time = time.time()
            
            async for key in self.redis_service.redis.scan_iter("task:*"):
                completed_at = await self.redis_service.redis.hget(key, "completed_at")
                if completed_at:
                    try:
                        completed_timestamp = datetime.fromisoformat(completed_at).timestamp()
                        if current_time - completed_timestamp < 300:  # Within last 5 minutes
                            recent_completions += 1
                            if recent_completions > 0:
                                return True
                    except (ValueError, TypeError):
                        continue
            
            # If we have pending tasks but no recent activity, workers might be down
            pending_count = 0
            pending_count += await self.redis_service.redis.llen(QUEUE_KEY_MAP[QueueName.PRIMARY])
            pending_count += await self.redis_service.redis.llen(QUEUE_KEY_MAP[QueueName.RETRY])
            
            # If there are pending tasks but no recent activity, workers are likely down
            if pending_count > 0:
                return False
            
            # No pending tasks and no recent activity - this could be normal (no work to do)
            # In this case, we'll assume workers are healthy
            return True
            
        except Exception:
            # If all checks fail, assume workers are down
            return False


# Global service instances (will be initialized in main.py)
redis_service: Optional[RedisService] = None
task_service: Optional[TaskService] = None
queue_service: Optional[QueueService] = None
health_service: Optional[HealthService] = None
