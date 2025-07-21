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
    SCHEDULED = "SCHEDULED"
    DLQ = "DLQ"


class TaskType(str, Enum):
    """Task type enumeration."""

    SUMMARIZE = "summarize"
    PDFXTRACT = "pdfxtract"


class QueueName(str, Enum):
    """Enum for the different task queues."""

    PRIMARY = "primary"
    RETRY = "retry"
    SCHEDULED = "scheduled"
    DLQ = "dlq"


# Centralized mapping from queue names to Redis keys
QUEUE_KEY_MAP = {
    QueueName.PRIMARY: "tasks:pending:primary",
    QueueName.RETRY: "tasks:pending:retry",
    QueueName.SCHEDULED: "tasks:scheduled",
    QueueName.DLQ: "dlq:tasks",
}


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
    task_type: Optional[TaskType] = Field(
        TaskType.SUMMARIZE, description="Type of task"
    )
    error_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of errors"
    )
    state_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of state transitions"
    )


class TaskSummary(BaseModel):
    """Schema for task summary information (without content field)."""

    task_id: str = Field(..., description="Unique task identifier")
    state: TaskState = Field(..., description="Current task state")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum allowed retries")
    last_error: Optional[str] = Field(None, description="Last error message")
    error_type: Optional[str] = Field(None, description="Type of last error")
    retry_after: Optional[datetime] = Field(None, description="Next retry time")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    task_type: Optional[TaskType] = Field(
        TaskType.SUMMARIZE, description="Type of task"
    )
    content_length: Optional[int] = Field(
        None, description="Length of content in characters"
    )
    has_result: bool = Field(False, description="Whether task has a result")
    error_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of errors"
    )
    state_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of state transitions"
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


class TaskDeleteResponse(BaseModel):
    """Schema for task deletion response."""

    task_id: str = Field(..., description="Deleted task identifier")
    message: str = Field(..., description="Deletion confirmation message")


class TaskListResponse(BaseModel):
    """Schema for task list response."""

    tasks: List[TaskDetail] = Field(
        ..., description="List of tasks matching the criteria"
    )
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    status: Optional[TaskState] = Field(None, description="Filter status used")


class TaskSummaryListResponse(BaseModel):
    """Schema for task list response with summary information only."""

    tasks: List[TaskSummary] = Field(
        ..., description="List of task summaries matching the criteria"
    )
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    status: Optional[TaskState] = Field(None, description="Filter status used")


# PDF Extraction Schemas


class Article(BaseModel):
    """Schema for a newspaper article."""

    title: str = Field("", description="Article title")
    subtitle: str = Field("", description="Article subtitle")
    author: str = Field("", description="Article author")
    body: str = Field(..., description="Article body text")
    topics: List[str] = Field(default_factory=list, description="Article topics/tags")
    summary: str = Field("", description="Article summary")


class Page(BaseModel):
    """Schema for a newspaper page."""

    page_number: int = Field(..., description="Page number")
    status: str = Field(
        "processed", description="Processing status: 'processed' or 'skipped'"
    )
    reason: str = Field("", description="Reason for skipping if status is 'skipped'")
    articles: List[Article] = Field(
        default_factory=list, description="Articles on this page"
    )


class NewspaperEdition(BaseModel):
    """Schema for a complete newspaper edition."""

    filename: str = Field(..., description="Original PDF filename")
    issue_date: str = Field(..., description="Issue date in ISO 8601 format")
    pages: List[Page] = Field(default_factory=list, description="Pages in the edition")


class PdfTaskCreate(BaseModel):
    """Schema for creating a PDF extraction task."""

    filename: str = Field(..., description="PDF filename")
    issue_date: Optional[str] = Field(
        None, description="Issue date in ISO 8601 format (optional)"
    )
