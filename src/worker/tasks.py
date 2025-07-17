"""Celery tasks for text summarization and task processing."""

import json
import random
import time
from datetime import datetime
from typing import Optional

import httpx
import redis
from celery import Task
from celery.exceptions import Retry

from circuit_breaker import circuit_breaker
from config import settings


class TaskError(Exception):
    """Base exception for task errors."""

    pass


class TransientError(TaskError):
    """Error that should trigger a retry."""

    pass


class PermanentError(TaskError):
    """Error that should not trigger a retry."""

    pass


# Error classification mapping
ERROR_CLASSIFICATIONS = {
    400: PermanentError,  # Bad Request
    401: PermanentError,  # Unauthorized
    403: PermanentError,  # Forbidden
    404: PermanentError,  # Not Found
    429: TransientError,  # Rate Limited
    500: TransientError,  # Internal Server Error
    502: TransientError,  # Bad Gateway
    503: TransientError,  # Service Unavailable
    504: TransientError,  # Gateway Timeout
}

# Retry schedules by error type
RETRY_SCHEDULES = {
    "RateLimitError": [60, 120, 300, 600],  # Start with 1 minute
    "ServiceUnavailable": [5, 10, 30, 60, 120],  # Quick initial retry
    "NetworkTimeout": [2, 5, 10, 30, 60],  # Standard backoff
    "Default": [5, 15, 60, 300],  # Generic schedule
}


def get_redis_connection() -> redis.Redis:
    """Get Redis connection."""
    return redis.from_url(settings.redis_url, decode_responses=True)


def classify_error(status_code: int, error_message: str) -> str:
    """Classify error as transient or permanent."""
    if status_code in ERROR_CLASSIFICATIONS:
        error_class = ERROR_CLASSIFICATIONS[status_code]
        if error_class == TransientError:
            if status_code == 429:
                return "RateLimitError"
            elif status_code == 503:
                return "ServiceUnavailable"
            else:
                return "NetworkTimeout"
        else:
            return "PermanentError"

    # Default classification based on error message
    if any(keyword in error_message.lower() for keyword in ["timeout", "connection"]):
        return "NetworkTimeout"
    elif "rate limit" in error_message.lower():
        return "RateLimitError"
    else:
        return "Default"


def calculate_retry_delay(retry_count: int, error_type: str) -> float:
    """Calculate retry delay with exponential backoff and jitter."""
    schedule = RETRY_SCHEDULES.get(error_type, RETRY_SCHEDULES["Default"])
    base_delay = schedule[min(retry_count, len(schedule) - 1)]
    jitter = random.uniform(0, base_delay * 0.1)
    return base_delay + jitter


async def get_next_task(
    redis_conn: redis.Redis, retry_ratio: float = 0.3
) -> Optional[str]:
    """
    Get next task from queues with configurable retry ratio.

    Args:
        redis_conn: Redis connection
        retry_ratio: Ratio of retry queue consumption (0.0-1.0)

    Returns:
        Task ID or None if no tasks available
    """
    if random.random() > retry_ratio:
        # Try primary queue first
        task_id = redis_conn.lpop("tasks:pending:primary")
        if not task_id:
            task_id = redis_conn.lpop("tasks:pending:retry")
    else:
        # Try retry queue first
        task_id = redis_conn.lpop("tasks:pending:retry")
        if not task_id:
            task_id = redis_conn.lpop("tasks:pending:primary")

    return task_id


async def update_task_state(
    redis_conn: redis.Redis, task_id: str, state: str, **kwargs
) -> None:
    """Update task state and metadata in Redis."""
    updates = {
        "state": state,
        "updated_at": datetime.utcnow().isoformat(),
    }
    updates.update(kwargs)

    # Convert non-string values to strings for Redis
    for key, value in updates.items():
        if isinstance(value, (dict, list)):
            updates[key] = json.dumps(value)
        elif value is not None:
            updates[key] = str(value)

    redis_conn.hset(f"task:{task_id}", mapping=updates)


async def move_to_dlq(redis_conn: redis.Redis, task_id: str, reason: str) -> None:
    """Move task to dead letter queue."""
    # Update task state
    await update_task_state(
        redis_conn,
        task_id,
        "DLQ",
        last_error=reason,
        completed_at=datetime.utcnow().isoformat(),
    )

    # Add to DLQ
    redis_conn.lpush("dlq:tasks", task_id)

    # Copy task data to DLQ storage
    task_data = redis_conn.hgetall(f"task:{task_id}")
    if task_data:
        redis_conn.hset(f"dlq:task:{task_id}", mapping=task_data)


