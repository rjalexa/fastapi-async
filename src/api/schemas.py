# src/api/schemas.py
"""Pydantic schemas for API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Task state enumeration."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DLQ = "DLQ"


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    content: str = Field(..., description="Text content to summarize", min_length=1)


class TaskResponse(BaseModel):
    """Schema for task creation response."""

    task_id: str = Field(..., description="Unique task identifier")
    state: TaskState = Field(..., description="Current task state")


class TaskDetail(BaseModel):
    """Schema for detailed task information."""

    task_id: str = Field(..., description="Unique task identifier")
    state: TaskState = Field(..., description="Current task state")
    content: str = Field(..., description="Original text content")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum allowed retries")
    last_error: Optional[str] = Field(None, description="Last error message")
    error_type: Optional[str] = Field(None, description="Type of last error")
    retry_after: Optional[datetime] = Field(None, description="Next retry time")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    result: Optional[str] = Field(None, description="Summarization result")
    error_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of errors"
    )


class QueueStatus(BaseModel):
    """Schema for queue status information."""

    queues: Dict[str, int] = Field(..., description="Queue depths by name")
    states: Dict[str, int] = Field(..., description="Task counts by state")
    retry_ratio: float = Field(..., description="Current retry consumption ratio")


class HealthStatus(BaseModel):
    """Schema for health check response."""

    status: str = Field(..., description="Overall health status")
    components: Dict[str, Any] = Field(..., description="Component health status")
    note: Optional[str] = Field(None, description="Additional health information")
    timestamp: datetime = Field(..., description="Health check timestamp")


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskRetryRequest(BaseModel):
    """Schema for manual task retry request."""

    reset_retry_count: bool = Field(
        default=False, description="Whether to reset the retry count"
    )
