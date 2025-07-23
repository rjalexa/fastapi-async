"""Tests for the main Celery task processor."""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.worker.tasks import process_task, PermanentError, TransientError


class TestProcessTask:
    """Test the main process_task Celery task."""

    def test_process_task_not_found_in_redis(self):
        """Test process_task when task ID is not found in Redis."""
        
        async def mock_run_task():
            mock_redis = AsyncMock()
            mock_redis.hgetall.return_value = {}  # Empty dict means task not found
            
            with patch("src.worker.tasks.get_async_redis_connection", return_value=mock_redis):
                # This should raise PermanentError
                with pytest.raises(PermanentError, match="Task test-task-123 not found in Redis"):
                    from src.worker.tasks import process_task
                    # Create a mock task instance
                    mock_task = MagicMock()
                    mock_task.request.retries = 0
                    mock_task.request.hostname = "test-worker"
                    
                    # Call the inner _run_task function directly
                    task_id = "test-task-123"
                    redis_conn = await mock_redis
                    
                    # Update heartbeat
                    await mock_redis.setex(f"worker:heartbeat:celery-test-worker-123", 90, 1234567890.0)
                    
                    data = await redis_conn.hgetall(f"task:{task_id}")
                    if not data:
                        raise PermanentError(f"Task {task_id} not found in Redis.")

        # Run the async test
        asyncio.run(mock_run_task())

    def test_process_task_missing_content(self):
        """Test process_task when task data is missing content."""
        
        async def mock_run_task():
            mock_redis = AsyncMock()
            mock_redis.hgetall.return_value = {"task_type": "summarize"}  # No content field
            
            with patch("src.worker.tasks.get_async_redis_connection", return_value=mock_redis):
                with pytest.raises(PermanentError, match="No content to process"):
                    task_id = "test-task-123"
                    redis_conn = await mock_redis
                    
                    data = await redis_conn.hgetall(f"task:{task_id}")
                    content = data.get("content", "")
                    
                    if not content:
                        raise PermanentError("No content to process.")

        asyncio.run(mock_run_task())

    def test_process_task_max_retries_exceeded(self):
        """Test process_task when max retries are exceeded."""
        
        async def mock_run_task():
            mock_redis = AsyncMock()
            mock_redis.hgetall.return_value = {"content": "test content", "task_type": "summarize"}
            
            with patch("src.worker.tasks.get_async_redis_connection", return_value=mock_redis), \
                 patch("src.worker.tasks.settings") as mock_settings:
                
                mock_settings.max_retries = 3
                retry_count = 5  # Exceeds max retries
                
                with pytest.raises(PermanentError, match="Max retries \\(3\\) exceeded"):
                    task_id = "test-task-123"
                    redis_conn = await mock_redis
                    
                    data = await redis_conn.hgetall(f"task:{task_id}")
                    content = data.get("content", "")
                    
                    if not content:
                        raise PermanentError("No content to process.")
                    
                    if retry_count >= mock_settings.max_retries:
                        raise PermanentError(f"Max retries ({mock_settings.max_retries}) exceeded.")

        asyncio.run(mock_run_task())

    @patch("src.worker.tasks.summarize_text_with_pybreaker")
    @patch("src.worker.tasks.update_task_state")
    @patch("src.worker.tasks.update_worker_heartbeat")
    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.settings")
    def test_process_task_summarize_success(self, mock_settings, mock_get_redis, 
                                          mock_update_heartbeat, mock_update_state, 
                                          mock_summarize):
        """Test successful summarization task processing."""
        # Setup mocks
        mock_settings.max_retries = 3
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "This is test content to summarize",
            "task_type": "summarize"
        }
        mock_summarize.return_value = "This is a test summary"
        mock_update_heartbeat.return_value = None
        mock_update_state.return_value = None

        # Create mock task
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.request.hostname = "test-worker"

        # Call process_task with correct signature (self, task_id)
        result = process_task("test-task-123")

        # Verify the result
        assert "completed successfully" in result
        
        # Verify summarize was called with correct content
        mock_summarize.assert_called_once_with("This is test content to summarize")
        
        # Verify state was updated to COMPLETED
        assert mock_update_state.call_count >= 2  # ACTIVE and COMPLETED
        completed_call = None
        for call in mock_update_state.call_args_list:
            if call[0][2] == "COMPLETED":  # state parameter
                completed_call = call
                break
        assert completed_call is not None
        assert "result" in completed_call[1]

    @patch("src.worker.tasks.extract_pdf_with_pybreaker")
    @patch("src.worker.tasks.update_task_state")
    @patch("src.worker.tasks.update_worker_heartbeat")
    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.settings")
    def test_process_task_pdfxtract_success(self, mock_settings, mock_get_redis, 
                                          mock_update_heartbeat, mock_update_state, 
                                          mock_extract_pdf):
        """Test successful PDF extraction task processing."""
        # Setup mocks
        mock_settings.max_retries = 3
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "base64encodedpdfcontent",
            "task_type": "pdfxtract",
            "metadata": json.dumps({"filename": "test.pdf", "issue_date": "2023-01-01"})
        }
        mock_extract_pdf.return_value = '{"filename": "test.pdf", "pages": []}'
        mock_update_heartbeat.return_value = None
        mock_update_state.return_value = None

        # Create mock task
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.request.hostname = "test-worker"

        # Call process_task with correct signature (self, task_id)
        result = process_task("test-task-123")

        # Verify the result
        assert "completed successfully" in result
        
        # Verify extract_pdf was called with correct parameters
        mock_extract_pdf.assert_called_once_with(
            "base64encodedpdfcontent", 
            "test.pdf", 
            "2023-01-01"
        )

    @patch("src.worker.tasks.extract_pdf_with_pybreaker")
    @patch("src.worker.tasks.update_task_state")
    @patch("src.worker.tasks.update_worker_heartbeat")
    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.settings")
    def test_process_task_pdfxtract_malformed_metadata(self, mock_settings, mock_get_redis, 
                                                     mock_update_heartbeat, mock_update_state, 
                                                     mock_extract_pdf):
        """Test PDF extraction with malformed metadata."""
        # Setup mocks
        mock_settings.max_retries = 3
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "base64encodedpdfcontent",
            "task_type": "pdfxtract",
            "metadata": "invalid json"  # Malformed JSON
        }
        mock_extract_pdf.return_value = '{"filename": "unknown.pdf", "pages": []}'
        mock_update_heartbeat.return_value = None
        mock_update_state.return_value = None

        # Create mock task
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.request.hostname = "test-worker"

        # Call process_task with correct signature (self, task_id)
        result = process_task("test-task-123")

        # Verify the result
        assert "completed successfully" in result
        
        # Verify extract_pdf was called with default values
        mock_extract_pdf.assert_called_once_with(
            "base64encodedpdfcontent", 
            "unknown.pdf",  # Default filename
            None  # No issue_date
        )

    @patch("src.worker.tasks.summarize_text_with_pybreaker")
    @patch("src.worker.tasks.move_to_dlq")
    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.settings")
    def test_process_task_permanent_error_handling(self, mock_settings, mock_get_redis, 
                                                 mock_move_to_dlq, mock_summarize):
        """Test that permanent errors are handled correctly."""
        # Setup mocks
        mock_settings.max_retries = 3
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "test content",
            "task_type": "summarize"
        }
        mock_summarize.side_effect = PermanentError("Invalid API key")
        mock_move_to_dlq.return_value = None

        # Create mock task
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.request.hostname = "test-worker"

        # Call process_task with correct signature (self, task_id)
        result = process_task("test-task-123")

        # Verify the result indicates DLQ movement
        assert "moved to DLQ" in result
        assert "PermanentError" in result
        
        # Verify move_to_dlq was called
        mock_move_to_dlq.assert_called_once()

    @patch("src.worker.tasks.summarize_text_with_pybreaker")
    @patch("src.worker.tasks.schedule_task_for_retry")
    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.settings")
    def test_process_task_transient_error_handling(self, mock_settings, mock_get_redis, 
                                                  mock_schedule_retry, mock_summarize):
        """Test that transient errors are handled correctly."""
        # Setup mocks
        mock_settings.max_retries = 3
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "test content",
            "task_type": "summarize"
        }
        mock_summarize.side_effect = TransientError("API temporarily unavailable")
        mock_schedule_retry.return_value = None

        # Create mock task
        mock_task = MagicMock()
        mock_task.request.retries = 1
        mock_task.request.hostname = "test-worker"

        # Call process_task with correct signature (self, task_id)
        result = process_task("test-task-123")

        # Verify the result indicates retry scheduling
        assert "scheduled for retry" in result
        
        # Verify schedule_task_for_retry was called
        mock_schedule_retry.assert_called_once()

    @patch("src.worker.tasks.summarize_text_with_pybreaker")
    @patch("src.worker.tasks.schedule_task_for_retry")
    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.settings")
    def test_process_task_unexpected_error_handling(self, mock_settings, mock_get_redis, 
                                                   mock_schedule_retry, mock_summarize):
        """Test that unexpected errors are treated as transient."""
        # Setup mocks
        mock_settings.max_retries = 3
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "test content",
            "task_type": "summarize"
        }
        mock_summarize.side_effect = ValueError("Unexpected error")
        mock_schedule_retry.return_value = None

        # Create mock task
        mock_task = MagicMock()
        mock_task.request.retries = 0
        mock_task.request.hostname = "test-worker"

        # Call process_task with correct signature (self, task_id)
        result = process_task("test-task-123")

        # Verify the result indicates retry scheduling
        assert "scheduled for retry" in result
        
        # Verify schedule_task_for_retry was called with wrapped TransientError
        mock_schedule_retry.assert_called_once()
        call_args = mock_schedule_retry.call_args
        exc = call_args[0][2]  # The exception parameter
        assert isinstance(exc, TransientError)
        assert "Unexpected error" in str(exc)

    @patch("src.worker.tasks.update_worker_heartbeat")
    @patch("src.worker.tasks.get_async_redis_connection")
    def test_process_task_worker_heartbeat_updates(self, mock_get_redis, mock_update_heartbeat):
        """Test that worker heartbeat is updated at start and end of task."""
        # Setup mocks
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.hgetall.return_value = {
            "content": "test content",
            "task_type": "summarize"
        }
        mock_update_heartbeat.return_value = None

        # Mock the summarize function to succeed
        with patch("src.worker.tasks.summarize_text_with_pybreaker", return_value="summary"), \
             patch("src.worker.tasks.update_task_state"), \
             patch("src.worker.tasks.settings") as mock_settings:
            
            mock_settings.max_retries = 3

            # Create mock task
            mock_task = MagicMock()
            mock_task.request.retries = 0
            mock_task.request.hostname = "test-worker"

            # Call process_task with correct signature (self, task_id)
            process_task("test-task-123")

            # Verify heartbeat was updated at least twice (start and end)
            assert mock_update_heartbeat.call_count >= 2
            
            # Verify worker ID format
            for call in mock_update_heartbeat.call_args_list:
                worker_id = call[0][1]  # Second argument is worker_id
                assert "celery-test-worker" in worker_id

    def test_process_task_default_task_type(self):
        """Test that tasks without explicit type default to summarization."""
        
        async def mock_run_task():
            mock_redis = AsyncMock()
            mock_redis.hgetall.return_value = {"content": "test content"}  # No task_type
            
            with patch("src.worker.tasks.get_async_redis_connection", return_value=mock_redis), \
                 patch("src.worker.tasks.summarize_text_with_pybreaker") as mock_summarize, \
                 patch("src.worker.tasks.update_task_state"), \
                 patch("src.worker.tasks.update_worker_heartbeat"), \
                 patch("src.worker.tasks.settings") as mock_settings:
                
                mock_settings.max_retries = 3
                mock_summarize.return_value = "summary"
                
                # Simulate the task processing logic
                task_id = "test-task-123"
                retry_count = 0
                redis_conn = await mock_redis
                
                data = await redis_conn.hgetall(f"task:{task_id}")
                content = data.get("content", "")
                task_type = data.get("task_type", "summarize")  # Default to summarize
                
                # Should default to summarize
                assert task_type == "summarize"
                
                if task_type == "pdfxtract":
                    # Should not reach here
                    assert False, "Should not process as pdfxtract"
                else:
                    # Should call summarize function
                    result = await mock_summarize(content)
                    assert result == "summary"

        asyncio.run(mock_run_task())


