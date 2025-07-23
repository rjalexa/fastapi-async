# src/api/routers/queues.py
"""Queue monitoring API endpoints."""

import asyncio
import json
from typing import List

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from schemas import QueueStatus, TaskDetail, QueueName
from services import queue_service
from config import settings
from fastapi import Request

router = APIRouter(prefix="/api/v1/queues", tags=["queues"])


@router.get("/status", response_model=QueueStatus)
async def get_queue_status(request: Request) -> QueueStatus:
    """
    Get comprehensive queue status and statistics.

    Returns:
    - Queue depths for all queues (primary, retry, scheduled, DLQ)
    - Task counts by state
    - Current adaptive retry ratio
    """
    # Try to get the queue service from app state first
    current_queue_service = getattr(request.app.state, "queue_service", None)

    # Fallback to global variable
    if not current_queue_service:
        current_queue_service = queue_service

    if not current_queue_service:
        # Try to get from app state as fallback
        from services import QueueService, RedisService
        from config import settings

        try:
            # Create a temporary service for this request
            temp_redis = RedisService(settings.redis_url)
            await temp_redis.initialize()
            temp_queue_service = QueueService(temp_redis)
            result = await temp_queue_service.get_queue_status()
            await temp_redis.close()
            return result
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Queue service not available: {str(e)}",
            )

    try:
        return await current_queue_service.get_queue_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}",
        )


@router.get("/{queue_name}/tasks", response_model=List[str])
async def get_tasks_in_queue(
    request: Request,
    queue_name: QueueName,
    limit: int = Query(
        default=10, ge=1, le=1000, description="Maximum number of task IDs to return"
    ),
) -> List[str]:
    """
    List task IDs from a specific queue.

    - **queue_name**: The name of the queue to inspect (primary, retry, scheduled, dlq)
    - **limit**: Maximum number of task IDs to return (1-1000, default: 10)

    Returns a list of task IDs currently in the specified queue.
    For the scheduled queue, tasks are ordered by their scheduled execution time.
    For other queues, tasks are in FIFO order.
    """
    # Try to get the queue service from app state first
    current_queue_service = getattr(request.app.state, "queue_service", None)

    # Fallback to global variable
    if not current_queue_service:
        current_queue_service = queue_service

    if not current_queue_service:
        # Try to get from app state as fallback
        from services import QueueService, RedisService
        from config import settings

        try:
            # Create a temporary service for this request
            temp_redis = RedisService(settings.redis_url)
            await temp_redis.initialize()
            temp_queue_service = QueueService(temp_redis)
            result = await temp_queue_service.list_tasks_in_queue(
                queue_name.value, limit
            )
            await temp_redis.close()
            return result
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Queue service not available: {str(e)}",
            )

    try:
        return await current_queue_service.list_tasks_in_queue(queue_name.value, limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tasks from queue '{queue_name.value}': {str(e)}",
        )


@router.get("/dlq", response_model=List[TaskDetail])
async def get_dlq_tasks(
    request: Request,
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum number of tasks to return"
    ),
) -> List[TaskDetail]:
    """
    Get tasks from the dead letter queue.

    - **limit**: Maximum number of tasks to return (1-1000, default: 100)

    Returns a list of tasks that have been moved to the DLQ due to:
    - Exceeding maximum retry attempts
    - Permanent errors
    - Task age exceeding limits
    """
    # Try to get the queue service from app state first
    current_queue_service = getattr(request.app.state, "queue_service", None)

    # Fallback to global variable
    if not current_queue_service:
        current_queue_service = queue_service

    if not current_queue_service:
        # Try to get from app state as fallback
        from services import QueueService, RedisService
        from config import settings

        try:
            # Create a temporary service for this request
            temp_redis = RedisService(settings.redis_url)
            await temp_redis.initialize()
            temp_queue_service = QueueService(temp_redis)
            result = await temp_queue_service.get_dlq_tasks(limit)
            await temp_redis.close()
            return result
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Queue service not available: {str(e)}",
            )

    try:
        return await current_queue_service.get_dlq_tasks(limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DLQ tasks: {str(e)}",
        )


@router.get("/status/stream")
async def stream_queue_status():
    """
    Server-Sent Events endpoint for real-time queue status updates.

    This endpoint maintains an open connection and streams queue status changes
    in real-time using Redis pub/sub. The frontend can connect to this endpoint
    to receive live updates when tasks are created, completed, or change state.

    Returns:
    - Server-Sent Events stream with queue status updates
    """

    async def event_generator():
        # Create a dedicated Redis connection for pub/sub
        pubsub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = pubsub_redis.pubsub()

        try:
            # Subscribe to queue updates channel
            await pubsub.subscribe("queue-updates")

            # Send initial queue status
            # Import services module to get the current queue service
            import src.api.services as services

            current_queue_service = services.queue_service

            if not current_queue_service:
                # Try to get from app state as fallback
                try:
                    from services import QueueService, RedisService
                    from config import settings as config_settings

                    # Create a temporary service for this request
                    temp_redis = RedisService(config_settings.redis_url)
                    await temp_redis.initialize()
                    current_queue_service = QueueService(temp_redis)
                except Exception as e:
                    error_data = {
                        "type": "error",
                        "message": f"Queue service not available: {str(e)}",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

            if current_queue_service:
                try:
                    initial_status = await current_queue_service.get_queue_status()
                    initial_data = {
                        "type": "initial_status",
                        "queue_depths": initial_status.queues,
                        "state_counts": initial_status.states,
                        "retry_ratio": initial_status.retry_ratio,
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    yield f"data: {json.dumps(initial_data)}\n\n"
                except Exception as e:
                    error_data = {
                        "type": "error",
                        "message": f"Failed to get initial status: {str(e)}",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

            # Listen for updates
            while True:
                try:
                    # Wait for message with timeout to allow periodic heartbeat
                    message = await asyncio.wait_for(pubsub.get_message(), timeout=30.0)

                    if message and message["type"] == "message":
                        # Forward the update to the client
                        update_data = json.loads(message["data"])
                        yield f"data: {json.dumps(update_data)}\n\n"
                    elif message is None:
                        # No message received, just continue without sending heartbeat
                        # Heartbeats will be sent only on timeout
                        continue

                except asyncio.TimeoutError:
                    # Send heartbeat on timeout (every 30 seconds)
                    heartbeat_data = {
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    yield f"data: {json.dumps(heartbeat_data)}\n\n"

                except Exception as e:
                    # Send error and continue
                    error_data = {
                        "type": "error",
                        "message": str(e),
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

        except Exception as e:
            # Final error before closing
            error_data = {
                "type": "fatal_error",
                "message": str(e),
                "timestamp": asyncio.get_event_loop().time(),
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        finally:
            # Clean up
            try:
                await pubsub.unsubscribe("queue-updates")
                await pubsub.close()
                await pubsub_redis.close()
            except Exception:
                pass  # Ignore cleanup errors

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )
