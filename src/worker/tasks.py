# src/worker/tasks.py
"""
Celery tasks for text summarization and task processing.

Refactored for consistent async data access and idiomatic Celery patterns,
suitable for a FastAPI-based monitoring frontend.
"""

import asyncio
import json
import os
import random
import time
from datetime import datetime

import redis.asyncio as aioredis
from celery import Celery, Task
from celery.worker.control import Panel

from circuit_breaker import (
    call_openrouter_api,
    get_circuit_breaker_status,
    reset_circuit_breaker,
)
from config import settings

# --- Custom Exceptions ----------------------------------------------------


class TaskError(Exception):
    """Base exception for task errors."""

    pass


class TransientError(TaskError):
    """Error that should trigger a retry."""

    pass


class PermanentError(TaskError):
    """Error that should not trigger a retry."""

    pass


# --- Constants ------------------------------------------------------------

ERROR_CLASSIFICATIONS = {
    400: PermanentError,  # Bad Request
    401: PermanentError,  # Invalid credentials
    402: TransientError,  # Insufficient credits
    403: PermanentError,  # Forbidden
    404: PermanentError,  # Not Found
    429: TransientError,  # Rate Limited
    500: TransientError,  # Internal Server Error
    503: TransientError,  # Service Unavailable
}

RETRY_SCHEDULES = {
    "InsufficientCredits": [300, 600, 1800],  # 5min, 10min, 30min
    "RateLimitError": [60, 120, 300, 600],
    "ServiceUnavailable": [5, 10, 30, 60, 120],
    "NetworkTimeout": [2, 5, 10, 30, 60],
    "Default": [5, 15, 60, 300],
}

# --- Celery App Setup -----------------------------------------------------

app = Celery(
    "asynctaskflow-worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Worker settings
    worker_concurrency=settings.worker_concurrency,
    worker_prefetch_multiplier=settings.worker_prefetch_multiplier,
    task_soft_time_limit=settings.task_soft_time_limit,
    task_time_limit=settings.task_time_limit,
    # Result backend settings
    result_expires=3600,  # 1 hour
    # Task routing
    task_routes={
        "summarize_text": {"queue": "celery"},
        "process_scheduled_tasks": {"queue": "celery"},
    },
)

# --- Remote-Control Health Commands --------------------------------------


@Panel.register
def get_worker_health(panel, **kwargs):
    """Return health info for this worker (invoked via broadcast)."""
    cb_status = get_circuit_breaker_status()
    return {
        "worker_id": f"worker-{os.getpid()}",
        "circuit_breaker": cb_status,
        "status": "healthy" if cb_status["state"] != "open" else "unhealthy",
        "timestamp": time.time(),
    }


@Panel.register
def reset_worker_circuit_breaker(panel, **kwargs):
    """Reset the circuit breaker on this worker (invoked via broadcast)."""
    try:
        reset_circuit_breaker()
        return {
            "status": "success",
            "message": "Circuit breaker reset.",
            "new_state": get_circuit_breaker_status(),
            "worker_id": f"worker-{os.getpid()}",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "worker_id": f"worker-{os.getpid()}",
        }


# --- Async Redis and State Management Helpers -----------------------------


def get_async_redis_connection() -> aioredis.Redis:
    """Get an async Redis connection."""
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def classify_error(status_code: int, error_message: str) -> str:
    """Classify error as transient or permanent."""
    if status_code in ERROR_CLASSIFICATIONS:
        err_cls = ERROR_CLASSIFICATIONS[status_code]
        if err_cls is TransientError:
            if status_code == 402:
                return "InsufficientCredits"
            if status_code == 429:
                return "RateLimitError"
            if status_code == 503:
                return "ServiceUnavailable"
            return "NetworkTimeout"
        return "PermanentError"
    # Fallback based on message content
    # (assuming this logic is sound for your use case)
    return "Default"


def calculate_retry_delay(retry_count: int, error_type: str) -> float:
    """Calculate retry delay with exponential backoff and jitter."""
    schedule = RETRY_SCHEDULES.get(error_type, RETRY_SCHEDULES["Default"])
    base_delay = schedule[min(retry_count, len(schedule) - 1)]
    jitter = random.uniform(0, base_delay * 0.1)
    return base_delay + jitter


