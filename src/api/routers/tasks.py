# src/api/routers/tasks.py
"""Task management API endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends
from celery import Celery

from schemas import TaskCreate, TaskDetail, TaskResponse, TaskRetryRequest
from services import TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# Celery app instance (will be initialized in main.py)
celery_app: Celery = None


def get_task_service() -> TaskService:
    """Dependency to get task service from app state."""
    from fastapi import Request
    from services import task_service
    
    # Try to get from global first
    if task_service is not None:
        return task_service
    
    # If global is None, raise service unavailable
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Task service not available",
    )


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate, 
    task_svc: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """
    Create a new summarization task.

    - **content**: Text content to summarize (required)

    Returns the task ID and initial state.
    """
    try:
        task_id = await task_svc.create_task(task_data.content)

        # Trigger Celery task
        if celery_app:
            celery_app.send_task("summarize_text", args=[task_id])

        return TaskResponse(task_id=task_id, state="PENDING")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}",
        )


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str, 
    task_svc: TaskService = Depends(get_task_service)
) -> TaskDetail:
    """
    Get task status and details by ID.

    - **task_id**: Unique task identifier

    Returns complete task information including state, result, and error history.
    """
    task = await task_svc.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: str, 
    retry_request: TaskRetryRequest = None,
    task_svc: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """
    Manually retry a failed task.

    - **task_id**: Unique task identifier
    - **reset_retry_count**: Whether to reset the retry count (optional)

    Only failed or DLQ tasks can be retried.
    """
    # Get current task to check state
    task = await task_svc.get_task(task_id)
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
    success = await task_svc.retry_task(task_id, reset_retry_count)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retry task"
        )

    # Trigger Celery task
    if celery_app:
        celery_app.send_task("summarize_text", args=[task_id])

    return TaskResponse(task_id=task_id, state="PENDING")
