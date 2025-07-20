# src/api/routers/tasks.py
"""Generic task management API endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from celery import Celery

from schemas import TaskDetail, TaskResponse, TaskRetryRequest, TaskDeleteResponse, TaskListResponse, TaskState, QueueName
from datetime import datetime
from services import TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["task-management"])

# Celery app instance (will be initialized in main.py)
celery_app: Celery = None


def get_task_service() -> TaskService:
    """Dependency to get task service from app state."""
    from services import task_service
    
    # Try to get from global first
    if task_service is not None:
        return task_service
    
    # If global is None, raise service unavailable
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Task service not available",
    )


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    task_status: Optional[TaskState] = Query(None, description="Filter tasks by status"),
    queue: Optional[QueueName] = Query(None, description="Filter tasks by queue"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    sort_by: Optional[str] = Query("created_at", description="Field to sort by"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    task_id: Optional[str] = Query(None, description="Search by task ID"),
    task_svc: TaskService = Depends(get_task_service)
) -> TaskListResponse:
    """
    List and filter tasks with pagination, sorting, and advanced filtering.
    """
    try:
        result = await task_svc.list_tasks(
            status=task_status,
            queue=queue,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
            task_id=task_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}",
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
    Works for tasks of any type (summarization, entity detection, etc.).
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
    Works for tasks of any type (summarization, entity detection, etc.).
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
    
    Works for tasks of any type (summarization, entity detection, etc.).
    
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
    Works for tasks of any type (summarization, entity detection, etc.).
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