async def update_task_state(
    redis_conn: aioredis.Redis, task_id: str, state: str, **kwargs
) -> None:
    """Update task state and metadata in Redis asynchronously."""
    fields = {"state": state, "updated_at": datetime.utcnow().isoformat()}
    fields.update(kwargs)

    # Serialize complex types
    for key, value in fields.items():
        if isinstance(value, (dict, list)):
            fields[key] = json.dumps(value)
        elif value is not None:
            fields[key] = str(value)

    await redis_conn.hset(f"task:{task_id}", mapping=fields)


async def move_to_dlq(
    redis_conn: aioredis.Redis, task_id: str, reason: str, error_type: str = "Unknown"
) -> None:
    """Move a task to the dead-letter queue asynchronously."""
    await update_task_state(
        redis_conn,
        task_id,
        "DLQ",
        last_error=reason,
        error_type=error_type,
        completed_at=datetime.utcnow().isoformat(),
    )
    await redis_conn.lpush("dlq:tasks", task_id)


async def schedule_task_for_retry(
    redis_conn: aioredis.Redis, task_id: str, retry_count: int, exc: Exception
) -> None:
    """Schedule a task for a future retry by adding it to a sorted set."""
    error_type = classify_error(getattr(exc, "status_code", 0), str(exc))
    delay = calculate_retry_delay(retry_count, error_type)
    retry_at_timestamp = time.time() + delay

    await update_task_state(
        redis_conn,
        task_id,
        "SCHEDULED",
        retry_count=retry_count + 1,
        last_error=str(exc),
        error_type=error_type,
        retry_after=datetime.fromtimestamp(retry_at_timestamp).isoformat(),
    )
    await redis_conn.zadd("tasks:scheduled", {task_id: retry_at_timestamp})


async def summarize_text_with_pybreaker(content: str) -> str:
    """Summarize text via OpenRouter protected by a circuit breaker."""
    if not settings.openrouter_api_key:
        raise PermanentError("OpenRouter API key not configured")
    try:
        return await call_openrouter_api(content)
    except Exception as e:
        msg = str(e)
        if "circuit breaker" in msg.lower():
            raise TransientError(f"Circuit breaker protection: {msg}")

        # Simple status code parsing
        code = 0
        if "status_code=" in msg:
            try:
                code_str = msg.split("status_code=")[1].split(" ")[0].strip()
                code = int(code_str)
            except (IndexError, ValueError):
                pass

        if classify_error(code, msg) == "PermanentError":
            raise PermanentError(f"OpenRouter API error: {msg}")
        else:
            exc = TransientError(f"OpenRouter API error: {msg}")
            exc.status_code = code
            raise exc


# --- Celery Tasks ---------------------------------------------------------


@app.task(name="summarize_text", bind=True)
def summarize_task(self: Task, task_id: str) -> str:
    """
    Main summarization task using custom retry scheduling.
    `bind=True` provides access to the task instance via `self`.
    """
    redis_conn = get_async_redis_connection()
    retry_count = self.request.retries  # Use Celery's built-in retry counter

    async def _run_task():
        data = await redis_conn.hgetall(f"task:{task_id}")
        if not data:
            raise PermanentError(f"Task {task_id} not found in Redis.")

        content = data.get("content", "")
        if not content:
            raise PermanentError("No content to summarize.")

        # Check for max retries before execution
        if retry_count >= settings.max_retries:
            raise PermanentError(f"Max retries ({settings.max_retries}) exceeded.")

        await update_task_state(
            redis_conn, task_id, "ACTIVE", worker_id=self.request.hostname
        )

        result = await summarize_text_with_pybreaker(content)

        await update_task_state(
            redis_conn,
            task_id,
            "COMPLETED",
            result=result,
            completed_at=datetime.utcnow().isoformat(),
        )
        return f"Task {task_id} completed successfully."

    try:
        return asyncio.run(_run_task())
    except PermanentError as e:
        asyncio.run(move_to_dlq(redis_conn, task_id, str(e), "PermanentError"))
        return f"Task {task_id} moved to DLQ: {e}"
    except TransientError as e:
        # Schedule for retry and let the task complete. The beat task will requeue it.
        asyncio.run(schedule_task_for_retry(redis_conn, task_id, retry_count, e))
        return f"Task {task_id} failed, scheduled for retry."
    except Exception as e:
        # Catch any other unexpected errors and treat them as transient
        exc = TransientError(f"An unexpected error occurred: {str(e)}")
        asyncio.run(schedule_task_for_retry(redis_conn, task_id, retry_count, exc))
        return f"Task {task_id} failed with unexpected error, scheduled for retry."


