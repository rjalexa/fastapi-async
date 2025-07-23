"""Tests for worker state management and Redis interactions."""

import pytest
import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from src.worker.tasks import (
    update_task_state,
    move_to_dlq,
    schedule_task_for_retry,
    update_worker_heartbeat,
    PermanentError,
    TransientError,
)


class TestUpdateTaskState:
    """Test the update_task_state function."""

    @pytest.mark.asyncio
    async def test_basic_state_update(self):
        """Test basic state update functionality."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        
        # Create a proper async context manager mock
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)
        mock_pipeline.hset = AsyncMock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        await update_task_state(mock_redis, task_id, "ACTIVE", worker_id="worker-1")

        # Verify hset was called with correct mapping
        mock_pipeline.hset.assert_called_once()
        call_args = mock_pipeline.hset.call_args
        assert call_args[0][0] == f"task:{task_id}"
        mapping = call_args[1]["mapping"]
        assert mapping["state"] == "ACTIVE"
        assert mapping["worker_id"] == "worker-1"
        assert "updated_at" in mapping
        assert "started_at" in mapping

    @pytest.mark.asyncio
    async def test_state_specific_timestamps(self):
        """Test that state-specific timestamps are added correctly."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        
        # Create a proper async context manager mock
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)
        mock_pipeline.hset = AsyncMock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"

        # Test COMPLETED state
        await update_task_state(mock_redis, task_id, "COMPLETED")
        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "completed_at" in mapping

        # Test FAILED state
        await update_task_state(mock_redis, task_id, "FAILED")
        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "failed_at" in mapping

        # Test DLQ state
        await update_task_state(mock_redis, task_id, "DLQ")
        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "dlq_at" in mapping

        # Test SCHEDULED state
        await update_task_state(mock_redis, task_id, "SCHEDULED")
        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "scheduled_at" in mapping

    @pytest.mark.asyncio
    async def test_error_history_creation(self):
        """Test that error history is created and updated correctly."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {"state": "PENDING"}
        
        # Create a proper async context manager mock
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)
        mock_pipeline.hset = AsyncMock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        await update_task_state(
            mock_redis,
            task_id,
            "FAILED",
            last_error="Test error message",
            error_type="TransientError",
            retry_count=1,
        )

        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "error_history" in mapping

        # Parse the error history
        error_history = json.loads(mapping["error_history"])
        assert len(error_history) == 1
        assert error_history[0]["error"] == "Test error message"
        assert error_history[0]["error_type"] == "TransientError"
        assert error_history[0]["retry_count"] == 1
        assert error_history[0]["state_transition"] == "PENDING -> FAILED"

    @pytest.mark.asyncio
    async def test_retry_timestamps_creation(self):
        """Test that retry timestamps are created correctly."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {"state": "FAILED"}
        
        # Create a proper async context manager mock
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)
        mock_pipeline.hset = AsyncMock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        retry_after = datetime.utcnow().isoformat()
        await update_task_state(
            mock_redis,
            task_id,
            "SCHEDULED",
            last_error="Test error",
            error_type="TransientError",
            retry_count=2,
            retry_after=retry_after,
        )

        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "retry_timestamps" in mapping

        # Parse the retry timestamps
        retry_timestamps = json.loads(mapping["retry_timestamps"])
        assert len(retry_timestamps) == 1
        assert retry_timestamps[0]["retry_number"] == 2
        assert retry_timestamps[0]["retry_after"] == retry_after
        assert retry_timestamps[0]["error_type"] == "TransientError"

    @pytest.mark.asyncio
    async def test_retry_actual_start_tracking(self):
        """Test that actual retry start times are tracked correctly."""
        existing_retry_data = [
            {
                "retry_number": 1,
                "scheduled_at": "2023-01-01T10:00:00",
                "error_type": "TransientError",
            }
        ]

        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "state": "PENDING",
            "retry_timestamps": json.dumps(existing_retry_data),
        }
        
        # Create a proper async context manager mock
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)
        mock_pipeline.hset = AsyncMock()
        mock_pipeline.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        await update_task_state(mock_redis, task_id, "ACTIVE")

        mapping = mock_pipeline.hset.call_args[1]["mapping"]
        assert "retry_timestamps" in mapping

        # Parse the updated retry timestamps
        retry_timestamps = json.loads(mapping["retry_timestamps"])
        assert len(retry_timestamps) == 1
        assert "actual_start_at" in retry_timestamps[0]
        assert "delay_seconds" in retry_timestamps[0]

    @pytest.mark.asyncio
    async def test_queue_update_publishing(self):
        """Test that queue updates are published correctly."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {"state": "PENDING"}
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        await update_task_state(mock_redis, task_id, "ACTIVE")

        # Verify publish was called
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "queue-updates"

        # Parse the published data
        published_data = json.loads(call_args[0][1])
        assert published_data["type"] == "task_state_changed"
        assert published_data["task_id"] == task_id
        assert published_data["old_state"] == "PENDING"
        assert published_data["new_state"] == "ACTIVE"
        assert "queue_depths" in published_data

    @pytest.mark.asyncio
    async def test_publish_failure_handling(self):
        """Test that publish failures don't break state updates."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish.side_effect = Exception("Redis publish failed")

        task_id = "test-task-123"
        # This should not raise an exception
        await update_task_state(mock_redis, task_id, "ACTIVE")

        # Verify hset was still called despite publish failure
        mock_redis.hset.assert_called_once()


