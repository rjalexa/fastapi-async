# src/api/routers/tasks.py
"""Task management API endpoints."""

from fastapi import APIRouter, HTTPException, status
from celery import Celery

from schemas import TaskCreate, TaskDetail, TaskResponse, TaskRetryRequest
from services import task_service

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# Celery app instance (will be initialized in main.py)
celery_app: Celery = None


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate) -> TaskResponse:
    """
    Create a new summarization task.

    - **content**: Text content to summarize (required)

    Returns the task ID and initial state.
    """
    if not task_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task service not available",
        )

    try:
        task_id = await task_service.create_task(task_data.content)

        # Trigger Celery task
        if celery_app:
            celery_app.send_task("summarize_task", args=[task_id])

        return TaskResponse(task_id=task_id, state="PENDING")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}",
        )


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str) -> TaskDetail:
    """
    Get task status and details by ID.

    - **task_id**: Unique task identifier

    Returns complete task information including state, result, and error history.
    """
    if not task_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task service not available",
        )

    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: str, retry_request: TaskRetryRequest = None
) -> TaskResponse:
    """
    Manually retry a failed task.

    - **task_id**: Unique task identifier
    - **reset_retry_count**: Whether to reset the retry count (optional)

    Only failed or DLQ tasks can be retried.
    """
    if not task_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task service not available",
        )

    # Get current task to check state
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.state not in ["FAILED", "DLQ"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task in state '{task.state}' cannot be retried",
        )

    reset_retry_count = retry_request.reset_retry_count if retry_request else False
    success = await task_service.retry_task(task_id, reset_retry_count)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retry task"
        )

    # Trigger Celery task
    if celery_app:
        celery_app.send_task("summarize_task", args=[task_id])

    return TaskResponse(task_id=task_id, state="PENDING")