async def summarize_text(content: str) -> str:
    """
    Summarize text using OpenRouter API.

    Args:
        content: Text content to summarize

    Returns:
        Summarized text

    Raises:
        TransientError: For retryable errors
        PermanentError: For non-retryable errors
    """
    if not settings.openrouter_api_key:
        raise PermanentError("OpenRouter API key not configured")

    # Check circuit breaker
    if not circuit_breaker.can_execute("openrouter"):
        raise TransientError("Circuit breaker is open for OpenRouter")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes text concisely while preserving key information.",
            },
            {
                "role": "user",
                "content": f"Please summarize the following text:\n\n{content}",
            },
        ],
        "max_tokens": 500,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.openrouter_timeout) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code == 200:
                circuit_breaker.record_success("openrouter")
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                circuit_breaker.record_failure("openrouter")
                error_class = ERROR_CLASSIFICATIONS.get(
                    response.status_code, TransientError
                )
                raise error_class(
                    f"OpenRouter API error: {response.status_code} - {response.text}"
                )

    except httpx.TimeoutException:
        circuit_breaker.record_failure("openrouter")
        raise TransientError("Request timeout")
    except httpx.RequestError as e:
        circuit_breaker.record_failure("openrouter")
        raise TransientError(f"Network error: {str(e)}")


class SummarizeTask(Task):
    """Custom Celery task class for summarization with retry logic."""

    def retry_with_backoff(self, exc, task_id: str, retry_count: int):
        """Retry task with exponential backoff."""
        error_type = classify_error(getattr(exc, "status_code", 0), str(exc))

        if error_type == "PermanentError":
            # Don't retry permanent errors
            raise exc

        if retry_count >= settings.max_retries:
            # Exceeded max retries
            raise exc

        delay = calculate_retry_delay(retry_count, error_type)

        # Schedule retry
        redis_conn = get_redis_connection()
        retry_time = time.time() + delay
        redis_conn.zadd("tasks:scheduled", {task_id: retry_time})

        # Update task state
        redis_conn.hset(
            f"task:{task_id}",
            mapping={
                "state": "FAILED",
                "retry_count": retry_count + 1,
                "last_error": str(exc),
                "error_type": error_type,
                "retry_after": datetime.fromtimestamp(retry_time).isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        raise Retry(countdown=delay)


def summarize_task(task_id: str) -> str:
    """
    Main summarization task.

    Args:
        task_id: Unique task identifier

    Returns:
        Task result summary
    """
    redis_conn = get_redis_connection()

    try:
        # Get task data
        task_data = redis_conn.hgetall(f"task:{task_id}")
        if not task_data:
            raise PermanentError(f"Task {task_id} not found")

        content = task_data.get("content")
        if not content:
            raise PermanentError("No content to summarize")

        retry_count = int(task_data.get("retry_count", 0))

        # Check task age
        created_at = datetime.fromisoformat(task_data["created_at"])
        age_seconds = (datetime.utcnow() - created_at).total_seconds()

        if age_seconds > settings.max_task_age:
            redis_conn.hset(
                f"task:{task_id}",
                mapping={
                    "state": "DLQ",
                    "last_error": "Task exceeded maximum age",
                    "completed_at": datetime.utcnow().isoformat(),
                },
            )
            redis_conn.lpush("dlq:tasks", task_id)
            return f"Task {task_id} moved to DLQ (exceeded max age)"

        # Update to ACTIVE state
        redis_conn.hset(
            f"task:{task_id}",
            mapping={
                "state": "ACTIVE",
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        # Perform summarization
        import asyncio

        result = asyncio.run(summarize_text(content))

        # Update to COMPLETED state
        redis_conn.hset(
            f"task:{task_id}",
            mapping={
                "state": "COMPLETED",
                "result": result,
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return f"Task {task_id} completed successfully"

    except PermanentError as e:
        # Move to DLQ immediately
        redis_conn.hset(
            f"task:{task_id}",
            mapping={
                "state": "DLQ",
                "last_error": str(e),
                "error_type": "PermanentError",
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        redis_conn.lpush("dlq:tasks", task_id)
        return f"Task {task_id} moved to DLQ: {str(e)}"

    except TransientError as e:
        # Handle retry logic
        task = SummarizeTask()
        task.retry_with_backoff(e, task_id, retry_count)

    except Exception as e:
        # Unexpected error - treat as transient
        task = SummarizeTask()
        task.retry_with_backoff(TransientError(str(e)), task_id, retry_count)


def process_scheduled_tasks() -> str:
    """
    Process scheduled tasks (retry queue management).

    This is run as a periodic Celery beat task.
    """
    redis_conn = get_redis_connection()
    now = time.time()

    # Get due tasks (up to 100 at a time)
    due_tasks = redis_conn.zrangebyscore("tasks:scheduled", 0, now, start=0, num=100)

    moved_count = 0
    for task_id in due_tasks:
        # Move to retry queue
        redis_conn.lpush("tasks:pending:retry", task_id)
        redis_conn.zrem("tasks:scheduled", task_id)

        # Update state
        redis_conn.hset(
            f"task:{task_id}",
            mapping={
                "state": "PENDING",
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        moved_count += 1

    return f"Moved {moved_count} tasks from scheduled to retry queue"