class TestMoveToDlq:
    """Test the move_to_dlq function."""

    @pytest.mark.asyncio
    async def test_move_to_dlq_basic(self):
        """Test basic DLQ movement functionality."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()
        mock_redis.lpush = AsyncMock()

        task_id = "test-task-123"
        reason = "Permanent error occurred"
        error_type = "PermanentError"

        await move_to_dlq(mock_redis, task_id, reason, error_type)

        # Verify task was added to DLQ
        mock_redis.lpush.assert_called_once_with("dlq:tasks", task_id)

        # Verify state was updated
        mock_redis.hset.assert_called_once()
        mapping = mock_redis.hset.call_args[1]["mapping"]
        assert mapping["state"] == "DLQ"
        assert mapping["last_error"] == reason
        assert mapping["error_type"] == error_type

    @pytest.mark.asyncio
    async def test_move_to_dlq_with_default_error_type(self):
        """Test DLQ movement with default error type."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()
        mock_redis.lpush = AsyncMock()

        task_id = "test-task-123"
        reason = "Some error"

        await move_to_dlq(mock_redis, task_id, reason)

        # Verify default error type was used
        mapping = mock_redis.hset.call_args[1]["mapping"]
        assert mapping["error_type"] == "Unknown"


class TestScheduleTaskForRetry:
    """Test the schedule_task_for_retry function."""

    @pytest.mark.asyncio
    async def test_schedule_task_for_retry_basic(self):
        """Test basic retry scheduling functionality."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()
        mock_redis.zadd = AsyncMock()

        task_id = "test-task-123"
        retry_count = 2
        exc = TransientError("API temporarily unavailable")

        with patch("src.worker.tasks.time.time", return_value=1000.0), \
             patch("src.worker.tasks.calculate_retry_delay", return_value=60.0):

            await schedule_task_for_retry(mock_redis, task_id, retry_count, exc)

            # Verify task was added to scheduled set with correct timestamp
            mock_redis.zadd.assert_called_once_with("tasks:scheduled", {task_id: 1060.0})

            # Verify state was updated
            mock_redis.hset.assert_called_once()
            mapping = mock_redis.hset.call_args[1]["mapping"]
            assert mapping["state"] == "SCHEDULED"
            assert mapping["retry_count"] == "3"  # retry_count + 1
            assert mapping["last_error"] == "API temporarily unavailable"

    @pytest.mark.asyncio
    async def test_schedule_task_for_retry_with_status_code(self):
        """Test retry scheduling with exception that has status code."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()
        mock_redis.zadd = AsyncMock()

        task_id = "test-task-123"
        retry_count = 1
        exc = TransientError("Rate limited")
        exc.status_code = 429

        with patch("src.worker.tasks.time.time", return_value=2000.0), \
             patch("src.worker.tasks.calculate_retry_delay", return_value=120.0), \
             patch("src.worker.tasks.classify_error", return_value="RateLimitError"):

            await schedule_task_for_retry(mock_redis, task_id, retry_count, exc)

            # Verify error classification was called with status code
            mapping = mock_redis.hset.call_args[1]["mapping"]
            assert mapping["error_type"] == "RateLimitError"


