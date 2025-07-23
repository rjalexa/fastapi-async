# src/worker/tasks_fixed.py
"""
Celery tasks for text summarization and task processing.

Refactored for consistent async data access and idiomatic Celery patterns,
suitable for a FastAPI-based monitoring frontend.
"""

import asyncio
import base64
import io
import json
import os
import random
import time
from datetime import datetime

import redis.asyncio as aioredis
from celery import Task
from celery.worker.control import Panel
from pdf2image import convert_from_bytes

from circuit_breaker import (
    call_openrouter_api,
    get_circuit_breaker_status,
    reset_circuit_breaker,
    open_circuit_breaker,
)
from config import settings
from prompts import load_prompt
from redis_config import get_worker_standard_redis

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
    "RateLimitError": [
        120,
        300,
        600,
        1200,
    ],  # 2min, 5min, 10min, 20min - longer delays for rate limits
    "ServiceUnavailable": [5, 10, 30, 60, 120],
    "NetworkTimeout": [2, 5, 10, 30, 60],
    "Default": [5, 15, 60, 300],
}

# --- Import Unified Celery App --------------------------------------------

# Import the unified Celery app from main.py
from main import app

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


@Panel.register
def open_worker_circuit_breaker(panel, **kwargs):
    """Open the circuit breaker on this worker (invoked via broadcast)."""
    try:
        open_circuit_breaker()
        return {
            "status": "success",
            "message": "Circuit breaker opened.",
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


async def get_async_redis_connection() -> aioredis.Redis:
    """Get an optimized async Redis connection."""
    try:
        return await get_worker_standard_redis()
    except RuntimeError:
        # Fallback to direct connection if worker Redis not initialized
        return aioredis.from_url(settings.redis_url, decode_responses=True)


def classify_error(status_code: int, error_message: str) -> str:
    """Classify error as transient or permanent."""
    # First check for dependency/environment errors that should go directly to DLQ
    dependency_error_patterns = [
        "poppler installed and in path",
        "command not found",
        "no such file or directory",
        "permission denied",
        "module not found",
        "import error",
        "library not found",
        "missing dependency",
        "environment variable not set",
        "configuration error",
        "invalid configuration",
        "database connection failed",
        "redis connection failed",
    ]

    error_lower = error_message.lower()
    for pattern in dependency_error_patterns:
        if pattern in error_lower:
            return "DependencyError"

    # Check for other permanent errors based on content
    permanent_error_patterns = [
        "invalid api key",
        "authentication failed",
        "unauthorized",
        "forbidden",
        "not found",
        "bad request",
        "invalid request",
        "malformed",
        "syntax error",
        "parse error",
        "invalid json",
        "invalid format",
        "unsupported format",
        "file too large",
        "quota exceeded",
        "limit exceeded",
    ]

    for pattern in permanent_error_patterns:
        if pattern in error_lower:
            return "PermanentError"

    # Check HTTP status codes
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

    # Fallback to default retry behavior for unknown errors
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
    current_time = datetime.utcnow().isoformat()
    fields = {"state": state, "updated_at": current_time}
    fields.update(kwargs)

    # Get current state for counter updates
    current_task_data = await redis_conn.hgetall(f"task:{task_id}")
    old_state = current_task_data.get("state") if current_task_data else None

    # Add state-specific timestamps
    if state == "ACTIVE":
        fields["started_at"] = current_time
    elif state == "COMPLETED":
        fields["completed_at"] = current_time
    elif state == "FAILED":
        fields["failed_at"] = current_time
    elif state == "DLQ":
        fields["dlq_at"] = current_time
    elif state == "SCHEDULED":
        fields["scheduled_at"] = current_time


async def move_to_dlq(
    redis_conn: aioredis.Redis, task_id: str, error_message: str, reason: str
) -> None:
    """Move a task to the Dead Letter Queue (DLQ)."""
    await update_task_state(
        redis_conn,
        task_id,
        "DLQ",
        error=error_message,
        dlq_reason=reason,
        dlq_at=datetime.utcnow().isoformat(),
    )


async def schedule_task_for_retry(
    redis_conn: aioredis.Redis, task_id: str, retry_count: int, exc: Exception
) -> None:
    """Schedule a task for a future retry."""
    error_type = classify_error(getattr(exc, "status_code", 0), str(exc))
    delay = calculate_retry_delay(retry_count, error_type)
    retry_at = time.time() + delay

    await update_task_state(
        redis_conn,
        task_id,
        "SCHEDULED",
        error=str(exc),
        retry_count=retry_count + 1,
        retry_at=datetime.fromtimestamp(retry_at).isoformat(),
    )
    await redis_conn.zadd("tasks:scheduled", {task_id: retry_at})


# --- Core Task Logic (with Circuit Breaker) -------------------------------


async def summarize_text_with_pybreaker(text: str) -> str:
    """Summarize text using the OpenRouter API, wrapped in a circuit breaker."""
    try:
        prompt = load_prompt("summarize.txt")
        messages = [{"role": "user", "content": prompt.format(text_to_summarize=text)}]
        return await call_openrouter_api(messages)
    except FileNotFoundError as e:
        # Prompt loading errors are permanent
        raise PermanentError(f"Summarization error: {str(e)}")
    except Exception as e:
        msg = str(e)
        if "circuit breaker" in msg.lower() or "service unavailable" in msg.lower():
            raise TransientError(f"OpenRouter service protection: {msg}")

        # Simple status code parsing
        code = 0
        if "status_code=" in msg:
            try:
                code_str = msg.split("status_code=")[1].split(" ")[0].strip()
                code = int(code_str)
            except (IndexError, ValueError):
                pass

        if classify_error(code, msg) == "PermanentError":
            raise PermanentError(f"Summarization API error: {msg}")
        else:
            exc = TransientError(f"Summarization API error: {msg}")
            exc.status_code = code
            raise exc


async def extract_pdf_with_pybreaker(
    pdf_content_b64: str, filename: str, issue_date: str
) -> str:
    """Extract text from a PDF using OpenRouter, wrapped in a circuit breaker."""
    try:
        # Decode the base64 content
        pdf_bytes = base64.b64decode(pdf_content_b64)

        # Convert PDF to images
        images = convert_from_bytes(pdf_bytes, dpi=200)

        # Load the extraction prompt
        prompt = load_prompt("pdfxtract.txt")

        all_pages_data = []

        for page_num, img in enumerate(images, 1):
            try:
                # Convert image to base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                # Prepare messages for the API call
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                },
                            },
                        ],
                    },
                ]

                # Call the OpenRouter API for this page (includes rate limiting and reporting)
                page_result = await call_openrouter_api(messages)

                # Parse the JSON response
                try:
                    # Clean the response by removing markdown code blocks if present
                    cleaned_result = page_result.strip()
                    if cleaned_result.startswith("```json"):
                        # Remove opening ```json
                        cleaned_result = cleaned_result[7:]
                    if cleaned_result.startswith("```"):
                        # Remove opening ``` (in case it's just ```)
                        cleaned_result = cleaned_result[3:]
                    if cleaned_result.endswith("```"):
                        # Remove closing ```
                        cleaned_result = cleaned_result[:-3]

                    # Strip any remaining whitespace
                    cleaned_result = cleaned_result.strip()

                    page_data = json.loads(cleaned_result)
                    # Extract the pages array from the response
                    if "pages" in page_data and len(page_data["pages"]) > 0:
                        all_pages_data.extend(page_data["pages"])
                    else:
                        # If no pages array, create a skipped page entry
                        all_pages_data.append(
                            {
                                "page_number": page_num,
                                "status": "skipped",
                                "reason": "No valid page data returned from LLM",
                                "articles": [],
                            }
                        )
                except json.JSONDecodeError as e:
                    # If JSON parsing fails, create a skipped page entry
                    all_pages_data.append(
                        {
                            "page_number": page_num,
                            "status": "skipped",
                            "reason": f"JSON parsing failed: {str(e)}",
                            "articles": [],
                        }
                    )

            except Exception as e:
                # If page processing fails, create a skipped page entry
                all_pages_data.append(
                    {
                        "page_number": page_num,
                        "status": "skipped",
                        "reason": f"Page processing failed: {str(e)}",
                        "articles": [],
                    }
                )

        # Create the final document structure
        final_result = {
            "filename": filename,
            "issue_date": issue_date or "unknown",
            "pages": all_pages_data,
        }

        return json.dumps(final_result, ensure_ascii=False, indent=2)

    except (FileNotFoundError, ValueError) as e:
        # Prompt loading/formatting errors are permanent
        raise PermanentError(f"PDF extraction error: {str(e)}")
    except Exception as e:
        msg = str(e)
        if "circuit breaker" in msg.lower() or "service unavailable" in msg.lower():
            raise TransientError(f"OpenRouter service protection: {msg}")

        # Simple status code parsing
        code = 0
        if "status_code=" in msg:
            try:
                code_str = msg.split("status_code=")[1].split(" ")[0].strip()
                code = int(code_str)
            except (IndexError, ValueError):
                pass

        if classify_error(code, msg) == "PermanentError":
            raise PermanentError(f"PDF extraction API error: {msg}")
        else:
            exc = TransientError(f"PDF extraction API error: {msg}")
            exc.status_code = code
            raise exc


