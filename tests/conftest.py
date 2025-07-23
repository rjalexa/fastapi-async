"""Pytest configuration and shared fixtures for AsyncTaskFlow."""

import asyncio
import pytest
from httpx import AsyncClient
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


@pytest.fixture(scope="session")
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
async def test_client(mock_redis):
    """Create a test client with overridden dependencies."""
    # Override the app's Redis dependency with our mock
    app.dependency_overrides[src.api.redis_config.get_redis] = lambda: mock_redis

    # Create and yield the test client
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up the override after the test
    app.dependency_overrides.clear()


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
