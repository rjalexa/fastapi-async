"""Queue monitoring API endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, Query, status

from schemas import QueueStatus, TaskDetail
from services import queue_service

router = APIRouter(prefix="/api/v1/queues", tags=["queues"])


@router.get("/status", response_model=QueueStatus)
async def get_queue_status() -> QueueStatus:
    """
    Get comprehensive queue status and statistics.

    Returns:
    - Queue depths for all queues (primary, retry, scheduled, DLQ)
    - Task counts by state
    - Current adaptive retry ratio
    """
    if not queue_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue service not available",
        )

    try:
        return await queue_service.get_queue_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}",
        )


@router.get("/dlq", response_model=List[TaskDetail])
async def get_dlq_tasks(
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
    if not queue_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue service not available",
        )

    try:
        return await queue_service.get_dlq_tasks(limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DLQ tasks: {str(e)}",
        )
