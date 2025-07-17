"""Pytest configuration and shared fixtures."""

import pytest
import redis
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = MagicMock(spec=redis.Redis)
    mock.ping.return_value = True
    mock.hgetall.return_value = {}
    mock.hset.return_value = True
    mock.lpush.return_value = 1
    mock.lpop.return_value = None
    mock.llen.return_value = 0
    mock.zcard.return_value = 0
    mock.zadd.return_value = 1
    mock.zrem.return_value = 1
    mock.zrangebyscore.return_value = []
    return mock


@pytest.fixture
def mock_celery_app():
    """Mock Celery app for testing."""
    mock = MagicMock()
    mock.control.inspect.return_value.active_queues.return_value = {"worker1": []}
    return mock


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
            {
                "message": {
                    "content": "This is a test summary of the provided content."
                }
            }
        ]
    }
