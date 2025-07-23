"""Comprehensive tests for API services."""

import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.api.services import (
    RedisService,
    TaskService,
    QueueService,
    HealthService,
)
from src.api.schemas import TaskState, TaskType, QueueName, QUEUE_KEY_MAP
from src.api.config import settings


class TestRedisService:
    """Test RedisService functionality."""

    @pytest_asyncio.fixture
    async def redis_service(self):
        """Create a RedisService instance for testing."""
        service = RedisService("redis://localhost:6379")
        yield service
        await service.close()

    @pytest.mark.asyncio
    async def test_initialize_optimized_success(self, redis_service):
        """Test successful initialization with optimized Redis."""
        mock_manager = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("src.api.services.initialize_redis", return_value=mock_manager), \
             patch("src.api.services.get_standard_redis", return_value=mock_redis):
            
            await redis_service.initialize()
            
            assert redis_service._manager == mock_manager
            assert redis_service.redis == mock_redis
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_fallback_to_simple(self, redis_service):
        """Test fallback to simple Redis when optimized fails."""
        mock_simple_manager = AsyncMock()
        mock_simple_redis = AsyncMock()
        mock_simple_redis.ping.return_value = True

        with patch("src.api.services.initialize_redis", side_effect=Exception("Optimized failed")), \
             patch("src.api.services.initialize_simple_redis", return_value=mock_simple_manager), \
             patch("src.api.services.get_simple_redis", return_value=mock_simple_redis), \
             patch("src.api.services.close_redis"):
            
            await redis_service.initialize()
            
            assert redis_service._simple_manager == mock_simple_manager
            assert redis_service.redis == mock_simple_redis
            mock_simple_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_basic_fallback(self, redis_service):
        """Test fallback to basic Redis when both optimized and simple fail."""
        mock_basic_redis = AsyncMock()

        with patch("src.api.services.initialize_redis", side_effect=Exception("Optimized failed")), \
             patch("src.api.services.initialize_simple_redis", side_effect=Exception("Simple failed")), \
             patch("redis.asyncio.from_url", return_value=mock_basic_redis):
            
            await redis_service.initialize()
            
            assert redis_service.redis == mock_basic_redis

    @pytest.mark.asyncio
    async def test_ping_success(self, redis_service):
        """Test successful Redis ping."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        redis_service.redis = mock_redis

        result = await redis_service.ping()
        
        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_failure(self, redis_service):
        """Test Redis ping failure."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        redis_service.redis = mock_redis

        result = await redis_service.ping()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_auto_initialize(self, redis_service):
        """Test ping auto-initializes Redis if not initialized."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = "PONG"

        with patch.object(redis_service, 'initialize') as mock_init:
            redis_service.redis = None
            mock_init.return_value = None
            redis_service.redis = mock_redis  # Set after mock init

            result = await redis_service.ping()
            
            assert result is True
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pool_stats_optimized(self, redis_service):
        """Test getting pool stats from optimized manager."""
        mock_manager = AsyncMock()
        mock_stats = {"connections": 10, "available": 5}
        mock_manager.get_pool_stats.return_value = mock_stats
        redis_service._manager = mock_manager

        result = await redis_service.get_pool_stats()
        
        assert result == mock_stats

    @pytest.mark.asyncio
    async def test_get_pool_stats_simple(self, redis_service):
        """Test getting pool stats from simple manager."""
        mock_simple_manager = AsyncMock()
        mock_stats = {"connections": 5, "available": 3}
        mock_simple_manager.get_pool_stats.return_value = mock_stats
        redis_service._simple_manager = mock_simple_manager

        result = await redis_service.get_pool_stats()
        
        assert result == mock_stats

    @pytest.mark.asyncio
    async def test_get_pool_stats_not_initialized(self, redis_service):
        """Test getting pool stats when not initialized."""
        result = await redis_service.get_pool_stats()
        
        assert result == {"status": "not_initialized"}

    @pytest.mark.asyncio
    async def test_publish_queue_update(self, redis_service):
        """Test publishing queue updates."""
        mock_redis = AsyncMock()
        redis_service.redis = mock_redis
        
        update_data = {"type": "task_created", "task_id": "test-123"}
        
        await redis_service.publish_queue_update(update_data)
        
        mock_redis.publish.assert_called_once_with(
            "queue-updates", json.dumps(update_data)
        )

    @pytest.mark.asyncio
    async def test_close_optimized(self, redis_service):
        """Test closing optimized Redis connection."""
        mock_manager = AsyncMock()
        redis_service._manager = mock_manager

        with patch("src.api.services.close_redis") as mock_close:
            await redis_service.close()
            
            mock_close.assert_called_once()
            assert redis_service._manager is None
            assert redis_service.redis is None

    @pytest.mark.asyncio
    async def test_close_simple(self, redis_service):
        """Test closing simple Redis connection."""
        mock_simple_manager = AsyncMock()
        redis_service._simple_manager = mock_simple_manager

        with patch("src.api.services.close_simple_redis") as mock_close:
            await redis_service.close()
            
            mock_close.assert_called_once()
            assert redis_service._simple_manager is None
            assert redis_service.redis is None


class TestTaskService:
    """Test TaskService functionality."""

    @pytest_asyncio.fixture
    async def task_service(self):
        """Create a TaskService instance for testing."""
        mock_redis_service = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis_service.redis = mock_redis
        return TaskService(mock_redis_service)

    @pytest.mark.asyncio
    async def test_create_task_success(self, task_service):
        """Test successful task creation."""
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__.return_value = mock_pipeline
        mock_pipeline.__aexit__.return_value = None
        
        task_service.redis.pipeline.return_value = mock_pipeline
        task_service.redis.llen.return_value = 5
        
        content = "Test content"
        task_type = TaskType.SUMMARIZE
        metadata = {"key": "value"}
        
        with patch("uuid.uuid4", return_value="test-task-id"):
            task_id = await task_service.create_task(content, task_type, metadata)
        
        assert task_id == "test-task-id"
        mock_pipeline.hset.assert_called_once()
        mock_pipeline.lpush.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_task_without_metadata(self, task_service):
        """Test task creation without metadata."""
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__.return_value = mock_pipeline
        mock_pipeline.__aexit__.return_value = None
        
        task_service.redis.pipeline.return_value = mock_pipeline
        task_service.redis.llen.return_value = 3
        
        content = "Test content"
        
        with patch("uuid.uuid4", return_value="test-task-id"):
            task_id = await task_service.create_task(content)
        
        assert task_id == "test-task-id"
        # Verify hset was called with task data (without metadata)
        call_args = mock_pipeline.hset.call_args
        assert call_args[0][0] == "task:test-task-id"
        task_data = call_args[1]["mapping"]
        assert "metadata" not in task_data

    @pytest.mark.asyncio
    async def test_get_task_success(self, task_service):
        """Test successful task retrieval."""
        task_data = {
            "task_id": "test-123",
            "state": TaskState.PENDING.value,
            "content": "Test content",
            "retry_count": "0",
            "max_retries": "3",
            "last_error": "",
            "error_type": "",
            "retry_after": "",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "completed_at": "",
            "result": "",
            "task_type": TaskType.SUMMARIZE.value,
            "error_history": "[]",
            "state_history": "[]",
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.get_task("test-123")
        
        assert result is not None
        assert result.task_id == "test-123"
        assert result.state == TaskState.PENDING
        assert result.content == "Test content"
        assert result.task_type == TaskType.SUMMARIZE

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, task_service):
        """Test task retrieval when task doesn't exist."""
        task_service.redis.hgetall.return_value = {}
        
        result = await task_service.get_task("nonexistent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_task_with_completed_at(self, task_service):
        """Test task retrieval with completed_at timestamp."""
        task_data = {
            "task_id": "test-123",
            "state": TaskState.COMPLETED.value,
            "content": "Test content",
            "retry_count": "0",
            "max_retries": "3",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T01:00:00",
            "task_type": TaskType.SUMMARIZE.value,
            "error_history": "[]",
            "state_history": "[]",
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.get_task("test-123")
        
        assert result is not None
        assert result.completed_at is not None
        assert result.completed_at == datetime.fromisoformat("2024-01-01T01:00:00")

    @pytest.mark.asyncio
    async def test_get_task_invalid_task_type(self, task_service):
        """Test task retrieval with invalid task type defaults to SUMMARIZE."""
        task_data = {
            "task_id": "test-123",
            "state": TaskState.PENDING.value,
            "content": "Test content",
            "retry_count": "0",
            "max_retries": "3",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "task_type": "INVALID_TYPE",
            "error_history": "[]",
            "state_history": "[]",
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.get_task("test-123")
        
        assert result is not None
        assert result.task_type == TaskType.SUMMARIZE

    @pytest.mark.asyncio
    async def test_retry_task_success(self, task_service):
        """Test successful task retry."""
        task_data = {
            "task_id": "test-123",
            "state": TaskState.FAILED.value,
            "retry_count": "2",
            "state_history": "[]",
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.retry_task("test-123")
        
        assert result is True
        task_service.redis.hset.assert_called_once()
        task_service.redis.lpush.assert_called_once_with(
            QUEUE_KEY_MAP[QueueName.RETRY], "test-123"
        )

    @pytest.mark.asyncio
    async def test_retry_task_not_found(self, task_service):
        """Test retry task when task doesn't exist."""
        task_service.redis.hgetall.return_value = {}
        
        result = await task_service.retry_task("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_task_invalid_state(self, task_service):
        """Test retry task with invalid state."""
        task_data = {
            "task_id": "test-123",
            "state": TaskState.PENDING.value,  # Can't retry pending task
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.retry_task("test-123")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_task_reset_retry_count(self, task_service):
        """Test retry task with reset retry count."""
        task_data = {
            "task_id": "test-123",
            "state": TaskState.FAILED.value,
            "retry_count": "3",
            "state_history": "[]",
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.retry_task("test-123", reset_retry_count=True)
        
        assert result is True
        # Verify retry_count was reset to 0
        call_args = task_service.redis.hset.call_args
        updates = call_args[1]["mapping"]
        assert updates["retry_count"] == "0"

    @pytest.mark.asyncio
    async def test_delete_task_success(self, task_service):
        """Test successful task deletion."""
        task_data = {"task_id": "test-123", "state": TaskState.COMPLETED.value}
        
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__.return_value = mock_pipeline
        mock_pipeline.__aexit__.return_value = None
        
        task_service.redis.hgetall.return_value = task_data
        task_service.redis.pipeline.return_value = mock_pipeline
        
        result = await task_service.delete_task("test-123")
        
        assert result is True
        mock_pipeline.delete.assert_called()
        mock_pipeline.lrem.assert_called()
        mock_pipeline.zrem.assert_called()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, task_service):
        """Test delete task when task doesn't exist."""
        task_service.redis.hgetall.return_value = {}
        
        result = await task_service.delete_task("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_task_corrupted_force_delete(self, task_service):
        """Test delete corrupted task with force delete."""
        # First call fails, second call for exists check returns True
        task_service.redis.hgetall.side_effect = [Exception("Corrupted"), {}]
        task_service.redis.exists.return_value = True
        
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__.return_value = mock_pipeline
        mock_pipeline.__aexit__.return_value = None
        task_service.redis.pipeline.return_value = mock_pipeline
        
        result = await task_service.delete_task("corrupted-123")
        
        assert result is True
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_requeue_orphaned_tasks_success(self, task_service):
        """Test successful requeuing of orphaned tasks."""
        # Mock queue contents
        task_service.redis.lrange.side_effect = [
            ["queued-1", "queued-2"],  # primary queue
            ["retry-1"],  # retry queue
            ["dlq-1"],  # dlq
        ]
        task_service.redis.zrange.return_value = ["scheduled-1"]  # scheduled queue
        
        # Mock scan_iter to return orphaned tasks
        async def mock_scan_iter(pattern):
            if pattern == "task:*":
                yield "task:orphaned-1"
                yield "task:orphaned-2"
                yield "task:queued-1"  # This one is already queued
        
        task_service.redis.scan_iter = mock_scan_iter
        
        # Mock task states
        def mock_hget(key, field):
            if key == "task:orphaned-1" and field == "state":
                return TaskState.PENDING.value
            elif key == "task:orphaned-2" and field == "state":
                return TaskState.PENDING.value
            elif key == "task:queued-1" and field == "state":
                return TaskState.ACTIVE.value  # Not orphaned
            return None
        
        task_service.redis.hget.side_effect = mock_hget
        
        result = await task_service.requeue_orphaned_tasks()
        
        assert result["found"] == 2
        assert result["requeued"] == 2
        assert len(result["errors"]) == 0
        assert "Found 2 orphaned tasks" in result["message"]

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, task_service):
        """Test listing tasks when no tasks exist."""
        async def mock_scan_iter(pattern):
            return
            yield  # Make it an async generator
        
        task_service.redis.scan_iter = mock_scan_iter
        
        result = await task_service.list_tasks()
        
        assert result.total_items == 0
        assert len(result.tasks) == 0
        assert result.total_pages == 0

    @pytest.mark.asyncio
    async def test_list_tasks_with_filters(self, task_service):
        """Test listing tasks with status filter."""
        # Mock scan_iter to return task keys
        async def mock_scan_iter(pattern):
            if pattern == "task:*":
                yield "task:test-1"
                yield "task:test-2"
        
        task_service.redis.scan_iter = mock_scan_iter
        
        # Mock task data
        def mock_hgetall(key):
            if key == "task:test-1":
                return {
                    "task_id": "test-1",
                    "state": TaskState.PENDING.value,
                    "content": "Content 1",
                    "retry_count": "0",
                    "max_retries": "3",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "task_type": TaskType.SUMMARIZE.value,
                    "error_history": "[]",
                    "state_history": "[]",
                }
            elif key == "task:test-2":
                return {
                    "task_id": "test-2",
                    "state": TaskState.COMPLETED.value,
                    "content": "Content 2",
                    "retry_count": "0",
                    "max_retries": "3",
                    "created_at": "2024-01-01T01:00:00",
                    "updated_at": "2024-01-01T01:00:00",
                    "task_type": TaskType.SUMMARIZE.value,
                    "error_history": "[]",
                    "state_history": "[]",
                }
            return {}
        
        task_service.redis.hgetall.side_effect = mock_hgetall
        
        # Filter by PENDING status
        result = await task_service.list_tasks(status=TaskState.PENDING)
        
        assert result.total_items == 1
        assert len(result.tasks) == 1
        assert result.tasks[0].task_id == "test-1"
        assert result.tasks[0].state == TaskState.PENDING

    @pytest.mark.asyncio
    async def test_list_tasks_by_task_id_exact_match(self, task_service):
        """Test listing tasks by exact task ID match."""
        task_data = {
            "task_id": "exact-match-123",
            "state": TaskState.PENDING.value,
            "content": "Test content",
            "retry_count": "0",
            "max_retries": "3",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "task_type": TaskType.SUMMARIZE.value,
            "error_history": "[]",
            "state_history": "[]",
        }
        
        task_service.redis.hgetall.return_value = task_data
        
        result = await task_service.list_tasks(task_id="exact-match-123")
        
        assert result.total_items == 1
        assert len(result.tasks) == 1
        assert result.tasks[0].task_id == "exact-match-123"

    @pytest.mark.asyncio
    async def test_list_task_summaries_success(self, task_service):
        """Test listing task summaries."""
        # Mock scan_iter to return task keys
        async def mock_scan_iter(pattern):
            if pattern == "task:*":
                yield "task:test-1"
        
        task_service.redis.scan_iter = mock_scan_iter
        
        # Mock task data
        task_service.redis.hgetall.return_value = {
            "task_id": "test-1",
            "state": TaskState.COMPLETED.value,
            "content": "This is test content",
            "retry_count": "0",
            "max_retries": "3",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "result": "Test result",
            "task_type": TaskType.SUMMARIZE.value,
            "error_history": "[]",
            "state_history": "[]",
        }
        
        result = await task_service.list_task_summaries()
        
        assert result.total_items == 1
        assert len(result.tasks) == 1
        summary = result.tasks[0]
        assert summary.task_id == "test-1"
        assert summary.content_length == len("This is test content")
        assert summary.has_result is True


class TestQueueService:
    """Test QueueService functionality."""

    @pytest_asyncio.fixture
    async def queue_service(self):
        """Create a QueueService instance for testing."""
        mock_redis_service = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis_service.redis = mock_redis
        return QueueService(mock_redis_service)

    @pytest.mark.asyncio
    async def test_get_queue_status_success(self, queue_service):
        """Test successful queue status retrieval."""
        # Mock queue depths
        queue_service.redis.llen.side_effect = [5, 2, 1]  # primary, retry, dlq
        queue_service.redis.zcard.return_value = 3  # scheduled
        
        # Mock task state scanning
        async def mock_scan_iter(pattern):
            if pattern == "task:*":
                yield "task:1"
                yield "task:2"
                yield "task:3"
        
        queue_service.redis.scan_iter = mock_scan_iter
        
        # Mock task states
        def mock_hget(key, field):
            if field == "state":
                if key == "task:1":
                    return "PENDING"
                elif key == "task:2":
                    return "ACTIVE"
                elif key == "task:3":
                    return "COMPLETED"
            return None
        
        queue_service.redis.hget.side_effect = mock_hget
        
        result = await queue_service.get_queue_status()
        
        assert result.queues[QueueName.PRIMARY.value] == 5
        assert result.queues[QueueName.RETRY.value] == 2
        assert result.queues[QueueName.SCHEDULED.value] == 3
        assert result.queues[QueueName.DLQ.value] == 1
        assert result.states["PENDING"] == 1
        assert result.states["ACTIVE"] == 1
        assert result.states["COMPLETED"] == 1

    @pytest.mark.asyncio
    async def test_get_dlq_tasks_success(self, queue_service):
        """Test successful DLQ tasks retrieval."""
        queue_service.redis.lrange.return_value = ["dlq-task-1", "dlq-task-2"]
        
        # Mock task data
        def mock_hgetall(key):
            if key == "dlq:task:dlq-task-1":
                return {
                    "task_id": "dlq-task-1",
                    "state": TaskState.DLQ.value,
                    "content": "DLQ content 1",
                    "retry_count": "3",
                    "max_retries": "3",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "task_type": TaskType.SUMMARIZE.value,
                    "error_history": "[]",
                    "state_history": "[]",
                }
            elif key == "task:dlq-task-2":  # Fallback to regular task storage
                return {
                    "task_id": "dlq-task-2",
                    "state": TaskState.DLQ.value,
                    "content": "DLQ content 2",
                    "retry_count": "3",
                    "max_retries": "3",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "task_type": TaskType.SUMMARIZE.value,
                    "error_history": "[]",
                    "state_history": "[]",
                }
            return {}
        
        queue_service.redis.hgetall.side_effect = mock_hgetall
        
        result = await queue_service.get_dlq_tasks(limit=10)
        
        assert len(result) == 2
        assert result[0].task_id == "dlq-task-1"
        assert result[1].task_id == "dlq-task-2"

    @pytest.mark.asyncio
    async def test_list_tasks_in_queue_list_queue(self, queue_service):
        """Test listing tasks in a list-based queue."""
        queue_service.redis.lrange.return_value = ["task-1", "task-2", "task-3"]
        
        result = await queue_service.list_tasks_in_queue("primary", limit=5)
        
        assert result == ["task-1", "task-2", "task-3"]
        queue_service.redis.lrange.assert_called_once_with(
            QUEUE_KEY_MAP[QueueName.PRIMARY], 0, 4
        )

    @pytest.mark.asyncio
    async def test_list_tasks_in_queue_scheduled(self, queue_service):
        """Test listing tasks in scheduled queue (sorted set)."""
        queue_service.redis.zrange.return_value = ["scheduled-1", "scheduled-2"]
        
        result = await queue_service.list_tasks_in_queue("scheduled", limit=5)
        
        assert result == ["scheduled-1", "scheduled-2"]
        queue_service.redis.zrange.assert_called_once_with(
            QUEUE_KEY_MAP[QueueName.SCHEDULED], 0, 4
        )

    @pytest.mark.asyncio
    async def test_list_tasks_in_queue_invalid(self, queue_service):
        """Test listing tasks in invalid queue."""
        result = await queue_service.list_tasks_in_queue("invalid_queue", limit=5)
        
        assert result == []

    @pytest.mark.asyncio
    async def test_calculate_adaptive_retry_ratio(self, queue_service):
        """Test adaptive retry ratio calculation."""
        # Normal level
        ratio = queue_service._calculate_adaptive_retry_ratio(50)
        assert ratio == settings.default_retry_ratio
        
        # Warning level
        with patch.object(settings, 'retry_queue_warning', 100), \
             patch.object(settings, 'retry_queue_critical', 200):
            ratio = queue_service._calculate_adaptive_retry_ratio(150)
            assert ratio == 0.2
            
            # Critical level
            ratio = queue_service._calculate_adaptive_retry_ratio(250)
            assert ratio == 0.1


class TestHealthService:
    """Test HealthService functionality."""

    @pytest_asyncio.fixture
    async def health_service(self):
        """Create a HealthService instance for testing."""
        mock_redis_service = AsyncMock()
        mock_celery_app = MagicMock()
        return HealthService(mock_redis_service, mock_celery_app)

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self, health_service):
        """Test health check when all components are healthy."""
        health_service.redis_service.ping.return_value = True
        
        with patch.object(health_service, '_check_workers_via_redis', return_value=True):
            result = await health_service.check_health()
        
        assert result["status"] == "healthy"
        assert result["components"]["redis"] is True
        assert result["components"]["workers"] is True

    @pytest.mark.asyncio
    async def test_check_health_redis_unhealthy(self, health_service):
        """Test health check when Redis is unhealthy."""
        health_service.redis_service.ping.return_value = False
        
        with patch.object(health_service, '_check_workers_via_redis', return_value=True):
            result = await health_service.check_health()
        
        assert result["status"] == "unhealthy"
        assert result["components"]["redis"] is False
        assert result["components"]["workers"] is True

    @pytest.mark.asyncio
    async def test_check_health_workers_unhealthy(self, health_service):
        """Test health check when workers are unhealthy."""
        health_service.redis_service.ping.return_value = True
        
        with patch.object(health_service, '_check_workers_via_redis', return_value=False):
            result = await health_service.check_health()
        
        assert result["status"] == "unhealthy"
        assert result["components"]["redis"] is True
        assert result["components"]["workers"] is False

    @pytest.mark.asyncio
    async def test_check_workers_via_redis_with_heartbeats(self, health_service):
        """Test worker check via Redis heartbeats."""
        import time
        current_time = time.time()
        recent_heartbeat = str(current_time - 30)  # 30 seconds ago
        
        # Mock scan_iter to return heartbeat keys
        async def mock_scan_iter(pattern):
            if pattern == "worker:heartbeat:*":
                yield "worker:heartbeat:worker-1"
                yield "worker:heartbeat:worker-2"
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        health_service.redis_service.redis.get.return_value = recent_heartbeat
        
        result = await health_service._check_workers_via_redis()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_check_workers_via_redis_no_heartbeats(self, health_service):
        """Test worker check when no heartbeats found."""
        # Mock scan_iter to return no heartbeat keys
        async def mock_scan_iter(pattern):
            return
            yield  # Make it an async generator
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        
        result = await health_service._check_workers_via_redis()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_workers_via_redis_old_heartbeats(self, health_service):
        """Test worker check with old heartbeats."""
        import time
        current_time = time.time()
        old_heartbeat = str(current_time - 120)  # 2 minutes ago (too old)
        
        # Mock scan_iter to return heartbeat keys
        async def mock_scan_iter(pattern):
            if pattern == "worker:heartbeat:*":
                yield "worker:heartbeat:worker-1"
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        health_service.redis_service.redis.get.return_value = old_heartbeat
        
        with patch.object(health_service, '_check_queue_activity', return_value=False):
            result = await health_service._check_workers_via_redis()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_queue_activity_with_active_tasks(self, health_service):
        """Test queue activity check with active tasks."""
        # Mock scan_iter to return task keys
        async def mock_scan_iter(pattern):
            if pattern == "task:*":
                yield "task:active-1"
                yield "task:pending-1"
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        
        # Mock task states
        def mock_hget(key, field):
            if field == "state":
                if key == "task:active-1":
                    return TaskState.ACTIVE.value
                elif key == "task:pending-1":
                    return TaskState.PENDING.value
            return None
        
        health_service.redis_service.redis.hget.side_effect = mock_hget
        
        result = await health_service._check_queue_activity()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_check_queue_activity_with_recent_completions(self, health_service):
        """Test queue activity check with recent completions."""
        import time
        current_time = time.time()
        recent_completion = datetime.fromtimestamp(current_time - 60).isoformat()  # 1 minute ago
        
        # Mock scan_iter to return task keys (no active tasks)
        async def mock_scan_iter(pattern):
            if pattern == "task:*":
                yield "task:completed-1"
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        
        # Mock task states and completion times
        def mock_hget(key, field):
            if field == "state":
                return TaskState.COMPLETED.value
            elif field == "completed_at":
                return recent_completion
            return None
        
        health_service.redis_service.redis.hget.side_effect = mock_hget
        
        result = await health_service._check_queue_activity()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_check_queue_activity_no_activity_with_pending(self, health_service):
        """Test queue activity check with pending tasks but no activity."""
        # Mock scan_iter to return no active tasks
        async def mock_scan_iter(pattern):
            return
            yield  # Make it an async generator
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        health_service.redis_service.redis.llen.return_value = 5  # Pending tasks exist
        
        result = await health_service._check_queue_activity()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_queue_activity_no_pending_tasks(self, health_service):
        """Test queue activity check with no pending tasks."""
        # Mock scan_iter to return no active tasks
        async def mock_scan_iter(pattern):
            return
            yield  # Make it an async generator
        
        health_service.redis_service.redis.scan_iter = mock_scan_iter
        health_service.redis_service.redis.llen.return_value = 0  # No pending tasks
        
        result = await health_service._check_queue_activity()
        
        assert result is True  # No work to do, so workers are assumed healthy

    @pytest.mark.asyncio
    async def test_check_queue_activity_exception(self, health_service):
        """Test queue activity check with exception."""
        health_service.redis_service.redis.scan_iter.side_effect = Exception("Redis error")
        
        result = await health_service._check_queue_activity()
        
        assert result is False