@app.task(name="process_scheduled_tasks")
def process_scheduled_tasks() -> str:
    """
    Periodically run by Celery Beat to move scheduled tasks back to the pending queue.
    """
    redis_conn = get_async_redis_connection()

    async def _run_processing():
        now = time.time()
        # Get up to 100 tasks that are due to be retried
        due_tasks = await redis_conn.zrangebyscore(
            "tasks:scheduled", 0, now, start=0, num=100
        )

        if not due_tasks:
            return 0

        # Use a pipeline for efficiency
        async with redis_conn.pipeline() as pipe:
            for task_id in due_tasks:
                pipe.lpush("tasks:pending:retry", task_id)
                pipe.zrem("tasks:scheduled", task_id)
                # Update state to PENDING so the UI reflects it's ready to be picked up
                await update_task_state(redis_conn, task_id, "PENDING")
            await pipe.execute()

        return len(due_tasks)

    moved_count = asyncio.run(_run_processing())
    return f"Moved {moved_count} tasks from scheduled to retry queue."


# --- Queue Consumer Task --------------------------------------------------


def calculate_adaptive_retry_ratio(retry_depth: int) -> float:
    """Calculate adaptive retry ratio based on queue pressure."""
    if retry_depth < settings.retry_queue_warning:
        return settings.default_retry_ratio  # Normal: 30%
    elif retry_depth < settings.retry_queue_critical:
        return 0.2  # Warning: 20%
    else:
        return 0.1  # Critical: 10%


@app.task(name="consume_tasks", bind=True)
def consume_tasks(self: Task) -> str:
    """
    Consumer task that pulls task IDs from Redis queues and processes them.
    This runs in a continuous loop on each worker.
    """
    import logging
    import redis
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting task consumer on worker {self.request.hostname}")
    
    # Use synchronous Redis for BLPOP
    redis_conn = redis.from_url(settings.redis_url, decode_responses=True)
    
    processed_count = 0
    
    try:
        while True:
            try:
                # Get current retry queue depth for adaptive ratio
                retry_depth = redis_conn.llen("tasks:pending:retry")
                retry_ratio = calculate_adaptive_retry_ratio(retry_depth)
                
                # Decide which queue to check first based on retry ratio
                if random.random() > retry_ratio:
                    # Try primary queue first (70% of the time by default)
                    queues = ["tasks:pending:primary", "tasks:pending:retry"]
                else:
                    # Try retry queue first (30% of the time by default)
                    queues = ["tasks:pending:retry", "tasks:pending:primary"]
                
                # Use BLPOP to wait for a task ID from either queue (timeout: 5 seconds)
                result = redis_conn.blpop(queues, timeout=5)
                
                if result is None:
                    # Timeout occurred, continue loop (this is normal)
                    continue
                
                queue_name, task_id = result
                logger.info(f"Received task {task_id} from {queue_name}")
                
                # Remove task from the queue it came from (already done by BLPOP)
                # Now trigger the actual summarization task
                summarize_task.delay(task_id)
                
                processed_count += 1
                logger.info(f"Dispatched task {task_id} for processing (total: {processed_count})")
                
            except redis.RedisError as e:
                logger.error(f"Redis error in consumer: {e}")
                time.sleep(5)  # Wait before retrying
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error in consumer: {e}")
                time.sleep(1)  # Brief pause before continuing
                continue
                
    except KeyboardInterrupt:
        logger.info("Consumer task interrupted, shutting down gracefully")
        return f"Consumer stopped after processing {processed_count} tasks"
    
    except Exception as e:
        logger.error(f"Consumer task failed: {e}")
        raise
