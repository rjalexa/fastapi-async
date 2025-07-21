# src/api/routers/pdfxtract.py
"""Router for PDF extraction endpoints."""

import base64
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from schemas import ErrorResponse, PdfTaskCreate, TaskResponse, TaskState, TaskType
from services import TaskService, task_service

router = APIRouter(prefix="/api/v1/tasks", tags=["PDF Extraction"])


@router.post(
    "/pdfxtract",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or parameters"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_pdf_extraction_task(
    file: UploadFile = File(..., description="PDF file to extract articles from"),
    issue_date: Optional[str] = Form(None, description="Issue date in ISO 8601 format (optional)"),
    task_service: TaskService = Depends(lambda: task_service),
) -> TaskResponse:
    """
    Create a new PDF extraction task.
    
    Accepts a PDF file upload and creates a task to extract newspaper articles
    from each page using LLM vision capabilities.
    
    Args:
        file: PDF file to process
        issue_date: Optional issue date in ISO 8601 format
        task_service: Injected task service
        
    Returns:
        TaskResponse with task_id and initial state
        
    Raises:
        HTTPException: If file validation fails or task creation fails
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("application/pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF document"
        )
    
    # Check file size (limit to 50MB)
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size must be less than 50MB"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Encode file content as base64 for storage
        file_content_b64 = base64.b64encode(file_content).decode('utf-8')
        
        # Create task metadata
        task_metadata = {
            "filename": file.filename or "unknown.pdf",
            "issue_date": issue_date,
            "file_size": len(file_content),
            "content_type": file.content_type,
        }
        
        # Create the task
        task_id = await task_service.create_task(
            content=file_content_b64,
            task_type=TaskType.PDFXTRACT,
            metadata=task_metadata
        )
        
        return TaskResponse(
            task_id=task_id,
            state=TaskState.PENDING
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create PDF extraction task: {str(e)}"
        )
    finally:
        # Ensure file is closed
        await file.close()
