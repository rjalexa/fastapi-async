"""Pytest configuration and shared fixtures for AsyncTaskFlow."""

import asyncio
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch

# Import the FastAPI app instance
from src.api.main import app
from src.worker.main import app as celery_app

# Import settings from the correct location
from src.api.config import settings

# Import the real Redis client
import redis.asyncio as redis

# Import fakeredis for mocking
from fakeredis import aioredis


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def mock_redis():
    """Create a fakeredis instance for testing."""
    # Create a fakeredis server
    server = aioredis.FakeServer()
    # Create a Redis client connected to the fake server
    client = aioredis.FakeRedis(server=server)
    # Ensure the connection is ready
    await client.ping()
    return client


@pytest.fixture(scope="function")
def test_client(mock_redis):
    """Create a test client with mocked services."""
    from unittest.mock import AsyncMock, MagicMock, patch
    import src.api.services as services
    from src.api.services import RedisService, TaskService, QueueService, HealthService
    
    # Create mock services
    mock_redis_service = AsyncMock(spec=RedisService)
    mock_redis_service.redis = mock_redis
    mock_redis_service.ping.return_value = True
    mock_redis_service.get_pool_stats.return_value = {"status": "mocked"}
    
    mock_task_service = AsyncMock(spec=TaskService)
    mock_queue_service = AsyncMock(spec=QueueService)
    mock_health_service = AsyncMock(spec=HealthService)
    
    # Configure health service to return healthy status
    mock_health_service.check_health.return_value = {
        "status": "healthy",
        "components": {
            "redis": True,
            "workers": True
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    # Configure task service mock responses
    from src.api.schemas import TaskListResponse, QueueStatus, TaskDetail, TaskState, TaskType
    from datetime import datetime
    
    mock_task_service.create_task.return_value = "test-task-123"
    mock_task_service.list_tasks.return_value = TaskListResponse(
        tasks=[],
        total_items=0,
        page=1,
        page_size=20,
        total_pages=0
    )
    
    # Configure get_task to return a proper TaskDetail object
    mock_task_detail = TaskDetail(
        task_id="test-task-123",
        state=TaskState.PENDING,
        content="Test content",
        retry_count=0,
        max_retries=3,
        last_error=None,
        error_type=None,
        retry_after=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        completed_at=None,
        result=None,
        task_type=TaskType.SUMMARIZE,
        error_history=[],
        state_history=[]
    )
    mock_task_service.get_task.return_value = mock_task_detail
    
    # Configure queue service mock responses
    mock_queue_service.get_queue_status.return_value = QueueStatus(
        queues={"primary": 0, "retry": 0, "scheduled": 0, "dlq": 0},
        states={"PENDING": 0, "ACTIVE": 0, "COMPLETED": 0, "FAILED": 0},
        retry_ratio=0.3
    )
    mock_queue_service.get_dlq_tasks.return_value = []
    
    # Store original services
    original_redis = getattr(services, 'redis_service', None)
    original_task = getattr(services, 'task_service', None)
    original_queue = getattr(services, 'queue_service', None)
    original_health = getattr(services, 'health_service', None)
    
    # Set mock services before creating the test client
    services.redis_service = mock_redis_service
    services.task_service = mock_task_service
    services.queue_service = mock_queue_service
    services.health_service = mock_health_service
    
    # Mock the initialize_services function to prevent real service initialization
    with patch('src.api.main.initialize_services') as mock_init:
        mock_init.return_value = (mock_redis_service, mock_task_service, mock_queue_service, mock_health_service)
        
        # Also set in app state
        app.state.redis_service = mock_redis_service
        app.state.task_service = mock_task_service
        app.state.queue_service = mock_queue_service
        app.state.health_service = mock_health_service

        # Create and yield the test client
        with TestClient(app) as client:
            yield client

    # Restore original services
    services.redis_service = original_redis
    services.task_service = original_task
    services.queue_service = original_queue
    services.health_service = original_health


# The celery_app fixture is provided by celery[pytest]
# We can use it directly, but we'll also provide a worker fixture
@pytest.fixture(scope="session")
def celery_config():
    """Configure Celery for testing."""
    return {
        "broker_url": "memory://",
        "result_backend": "rpc://",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


@pytest.fixture(scope="session")
def celery_worker_parameters():
    """Configure Celery worker for testing."""
    return {
        "perform_ping_check": False,
        "ready_timeout": 10,
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        "task_id": "test-task-123",
        "content": "This is test content to summarize.",
        "state": "PENDING",
        "created_at": "2024-01-10T15:00:00Z",
        "retry_count": "0",
        "max_retries": "3",
    }


@pytest.fixture
def mock_openrouter_response():
    """Mock OpenRouter API response."""
    return {
        "choices": [
            {"message": {"content": "This is a test summary of the provided content."}}
        ]
    }