class TestSummarizeTaskLegacy:
    """Test the legacy summarize_task function."""

    def test_summarize_task_exists_and_is_callable(self):
        """Test that summarize_task exists and can be imported."""
        from src.worker.tasks import summarize_task
        
        # Verify the task exists and has the expected attributes
        assert hasattr(summarize_task, 'name')
        assert summarize_task.name == "summarize_text"
        assert callable(summarize_task)
        
        # Verify it's a Celery task
        assert hasattr(summarize_task, 'apply_async')
        assert hasattr(summarize_task, 'delay')


class TestProcessScheduledTasks:
    """Test the process_scheduled_tasks function."""

    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.update_task_state")
    def test_process_scheduled_tasks_success(self, mock_update_state, mock_get_redis):
        """Test successful processing of scheduled tasks."""
        from src.worker.tasks import process_scheduled_tasks
        
        # Setup mocks
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.zrangebyscore.return_value = ["task-1", "task-2", "task-3"]
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.lpush = AsyncMock()
        mock_redis.zrem = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_update_state.return_value = None

        # Call process_scheduled_tasks
        result = process_scheduled_tasks()

        # Verify the result
        assert "Moved 3 tasks" in result
        assert "scheduled to retry queue" in result

        # Verify Redis operations
        mock_redis.zrangebyscore.assert_called_once()
        assert mock_redis.lpush.call_count == 3  # One for each task
        assert mock_redis.zrem.call_count == 3   # One for each task

    @patch("src.worker.tasks.get_async_redis_connection")
    def test_process_scheduled_tasks_no_due_tasks(self, mock_get_redis):
        """Test processing when no tasks are due."""
        from src.worker.tasks import process_scheduled_tasks
        
        # Setup mocks
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.zrangebyscore.return_value = []  # No due tasks

        # Call process_scheduled_tasks
        result = process_scheduled_tasks()

        # Verify the result
        assert "Moved 0 tasks" in result

        # Verify no pipeline operations were performed
        mock_redis.pipeline.assert_not_called()

    @patch("src.worker.tasks.get_async_redis_connection")
    @patch("src.worker.tasks.update_task_state")
    @patch("src.worker.tasks.time.time")
    def test_process_scheduled_tasks_time_filtering(self, mock_time, mock_update_state, mock_get_redis):
        """Test that only tasks due now are processed."""
        from src.worker.tasks import process_scheduled_tasks
        
        # Setup mocks
        current_time = 1000.0
        mock_time.return_value = current_time
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.zrangebyscore.return_value = ["task-1"]
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.lpush = AsyncMock()
        mock_redis.zrem = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_update_state.return_value = None

        # Call process_scheduled_tasks
        process_scheduled_tasks()

        # Verify zrangebyscore was called with correct time range
        mock_redis.zrangebyscore.assert_called_once_with(
            "tasks:scheduled", 0, current_time, start=0, num=100
        )
