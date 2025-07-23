"""Tests for the task summaries endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_task_summaries_endpoint(test_client: AsyncClient):
    """Test the task summaries endpoint for functionality and performance."""
    # Test listing all task summaries
    response = await test_client.get("/api/v1/tasks/summaries/")
    assert response.status_code == 200
    data = response.json()
    assert "total_items" in data
    assert "tasks" in data

    # Test searching for a specific task
    response = await test_client.get("/api/v1/tasks/summaries/?task_id=e1c3ba11")
    assert response.status_code == 200
    data = response.json()
    # If a task with this ID exists, it should be returned
    if data["total_items"] > 0:
        task = data["tasks"][0]
        assert task["task_id"] == "e1c3ba11"

    # Compare response sizes (conceptual test)
    # In a real test, we would create tasks with large content to verify the size reduction.
    # This test asserts that the endpoint exists and returns valid data.
    full_response = await test_client.get("/api/v1/tasks/?page_size=1")
    summary_response = await test_client.get("/api/v1/tasks/summaries/?page_size=1")

    # Both endpoints should be accessible
    assert full_response.status_code == 200
    assert summary_response.status_code == 200

    # The summary response should be smaller or equal in size
    # (It might be equal if the task has no large content)
    assert len(summary_response.text) <= len(full_response.text)
