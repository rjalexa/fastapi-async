# src/api/services.py
"""Service layer for task and queue management."""

import json
import math
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import redis.asyncio as redis
from celery import Celery

from config import settings
from redis_config import (
    get_standard_redis,
    get_pipeline_redis,
    get_redis_manager,
    initialize_redis,
    close_redis
)
from redis_config_simple import (
    initialize_simple_redis,
    get_simple_redis_manager,
    close_simple_redis,
    get_simple_redis
)
from schemas import (
    QueueStatus,
    TaskDetail,
    TaskState,
    QueueName,
    QUEUE_KEY_MAP,
    TaskListResponse,
    TaskSummaryListResponse,
    TaskSummary,
    TaskType,
)


class RedisService:
    """Redis service for task and queue management with optimized connection pool."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._manager = None
        self._simple_manager = None
        self.redis = None

    async def initialize(self):
        """Initialize the optimized Redis connection manager with fallback."""
        if self._manager is None and self._simple_manager is None:
            try:
                # Try optimized Redis configuration first
                self._manager = await initialize_redis(self.redis_url)
                self.redis = await get_standard_redis()
                print("Using optimized Redis connection pool")
                # Test the connection
                await self.redis.ping()
                print("Optimized Redis connection successful")
            except Exception as e:
                print(f"Optimized Redis failed ({e}), falling back to simple Redis")
                # Clean up failed optimized connection
                if self._manager:
                    try:
                        await close_redis()
                    except:
                        pass
                    self._manager = None
                
                # Fall back to simple Redis configuration
                try:
                    self._simple_manager = await initialize_simple_redis(self.redis_url)
                    self.redis = await get_simple_redis()
                    print("Using simple Redis connection")
                    # Test the simple connection
                    await self.redis.ping()
                    print("Simple Redis connection successful")
                except Exception as e2:
                    print(f"Simple Redis also failed: {e2}")
                    # Create a basic fallback connection
                    import redis.asyncio as redis
                    self.redis = redis.from_url(self.redis_url, decode_responses=True)
                    print("Using basic Redis connection as last resort")

    async def close(self):
        """Close Redis connection."""
        if self._manager:
            await close_redis()
            self._manager = None
        if self._simple_manager:
            await close_simple_redis()
            self._simple_manager = None
        self.redis = None

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            if self.redis is None:
                await self.initialize()
            result = await self.redis.ping()
            return result is True or result == b'PONG' or result == 'PONG'
        except Exception as e:
            print(f"Redis ping failed: {e}")
            return False

    async def get_pool_stats(self) -> dict:
        """Get Redis connection pool statistics."""
        if self._manager:
            return await self._manager.get_pool_stats()
        elif self._simple_manager:
            return await self._simple_manager.get_pool_stats()
        return {"status": "not_initialized"}


    async def publish_queue_update(self, update_data: Dict) -> None:
        """Publish queue update to Redis pub/sub channel."""
        await self.redis.publish("queue-updates", json.dumps(update_data))


class TaskService:
    """Service for managing tasks."""

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service.redis
        self.redis_service = redis_service

    async def create_task(
        self,
        content: str,
        task_type: TaskType = TaskType.SUMMARIZE,
        metadata: Optional[Dict[str, any]] = None,
    ) -> str:
        """Create a new task and queue it for processing."""
        task_id = str(uuid4())
        now = datetime.utcnow()

        task_data = {
            "task_id": task_id,
            "content": content,
            "task_type": task_type.value,
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
            "state_history": json.dumps(
                [{"state": TaskState.PENDING.value, "timestamp": now.isoformat()}]
            ),
        }

        # Add metadata if provided
        if metadata:
            task_data["metadata"] = json.dumps(metadata)

        # Use Redis transaction to ensure atomicity
        async with self.redis.pipeline(transaction=True) as pipe:
            # Store task metadata and queue in primary queue atomically
            await pipe.hset(f"task:{task_id}", mapping=task_data)
            await pipe.lpush(QUEUE_KEY_MAP[QueueName.PRIMARY], task_id)
            await pipe.execute()

        # Publish queue update for real-time UI
        primary_depth = await self.redis.llen(QUEUE_KEY_MAP[QueueName.PRIMARY])

        await self.redis_service.publish_queue_update(
            {
                "type": "task_created",
                "task_id": task_id,
                "queue_depths": {"primary": primary_depth},
                "timestamp": now.isoformat(),
            }
        )

        return task_id

    async def get_task(self, task_id: str) -> Optional[TaskDetail]:
        """Get task details by ID."""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return None

        # Parse JSON fields
        error_history = json.loads(task_data.get("error_history", "[]"))
        state_history = json.loads(task_data.get("state_history", "[]"))

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

        # Get task type, defaulting to SUMMARIZE for backward compatibility
        task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
        try:
            task_type = TaskType(task_type_str)
        except ValueError:
            task_type = TaskType.SUMMARIZE

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
            task_type=task_type,
            error_history=error_history,
            state_history=state_history,
        )

    async def retry_task(self, task_id: str, reset_retry_count: bool = False) -> bool:
        """Manually retry a failed task."""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return False

        current_state = task_data.get("state")
        if current_state not in [TaskState.FAILED.value, TaskState.DLQ.value]:
            return False

        now = datetime.utcnow()
        state_history = json.loads(task_data.get("state_history", "[]"))
        state_history.append(
            {"state": TaskState.PENDING.value, "timestamp": now.isoformat()}
        )

        # Update task state
        updates = {
            "state": TaskState.PENDING.value,
            "updated_at": now.isoformat(),
            "state_history": json.dumps(state_history),
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
            primary_tasks = await self.redis.lrange(
                QUEUE_KEY_MAP[QueueName.PRIMARY], 0, -1
            )
            queued_task_ids.update(primary_tasks)

            # Check retry queue
            retry_tasks = await self.redis.lrange(QUEUE_KEY_MAP[QueueName.RETRY], 0, -1)
            queued_task_ids.update(retry_tasks)

            # Check scheduled queue (sorted set)
            scheduled_tasks = await self.redis.zrange(
                QUEUE_KEY_MAP[QueueName.SCHEDULED], 0, -1
            )
            queued_task_ids.update(scheduled_tasks)

            # Check DLQ
            dlq_tasks = await self.redis.lrange(QUEUE_KEY_MAP[QueueName.DLQ], 0, -1)
            queued_task_ids.update(dlq_tasks)

            # Scan all task keys to find orphaned ones
            async for key in self.redis.scan_iter("task:*"):
                task_id = key.split(":", 1)[1]  # Extract task_id from "task:uuid"

                # Get task state
                task_state = await self.redis.hget(key, "state")

                if (
                    task_state == TaskState.PENDING.value
                    and task_id not in queued_task_ids
                ):
                    found_count += 1

                    try:
                        # Re-queue the orphaned task in primary queue
                        await self.redis.lpush(
                            QUEUE_KEY_MAP[QueueName.PRIMARY], task_id
                        )

                        # Update the task's updated_at timestamp
                        await self.redis.hset(
                            key, "updated_at", datetime.utcnow().isoformat()
                        )

                        requeued_count += 1

                    except Exception as e:
                        error_msg = f"Failed to requeue task {task_id}: {str(e)}"
                        errors.append(error_msg)

            return {
                "found": found_count,
                "requeued": requeued_count,
                "errors": errors,
                "message": f"Found {found_count} orphaned tasks, successfully requeued {requeued_count}",
            }

        except Exception as e:
            errors.append(f"Error during orphaned task scan: {str(e)}")
            return {
                "found": found_count,
                "requeued": requeued_count,
                "errors": errors,
                "message": f"Partial completion due to error: {str(e)}",
            }

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task and all its associated data from the system."""
        try:
            # First, get the task's current state to update counters
            task_data = await self.redis.hgetall(f"task:{task_id}")
            if not task_data:
                return False  # Task doesn't exist
            
            current_state = task_data.get("state")
            
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
        except Exception as e:
            # If there's an error getting task data but we know the task exists,
            # try to delete it anyway without updating counters
            try:
                # Check if task exists in Redis at all
                exists = await self.redis.exists(f"task:{task_id}")
                if not exists:
                    return False
                
                # Force delete without counter updates for corrupted tasks
                async with self.redis.pipeline(transaction=True) as pipe:
                    await pipe.delete(f"task:{task_id}")
                    await pipe.delete(f"dlq:task:{task_id}")
                    await pipe.lrem(QUEUE_KEY_MAP[QueueName.PRIMARY], 0, task_id)
                    await pipe.lrem(QUEUE_KEY_MAP[QueueName.RETRY], 0, task_id)
                    await pipe.lrem(QUEUE_KEY_MAP[QueueName.DLQ], 0, task_id)
                    await pipe.zrem(QUEUE_KEY_MAP[QueueName.SCHEDULED], task_id)
                    await pipe.execute()
                
                return True
            except Exception:
                return False

    async def list_tasks(
        self,
        status: Optional[TaskState] = None,
        task_type: Optional[TaskType] = None,
        queue: Optional[QueueName] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
        task_id: Optional[str] = None,
    ) -> TaskListResponse:
        """List tasks with filtering, sorting, and pagination."""
        # If task_id is provided, do substring search instead of exact match
        if task_id:
            # First try exact match for backward compatibility
            exact_task = await self.get_task(task_id)
            if exact_task:
                return TaskListResponse(
                    tasks=[exact_task],
                    page=1,
                    page_size=1,
                    total_items=1,
                    total_pages=1,
                    status=exact_task.state,
                )

            # If no exact match, do substring search
            all_tasks = []
            async for key in self.redis.scan_iter("task:*"):
                task_data = await self.redis.hgetall(key)
                if (
                    task_data
                    and task_id.lower() in task_data.get("task_id", "").lower()
                ):
                    all_tasks.append(task_data)

            if not all_tasks:
                return TaskListResponse(
                    tasks=[], page=1, page_size=page_size, total_items=0, total_pages=0
                )

            # Apply other filters to substring matches
            filtered_tasks = []
            for task_data in all_tasks:
                if status and task_data.get("state") != status.value:
                    continue

                # Safely parse created_at field
                try:
                    created_at_str = task_data.get("created_at")
                    if created_at_str:
                        created_at = datetime.fromisoformat(created_at_str)
                        if start_date and created_at < start_date:
                            continue
                        if end_date and created_at > end_date:
                            continue
                except (ValueError, TypeError):
                    # Skip tasks with invalid created_at format
                    continue

                filtered_tasks.append(task_data)

            # Sort and paginate the substring matches
            reverse = sort_order.lower() == "desc"

            def sort_key_func(task_data):
                val = task_data.get(sort_by)
                if val is None:
                    if sort_by in ["created_at", "updated_at", "completed_at"]:
                        return datetime.min if not reverse else datetime.max
                    elif sort_by in ["retry_count", "max_retries"]:
                        return 0
                    else:
                        return ""

                if isinstance(val, str) and val.isdigit():
                    return int(val)
                if isinstance(val, str):
                    try:
                        return datetime.fromisoformat(val)
                    except ValueError:
                        return val
                return val

            try:
                filtered_tasks.sort(key=sort_key_func, reverse=reverse)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid sort key '{sort_by}': {e}")

            # Pagination for substring matches
            total_items = len(filtered_tasks)
            total_pages = math.ceil(total_items / page_size)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_data = filtered_tasks[start_index:end_index]

            tasks = []
            for task_data in paginated_data:
                try:
                    error_history = json.loads(task_data.get("error_history", "[]"))
                    state_history = json.loads(task_data.get("state_history", "[]"))

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

                    # Get task type, defaulting to SUMMARIZE for backward compatibility
                    task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
                    try:
                        task_type = TaskType(task_type_str)
                    except ValueError:
                        task_type = TaskType.SUMMARIZE

                    tasks.append(
                        TaskDetail(
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
                            task_type=task_type,
                            error_history=error_history,
                            state_history=state_history,
                        )
                    )
                except (ValueError, TypeError, KeyError):
                    continue

            return TaskListResponse(
                tasks=tasks,
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                status=status,
            )

        all_tasks = []
        async for key in self.redis.scan_iter("task:*"):
            task_data = await self.redis.hgetall(key)
            if task_data:
                all_tasks.append(task_data)

        # If no tasks found, return empty result
        if not all_tasks:
            return TaskListResponse(
                tasks=[], page=page, page_size=page_size, total_items=0, total_pages=0
            )

        # Filtering
        filtered_tasks = []
        for task_data in all_tasks:
            if status and task_data.get("state") != status.value:
                continue

            # Filter by task type
            if task_type:
                task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
                if task_type_str != task_type.value:
                    continue

            # Safely parse created_at field
            try:
                created_at_str = task_data.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    if start_date and created_at < start_date:
                        continue
                    if end_date and created_at > end_date:
                        continue
            except (ValueError, TypeError):
                # Skip tasks with invalid created_at format
                continue

            # This is a simplified queue filter. A more robust implementation
            # would require storing the queue in the task hash.
            if queue:
                # This is a placeholder for more complex queue filtering logic
                pass

            filtered_tasks.append(task_data)

        # If no tasks after filtering, return empty result
        if not filtered_tasks:
            return TaskListResponse(
                tasks=[], page=page, page_size=page_size, total_items=0, total_pages=0
            )

        # Sorting
        reverse = sort_order.lower() == "desc"

        def sort_key_func(task_data):
            val = task_data.get(sort_by)
            if val is None:
                # If the field doesn't exist, return a default value for sorting
                if sort_by in ["created_at", "updated_at", "completed_at"]:
                    # For datetime fields, put invalid/missing dates at the end
                    return datetime.min if reverse else datetime.max
                elif sort_by in ["retry_count", "max_retries"]:
                    return 0
                else:
                    return ""

            if isinstance(val, str) and val.isdigit():
                return int(val)
            if isinstance(val, str):
                try:
                    parsed_date = datetime.fromisoformat(val)
                    # Check if this is an invalid date (datetime.min means invalid)
                    if parsed_date == datetime.min:
                        # Put invalid dates at the end regardless of sort order
                        return datetime.min if reverse else datetime.max
                    return parsed_date
                except ValueError:
                    # For non-datetime strings that can't be parsed, put them at the end
                    if sort_by in ["created_at", "updated_at", "completed_at"]:
                        return datetime.min if reverse else datetime.max
                    return val
            return val

        try:
            filtered_tasks.sort(key=sort_key_func, reverse=reverse)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid sort key '{sort_by}': {e}")

        # Pagination
        total_items = len(filtered_tasks)
        total_pages = math.ceil(total_items / page_size)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_data = filtered_tasks[start_index:end_index]

        def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                return None

        def parse_json_field(field_data: Optional[str]) -> List:
            if not field_data:
                return []
            try:
                return json.loads(field_data)
            except (json.JSONDecodeError, TypeError):
                return []

        tasks = []
        for task_data in paginated_data:
            # Defensively parse all fields to avoid skipping tasks
            task_id_val = task_data.get("task_id", "unknown_id")
            
            try:
                state = TaskState(task_data.get("state", TaskState.FAILED.value))
            except ValueError:
                state = TaskState.FAILED

            try:
                retry_count = int(task_data.get("retry_count", 0))
            except (ValueError, TypeError):
                retry_count = 0

            try:
                max_retries = int(task_data.get("max_retries", settings.max_retries))
            except (ValueError, TypeError):
                max_retries = settings.max_retries

            created_at = parse_iso_date(task_data.get("created_at")) or datetime.min
            updated_at = parse_iso_date(task_data.get("updated_at")) or datetime.min
            completed_at = parse_iso_date(task_data.get("completed_at"))
            retry_after = parse_iso_date(task_data.get("retry_after"))

            error_history = parse_json_field(task_data.get("error_history"))
            state_history = parse_json_field(task_data.get("state_history"))

            task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
            try:
                task_type = TaskType(task_type_str)
            except ValueError:
                task_type = TaskType.SUMMARIZE

            tasks.append(
                TaskDetail(
                    task_id=task_id_val,
                    state=state,
                    content=task_data.get("content", ""),
                    retry_count=retry_count,
                    max_retries=max_retries,
                    last_error=task_data.get("last_error"),
                    error_type=task_data.get("error_type"),
                    retry_after=retry_after,
                    created_at=created_at,
                    updated_at=updated_at,
                    completed_at=completed_at,
                    result=task_data.get("result"),
                    task_type=task_type,
                    error_history=error_history,
                    state_history=state_history,
                )
            )

        return TaskListResponse(
            tasks=tasks,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            status=status,
        )

    async def list_task_summaries(
        self,
        status: Optional[TaskState] = None,
        task_type: Optional[TaskType] = None,
        queue: Optional[QueueName] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
        task_id: Optional[str] = None,
    ) -> TaskSummaryListResponse:
        """List task summaries (without content) with filtering, sorting, and pagination."""
        # If task_id is provided, do substring search instead of exact match
        if task_id:
            # First try exact match for backward compatibility
            exact_task = await self.get_task(task_id)
            if exact_task:
                # Convert TaskDetail to TaskSummary
                task_summary = TaskSummary(
                    task_id=exact_task.task_id,
                    state=exact_task.state,
                    retry_count=exact_task.retry_count,
                    max_retries=exact_task.max_retries,
                    last_error=exact_task.last_error,
                    error_type=exact_task.error_type,
                    retry_after=exact_task.retry_after,
                    created_at=exact_task.created_at,
                    updated_at=exact_task.updated_at,
                    completed_at=exact_task.completed_at,
                    task_type=exact_task.task_type,
                    content_length=len(exact_task.content) if exact_task.content else 0,
                    has_result=bool(exact_task.result),
                    error_history=exact_task.error_history,
                    state_history=exact_task.state_history,
                )
                return TaskSummaryListResponse(
                    tasks=[task_summary],
                    page=1,
                    page_size=1,
                    total_items=1,
                    total_pages=1,
                    status=exact_task.state,
                )

            # If no exact match, do substring search
            all_tasks = []
            async for key in self.redis.scan_iter("task:*"):
                task_data = await self.redis.hgetall(key)
                if (
                    task_data
                    and task_id.lower() in task_data.get("task_id", "").lower()
                ):
                    all_tasks.append(task_data)

            if not all_tasks:
                return TaskSummaryListResponse(
                    tasks=[], page=1, page_size=page_size, total_items=0, total_pages=0
                )

            # Apply other filters to substring matches
            filtered_tasks = []
            for task_data in all_tasks:
                if status and task_data.get("state") != status.value:
                    continue

                # Safely parse created_at field
                try:
                    created_at_str = task_data.get("created_at")
                    if created_at_str:
                        created_at = datetime.fromisoformat(created_at_str)
                        if start_date and created_at < start_date:
                            continue
                        if end_date and created_at > end_date:
                            continue
                except (ValueError, TypeError):
                    # Skip tasks with invalid created_at format
                    continue

                filtered_tasks.append(task_data)

            # Sort and paginate the substring matches
            reverse = sort_order.lower() == "desc"

            def sort_key_func(task_data):
                val = task_data.get(sort_by)
                if val is None:
                    if sort_by in ["created_at", "updated_at", "completed_at"]:
                        return datetime.min if not reverse else datetime.max
                    elif sort_by in ["retry_count", "max_retries"]:
                        return 0
                    else:
                        return ""

                if isinstance(val, str) and val.isdigit():
                    return int(val)
                if isinstance(val, str):
                    try:
                        return datetime.fromisoformat(val)
                    except ValueError:
                        return val
                return val

            try:
                filtered_tasks.sort(key=sort_key_func, reverse=reverse)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid sort key '{sort_by}': {e}")

            # Pagination for substring matches
            total_items = len(filtered_tasks)
            total_pages = math.ceil(total_items / page_size)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_data = filtered_tasks[start_index:end_index]

            def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
                if not date_str:
                    return None
                try:
                    return datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    return None

            def parse_json_field(field_data: Optional[str]) -> List:
                if not field_data:
                    return []
                try:
                    return json.loads(field_data)
                except (json.JSONDecodeError, TypeError):
                    return []

            tasks = []
            for task_data in paginated_data:
                # Defensively parse all fields to avoid skipping tasks
                task_id_val = task_data.get("task_id", "unknown_id")

                try:
                    state = TaskState(task_data.get("state", TaskState.FAILED.value))
                except ValueError:
                    state = TaskState.FAILED

                try:
                    retry_count = int(task_data.get("retry_count", 0))
                except (ValueError, TypeError):
                    retry_count = 0

                try:
                    max_retries = int(task_data.get("max_retries", settings.max_retries))
                except (ValueError, TypeError):
                    max_retries = settings.max_retries

                created_at = parse_iso_date(task_data.get("created_at")) or datetime.min
                updated_at = parse_iso_date(task_data.get("updated_at")) or datetime.min
                completed_at = parse_iso_date(task_data.get("completed_at"))
                retry_after = parse_iso_date(task_data.get("retry_after"))

                error_history = parse_json_field(task_data.get("error_history"))
                state_history = parse_json_field(task_data.get("state_history"))

                task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    task_type = TaskType.SUMMARIZE

                content = task_data.get("content", "")
                result = task_data.get("result", "")

                tasks.append(
                    TaskSummary(
                        task_id=task_id_val,
                        state=state,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        last_error=task_data.get("last_error"),
                        error_type=task_data.get("error_type"),
                        retry_after=retry_after,
                        created_at=created_at,
                        updated_at=updated_at,
                        completed_at=completed_at,
                        task_type=task_type,
                        content_length=len(content),
                        has_result=bool(result),
                        error_history=error_history,
                        state_history=state_history,
                    )
                )

            return TaskSummaryListResponse(
                tasks=tasks,
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                status=status,
            )

        # If no task_id provided, do normal listing
        all_tasks = []
        async for key in self.redis.scan_iter("task:*"):
            task_data = await self.redis.hgetall(key)
            if task_data:
                all_tasks.append(task_data)

        # If no tasks found, return empty result
        if not all_tasks:
            return TaskSummaryListResponse(
                tasks=[], page=page, page_size=page_size, total_items=0, total_pages=0
            )

        # Filtering
        filtered_tasks = []
        for task_data in all_tasks:
            if status and task_data.get("state") != status.value:
                continue

            # Filter by task type
            if task_type:
                task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
                if task_type_str != task_type.value:
                    continue

            # Safely parse created_at field
            try:
                created_at_str = task_data.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    if start_date and created_at < start_date:
                        continue
                    if end_date and created_at > end_date:
                        continue
            except (ValueError, TypeError):
                # Skip tasks with invalid created_at format
                continue

            # This is a simplified queue filter. A more robust implementation
            # would require storing the queue in the task hash.
            if queue:
                # This is a placeholder for more complex queue filtering logic
                pass

            filtered_tasks.append(task_data)

        # If no tasks after filtering, return empty result
        if not filtered_tasks:
            return TaskSummaryListResponse(
                tasks=[], page=page, page_size=page_size, total_items=0, total_pages=0
            )

        # Sorting
        reverse = sort_order.lower() == "desc"

        def sort_key_func(task_data):
            val = task_data.get(sort_by)
            if val is None:
                # If the field doesn't exist, return a default value for sorting
                if sort_by in ["created_at", "updated_at", "completed_at"]:
                    return datetime.min if not reverse else datetime.max
                elif sort_by in ["retry_count", "max_retries"]:
                    return 0
                else:
                    return ""

            if isinstance(val, str) and val.isdigit():
                return int(val)
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    return val
            return val

        try:
            filtered_tasks.sort(key=sort_key_func, reverse=reverse)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid sort key '{sort_by}': {e}")

        # Pagination
        total_items = len(filtered_tasks)
        total_pages = math.ceil(total_items / page_size)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_data = filtered_tasks[start_index:end_index]

        def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                return None

        def parse_json_field(field_data: Optional[str]) -> List:
            if not field_data:
                return []
            try:
                return json.loads(field_data)
            except (json.JSONDecodeError, TypeError):
                return []

        tasks = []
        for task_data in paginated_data:
            # Defensively parse all fields to avoid skipping tasks
            task_id_val = task_data.get("task_id", "unknown_id")

            try:
                state = TaskState(task_data.get("state", TaskState.FAILED.value))
            except ValueError:
                state = TaskState.FAILED

            try:
                retry_count = int(task_data.get("retry_count", 0))
            except (ValueError, TypeError):
                retry_count = 0

            try:
                max_retries = int(task_data.get("max_retries", settings.max_retries))
            except (ValueError, TypeError):
                max_retries = settings.max_retries

            created_at = parse_iso_date(task_data.get("created_at")) or datetime.min
            updated_at = parse_iso_date(task_data.get("updated_at")) or datetime.min
            completed_at = parse_iso_date(task_data.get("completed_at"))
            retry_after = parse_iso_date(task_data.get("retry_after"))

            error_history = parse_json_field(task_data.get("error_history"))
            state_history = parse_json_field(task_data.get("state_history"))

            task_type_str = task_data.get("task_type", TaskType.SUMMARIZE.value)
            try:
                task_type = TaskType(task_type_str)
            except ValueError:
                task_type = TaskType.SUMMARIZE

            content = task_data.get("content", "")
            result = task_data.get("result", "")

            tasks.append(
                TaskSummary(
                    task_id=task_id_val,
                    state=state,
                    retry_count=retry_count,
                    max_retries=max_retries,
                    last_error=task_data.get("last_error"),
                    error_type=task_data.get("error_type"),
                    retry_after=retry_after,
                    created_at=created_at,
                    updated_at=updated_at,
                    completed_at=completed_at,
                    task_type=task_type,
                    content_length=len(content),
                    has_result=bool(result),
                    error_history=error_history,
                    state_history=state_history,
                )
            )

        return TaskSummaryListResponse(
            tasks=tasks,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            status=status,
        )


