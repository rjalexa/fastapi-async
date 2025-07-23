"""Comprehensive tests for all API endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(test_client: TestClient):
    """Test the root endpoint."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_endpoints(test_client: TestClient):
    """Test all health check endpoints."""
    # Test main health check
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    # Test readiness check
    response = test_client.get("/ready")
    assert response.status_code == 200

    # Test liveness check
    response = test_client.get("/live")
    assert response.status_code == 200


def test_task_creation_and_management(test_client: TestClient):
    """Test task creation, retrieval, and deletion."""
    # Test creating a summarization task
    task_data = {
        "content": "This is a test text for summarization. It should be processed by the worker system."
    }
    response = test_client.post("/api/v1/tasks/summarize/", json=task_data)
    assert response.status_code == 201
    response_data = response.json()
    assert "task_id" in response_data
    task_id = response_data["task_id"]

    # Test getting the created task
    response = test_client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["task_id"] == task_id

    # Test deleting the task
    response = test_client.delete(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200


def test_task_list_endpoints(test_client: TestClient):
    """Test listing tasks by status."""
    # Test listing pending tasks
    response = test_client.get("/api/v1/tasks/", params={"status": "PENDING", "limit": 10})
    assert response.status_code == 200

    # Test listing completed tasks
    response = test_client.get("/api/v1/tasks/", params={"status": "COMPLETED", "limit": 10})
    assert response.status_code == 200

    # Test listing failed tasks
    response = test_client.get("/api/v1/tasks/", params={"status": "FAILED", "limit": 10})
    assert response.status_code == 200

    # Test listing all tasks
    response = test_client.get("/api/v1/tasks/")
    assert response.status_code == 200


def test_queue_endpoints(test_client: TestClient):
    """Test queue monitoring endpoints."""
    # Test getting queue status
    response = test_client.get("/api/v1/queues/status")
    assert response.status_code == 200

    # Test getting DLQ tasks
    response = test_client.get("/api/v1/queues/dlq")
    assert response.status_code == 200


def test_openrouter_endpoints(test_client: TestClient):
    """Test OpenRouter monitoring endpoints."""
    # Test getting OpenRouter status
    response = test_client.get("/api/v1/openrouter/status")
    assert response.status_code == 200

    # Test getting OpenRouter metrics
    response = test_client.get("/api/v1/openrouter/metrics")
    assert response.status_code == 200


def test_redis_endpoints(test_client: TestClient):
    """Test Redis monitoring endpoints."""
    # Test getting Redis pool statistics
    response = test_client.get("/api/v1/redis/pool-stats")
    assert response.status_code == 200

    # Test getting Redis health
    response = test_client.get("/api/v1/redis/health")
    assert response.status_code == 200


def test_error_conditions(test_client: TestClient):
    """Test various error conditions."""
    # Test non-existent endpoint
    response = test_client.get("/api/v1/nonexistent")
    assert response.status_code == 404

    # Test invalid task creation payload
    response = test_client.post("/api/v1/tasks/summarize/", json={"invalid_field": "test"})
    assert response.status_code == 422

    # Test invalid queue name
    response = test_client.get("/api/v1/queues/invalid_queue/tasks")
    assert response.status_code == 422