class TestUpdateWorkerHeartbeat:
    """Test the update_worker_heartbeat function."""

    @pytest.mark.asyncio
    async def test_update_worker_heartbeat(self):
        """Test worker heartbeat update functionality."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        worker_id = "worker-123"

        with patch("src.worker.tasks.time.time", return_value=1234567890.0):
            await update_worker_heartbeat(mock_redis, worker_id)

            # Verify setex was called with correct parameters
            mock_redis.setex.assert_called_once_with(
                f"worker:heartbeat:{worker_id}", 90, 1234567890.0
            )

    @pytest.mark.asyncio
    async def test_update_worker_heartbeat_different_worker(self):
        """Test heartbeat update for different worker ID."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        worker_id = "celery-hostname-456"

        with patch("src.worker.tasks.time.time", return_value=9876543210.0):
            await update_worker_heartbeat(mock_redis, worker_id)

            mock_redis.setex.assert_called_once_with(
                f"worker:heartbeat:{worker_id}", 90, 9876543210.0
            )


class TestErrorHistoryAndRetryTimestamps:
    """Test complex error history and retry timestamp scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_errors_in_history(self):
        """Test that multiple errors are accumulated in history."""
        existing_error_history = [
            {
                "timestamp": "2023-01-01T10:00:00",
                "error": "First error",
                "error_type": "TransientError",
                "retry_count": 1,
                "state_transition": "PENDING -> FAILED",
            }
        ]

        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "state": "SCHEDULED",
            "error_history": json.dumps(existing_error_history),
        }
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        await update_task_state(
            mock_redis,
            task_id,
            "FAILED",
            last_error="Second error",
            error_type="NetworkTimeout",
            retry_count=2,
        )

        mapping = mock_redis.hset.call_args[1]["mapping"]
        error_history = json.loads(mapping["error_history"])

        # Should have both errors
        assert len(error_history) == 2
        assert error_history[0]["error"] == "First error"
        assert error_history[1]["error"] == "Second error"
        assert error_history[1]["error_type"] == "NetworkTimeout"
        assert error_history[1]["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_malformed_existing_error_history(self):
        """Test handling of malformed existing error history."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "state": "PENDING",
            "error_history": "invalid json",
        }
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        await update_task_state(
            mock_redis,
            task_id,
            "FAILED",
            last_error="New error",
            error_type="TransientError",
            retry_count=1,
        )

        # Should create new error history despite malformed existing data
        mapping = mock_redis.hset.call_args[1]["mapping"]
        error_history = json.loads(mapping["error_history"])
        assert len(error_history) == 1
        assert error_history[0]["error"] == "New error"

    @pytest.mark.asyncio
    async def test_malformed_existing_retry_timestamps(self):
        """Test handling of malformed existing retry timestamps."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "state": "PENDING",
            "retry_timestamps": "not valid json",
        }
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_redis
        mock_redis.pipeline.return_value.__aexit__.return_value = None
        mock_redis.hset = AsyncMock()
        mock_redis.execute = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.zcard.return_value = 5
        mock_redis.publish = AsyncMock()

        task_id = "test-task-123"
        # This should not raise an exception
        await update_task_state(mock_redis, task_id, "ACTIVE")

        # Should still update state successfully
        mock_redis.hset.assert_called_once()
        mapping = mock_redis.hset.call_args[1]["mapping"]
        assert mapping["state"] == "ACTIVE"
