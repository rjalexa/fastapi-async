# src/api/routers/summarize.py
"""Summarization task creation endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends
from celery import Celery

from src.api.schemas import TaskCreate, TaskResponse, TaskState
from src.api.services import TaskService

router = APIRouter(prefix="/api/v1/tasks/summarize", tags=["application"])

# Celery app instance (will be initialized in main.py)
celery_app: Celery = None


def get_task_service() -> TaskService:
    """Dependency to get task service from app state."""
    from src.api.services import task_service

    # Try to get from global first
    if task_service is not None:
        return task_service

    # If global is None, raise service unavailable
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Task service not available",
    )


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_summarization_task(
    task_data: TaskCreate, task_svc: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """
    Create a new text summarization task.

    - **content**: Text content to summarize (required)

    Returns the task ID and initial state. The task will be processed asynchronously
    by the worker system and can be monitored using the generic task endpoints.
    """
    try:
        task_id = await task_svc.create_task(task_data.content)

        # Note: No need to trigger Celery task anymore
        # Workers consume directly from Redis queues

        return TaskResponse(task_id=task_id, state=TaskState.PENDING)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create summarization task: {str(e)}",
        )