# --- Celery Tasks ---------------------------------------------------------


async def update_worker_heartbeat(redis_conn: aioredis.Redis, worker_id: str) -> None:
    """Update worker heartbeat in Redis."""
    heartbeat_key = f"worker:heartbeat:{worker_id}"
    current_time = time.time()
    await redis_conn.setex(heartbeat_key, 90, current_time)  # Expire after 90 seconds


@app.task(bind=True)
def process_task(self: Task, task_id: str) -> str:
    """
    Main task processor that handles different task types.
    `bind=True` provides access to the task instance via `self`.
    """
    retry_count = self.request.retries  # Use Celery's built-in retry counter
    worker_id = f"celery-{self.request.hostname}-{os.getpid()}"

    async def _run_task():
        # Get optimized Redis connection
        redis_conn = await get_async_redis_connection()

        # Update heartbeat at start of task
        await update_worker_heartbeat(redis_conn, worker_id)

        data = await redis_conn.hgetall(f"task:{task_id}")
        if not data:
            raise PermanentError(f"Task {task_id} not found in Redis.")

        content = data.get("content", "")
        task_type = data.get("task_type", "summarize")

        if not content:
            raise PermanentError("No content to process.")

        # Check for max retries before execution
        if retry_count >= settings.max_retries:
            raise PermanentError(f"Max retries ({settings.max_retries}) exceeded.")

        await update_task_state(redis_conn, task_id, "ACTIVE", worker_id=worker_id)

        # Process based on task type
        if task_type == "pdfxtract":
            # Parse metadata for PDF extraction
            metadata = {}
            if data.get("metadata"):
                try:
                    metadata = json.loads(data["metadata"])
                except json.JSONDecodeError:
                    metadata = {}

            filename = metadata.get("filename", "unknown.pdf")
            issue_date = metadata.get("issue_date")

            result = await extract_pdf_with_pybreaker(content, filename, issue_date)
        else:
            # Default to summarization
            result = await summarize_text_with_pybreaker(content)

        await update_task_state(
            redis_conn,
            task_id,
            "COMPLETED",
            result=result,
            completed_at=datetime.utcnow().isoformat(),
        )

        # Update heartbeat at end of task
        await update_worker_heartbeat(redis_conn, worker_id)

        return f"Task {task_id} ({task_type}) completed successfully."

    async def _handle_error(exc, error_type="TransientError"):
        """Handle task errors with proper Redis connection."""
        redis_conn = await get_async_redis_connection()

        # Classify the error to determine proper handling
        error_classification = classify_error(getattr(exc, "status_code", 0), str(exc))

        if error_type == "PermanentError" or error_classification in [
            "PermanentError",
            "DependencyError",
        ]:
            # Send to DLQ for permanent errors and dependency errors
            dlq_reason = (
                "DependencyError"
                if error_classification == "DependencyError"
                else "PermanentError"
            )
            await move_to_dlq(redis_conn, task_id, str(exc), dlq_reason)
            return f"Task {task_id} moved to DLQ ({dlq_reason}): {exc}"
        else:
            # Schedule for retry for transient errors
            await schedule_task_for_retry(redis_conn, task_id, retry_count, exc)
            return f"Task {task_id} failed, scheduled for retry."

    try:
        return asyncio.run(_run_task())
    except PermanentError as e:
        return asyncio.run(_handle_error(e, "PermanentError"))
    except TransientError as e:
        return asyncio.run(_handle_error(e, "TransientError"))
    except Exception as e:
        # Catch any other unexpected errors and treat them as transient
        exc = TransientError(f"An unexpected error occurred: {str(e)}")
        return asyncio.run(_handle_error(exc, "TransientError"))


# Keep the old summarize_task for backward compatibility
@app.task(bind=True)
def summarize_task(self: Task, task_id: str) -> str:
    """
    Legacy summarization task - redirects to process_task.
    `bind=True` provides access to the task instance via `self`.
    """
    return process_task.apply_async(args=[task_id], task_id=self.request.id).get()


@app.task(name='process_scheduled_tasks')
def process_scheduled_tasks() -> str:
    """
    Periodically run by Celery Beat to move scheduled tasks back to the pending queue.
    """

    async def _run_processing():
        # Get optimized Redis connection
        redis_conn = await get_async_redis_connection()

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
