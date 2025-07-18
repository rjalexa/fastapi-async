# src/api/routers/tasks.py
"""Task management API endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from celery import Celery

from schemas import TaskCreate, TaskDetail, TaskResponse, TaskRetryRequest, TaskDeleteResponse, TaskListResponse, TaskState
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

        # Note: No need to trigger Celery task anymore
        # Workers consume directly from Redis queues

        return TaskResponse(task_id=task_id, state=TaskState.PENDING)
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

    if task.state not in [TaskState.FAILED, TaskState.DLQ]:
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

    # Note: No need to trigger Celery task anymore
    # Workers consume directly from Redis queues

    return TaskResponse(task_id=task_id, state=TaskState.PENDING)


@router.post("/requeue-orphaned", response_model=dict)
async def requeue_orphaned_tasks(
    task_svc: TaskService = Depends(get_task_service)
) -> dict:
    """
    Find and re-queue orphaned tasks.
    
    Orphaned tasks are tasks that have PENDING state in Redis but are not
    present in any work queue. This can happen if there's a failure between
    storing task metadata and adding the task to a queue.
    
    Returns:
    - **found**: Number of orphaned tasks found
    - **requeued**: Number of tasks successfully re-queued
    - **errors**: List of any errors encountered
    """
    try:
        result = await task_svc.requeue_orphaned_tasks()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to requeue orphaned tasks: {str(e)}",
        )


@router.get("/", response_model=TaskListResponse)
async def list_tasks_by_status(
    task_status: Optional[TaskState] = Query(None, alias="status", description="Filter tasks by status"),
    limit: Optional[int] = Query(100, description="Maximum number of task IDs to return", ge=1, le=1000),
    task_svc: TaskService = Depends(get_task_service)
) -> TaskListResponse:
    """
    List task IDs filtered by status.

    - **status**: Task status to filter by (optional, shows dropdown in Swagger UI)
    - **limit**: Maximum number of task IDs to return (default: 100, max: 1000)

    Returns a list of task IDs matching the specified criteria.
    """
    try:
        if task_status is None:
            # If no status specified, we could return all tasks, but that might be too many
            # For now, let's require a status filter
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status parameter is required. Please specify a task status to filter by.",
            )
        
        task_ids = await task_svc.get_task_ids_by_status(task_status, limit)
        
        return TaskListResponse(
            task_ids=task_ids,
            count=len(task_ids),
            status=task_status
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}",
        )


@router.delete("/{task_id}", response_model=TaskDeleteResponse)
async def delete_task(
    task_id: str,
    task_svc: TaskService = Depends(get_task_service)
) -> TaskDeleteResponse:
    """
    Delete a task and all its associated data.

    - **task_id**: Unique task identifier

    This will permanently remove the task from all queues and delete all associated data.
    This action cannot be undone.
    """
    try:
        # Check if task exists first
        task = await task_svc.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Task not found"
            )
        
        # Delete the task
        success = await task_svc.delete_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete task"
            )
        
        return TaskDeleteResponse(
            task_id=task_id,
            message=f"Task {task_id} and all associated data have been permanently deleted"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}",
        )