class QueueService:
    """Service for managing queues and monitoring."""

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service.redis
        self.redis_service = redis_service

    async def get_queue_status(self) -> QueueStatus:
        """Get comprehensive queue status with coherent counts."""
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

        # Get task counts by state by scanning actual tasks for coherence
        # This ensures the state counts match the actual task states in Redis
        states = {
            "PENDING": 0,
            "ACTIVE": 0,
            "COMPLETED": 0,
            "FAILED": 0,
            "SCHEDULED": 0,
            "DLQ": 0,
        }

        # Count tasks by their actual state
        async for key in self.redis.scan_iter("task:*"):
            try:
                state = await self.redis.hget(key, "state")
                if state and state in states:
                    states[state] += 1
            except Exception:
                # Skip corrupted tasks
                continue

        # Calculate adaptive retry ratio
        retry_ratio = self._calculate_adaptive_retry_ratio(retry_depth)

        return QueueStatus(queues=queues, states=states, retry_ratio=retry_ratio)

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

    def __init__(
        self, redis_service: RedisService, celery_app: Optional[Celery] = None
    ):
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
                        if (
                            current_time - heartbeat_timestamp < 60
                        ):  # Within last 60 seconds
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
                        completed_timestamp = datetime.fromisoformat(
                            completed_at
                        ).timestamp()
                        if (
                            current_time - completed_timestamp < 300
                        ):  # Within last 5 minutes
                            recent_completions += 1
                            if recent_completions > 0:
                                return True
                    except (ValueError, TypeError):
                        continue

            # If we have pending tasks but no recent activity, workers might be down
            pending_count = 0
            pending_count += await self.redis_service.redis.llen(
                QUEUE_KEY_MAP[QueueName.PRIMARY]
            )
            pending_count += await self.redis_service.redis.llen(
                QUEUE_KEY_MAP[QueueName.RETRY]
            )

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
