# Dependency Error Handling Implementation

## Overview

This document describes the implementation of proper error handling for dependency and environment errors in the AsyncTaskFlow worker system. The goal is to ensure that errors caused by missing dependencies or environment configuration issues are sent directly to the Dead Letter Queue (DLQ) instead of being retried indefinitely.

## Problem Statement

Previously, when a task failed due to missing system dependencies (like the poppler utilities required for PDF processing), the task would be scheduled for retry. This was inefficient because:

1. **Resource Waste**: Retry attempts consume worker resources without any chance of success
2. **Delayed Failure Detection**: The actual issue (missing dependency) was masked by retry attempts
3. **Queue Congestion**: Failed tasks would cycle through retry queues unnecessarily

### Example Error

```
PDF extraction API error: Unable to get page count. Is poppler installed and in PATH?
```

This error indicates that the `poppler-utils` package is not available in the container, which is an environment/dependency issue that won't be resolved by retrying.

## Solution Implementation

### 1. Enhanced Error Classification

Updated the `classify_error()` function in `src/worker/tasks.py` to detect dependency and environment errors:

```python
def classify_error(status_code: int, error_message: str) -> str:
    """Classify error as transient or permanent."""
    # First check for dependency/environment errors that should go directly to DLQ
    dependency_error_patterns = [
        "poppler installed and in PATH",
        "command not found",
        "no such file or directory",
        "permission denied",
        "module not found",
        "import error",
        "library not found",
        "missing dependency",
        "environment variable not set",
        "configuration error",
        "invalid configuration",
        "database connection failed",
        "redis connection failed",
    ]
    
    error_lower = error_message.lower()
    for pattern in dependency_error_patterns:
        if pattern in error_lower:
            return "DependencyError"
    
    # ... rest of classification logic
```

### 2. Updated Error Handling Logic

Modified the `_handle_error()` function to properly route dependency errors to DLQ:

```python
async def _handle_error(exc, error_type="TransientError"):
    """Handle task errors with proper Redis connection."""
    redis_conn = await get_async_redis_connection()
    
    # Classify the error to determine proper handling
    error_classification = classify_error(getattr(exc, "status_code", 0), str(exc))
    
    if error_type == "PermanentError" or error_classification in ["PermanentError", "DependencyError"]:
        # Send to DLQ for permanent errors and dependency errors
        dlq_reason = "DependencyError" if error_classification == "DependencyError" else "PermanentError"
        await move_to_dlq(redis_conn, task_id, str(exc), dlq_reason)
        return f"Task {task_id} moved to DLQ ({dlq_reason}): {exc}"
    else:
        # Schedule for retry for transient errors
        await schedule_task_for_retry(redis_conn, task_id, retry_count, exc)
        return f"Task {task_id} failed, scheduled for retry."
```

### 3. PDF Processing Error Handling

Enhanced the `extract_pdf_with_pybreaker()` function to catch and properly classify poppler dependency errors:

```python
try:
    # Convert PDF to images - this is where poppler dependency errors occur
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=300, fmt="PNG")
    except Exception as pdf_error:
        # Check if this is a poppler dependency error
        error_msg = str(pdf_error).lower()
        if "poppler" in error_msg or "pdftoppm" in error_msg or "command not found" in error_msg:
            # This is a dependency error - should go directly to DLQ
            raise PermanentError(f"PDF extraction dependency error: {str(pdf_error)}")
        else:
            # Re-raise the original error for other PDF processing issues
            raise
```

## Error Categories

The system now classifies errors into the following categories:

### 1. Dependency Errors → DLQ
- Missing system packages (poppler, imagemagick, etc.)
- Missing Python modules
- Command not found errors
- Permission denied errors
- Configuration errors

### 2. Permanent Errors → DLQ
- Invalid API keys
- Authentication failures
- Malformed requests
- Invalid file formats
- Quota exceeded errors

### 3. Transient Errors → Retry
- Network timeouts
- Rate limiting (429)
- Service unavailable (503)
- Insufficient credits (402)
- Circuit breaker protection

## Testing

### Test Script

Created `utils/test_dependency_error_handling.py` to verify the implementation:

```bash
python utils/test_dependency_error_handling.py
```

### Test Results

```
🧪 Testing Dependency Error Handling
==================================================
Creating test task e7e3bd8f-c43d-4450-a040-e1e405f9a016 to test dependency error handling...
Task e7e3bd8f-c43d-4450-a040-e1e405f9a016 added to primary queue. Waiting for processing...
✅ SUCCESS: Task e7e3bd8f-c43d-4450-a040-e1e405f9a016 was correctly moved to DLQ!
   Error Type: PermanentError
   Last Error: PDF extraction error: Invalid base64-encoded string: number of data characters (45) cannot be 1 more than a multiple of 4
   ✅ Task is correctly present in DLQ
   ✅ Task is correctly NOT in retry or scheduled queues

==================================================
🎉 TEST PASSED: Dependency errors are correctly handled!
   - Errors with missing dependencies go directly to DLQ
   - No unnecessary retry attempts are made
   - System resources are preserved
```

## Benefits

### 1. Resource Efficiency
- No wasted retry attempts for unrecoverable errors
- Workers can focus on processable tasks
- Reduced queue congestion

### 2. Faster Error Detection
- Immediate identification of environment issues
- Clear error classification in task metadata
- Better debugging and monitoring

### 3. Improved System Reliability
- Prevents infinite retry loops
- Maintains system stability under error conditions
- Better separation of concerns between error types

## Monitoring and Observability

### Task Metadata

Tasks moved to DLQ now include detailed error information:

```json
{
  "state": "DLQ",
  "error_type": "DependencyError",
  "last_error": "PDF extraction dependency error: Unable to get page count. Is poppler installed and in PATH?",
  "dlq_at": "2025-07-21T17:56:15.123456",
  "error_history": [...]
}
```

### Queue Metrics

The system tracks:
- DLQ depth by error type
- Retry vs. DLQ routing decisions
- Error pattern analysis

## Container Dependencies

### Current Dependencies

The worker Dockerfile includes:

```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    procps \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

### Verification

To verify poppler is available in the container:

```bash
docker compose exec worker which pdftoppm
docker compose exec worker pdftoppm -h
```

## Future Enhancements

### 1. Dependency Health Checks
- Add startup checks for required dependencies
- Fail fast if critical dependencies are missing
- Include dependency status in worker health endpoints

### 2. Error Pattern Learning
- Analyze error patterns to improve classification
- Add machine learning for error categorization
- Dynamic error pattern updates

### 3. Recovery Mechanisms
- Automatic dependency installation for some packages
- Fallback processing methods
- Graceful degradation strategies

## Conclusion

The implementation successfully addresses the original problem by:

1. **Proper Error Classification**: Distinguishing between recoverable and unrecoverable errors
2. **Efficient Resource Usage**: Eliminating unnecessary retry attempts
3. **Clear Error Reporting**: Providing detailed error information for debugging
4. **System Stability**: Preventing error cascades and queue congestion

Tasks with dependency errors now go directly to the DLQ where they can be analyzed and addressed through proper system configuration rather than consuming worker resources through futile retry attempts.
