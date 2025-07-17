#!/usr/bin/env python3
"""Debug utilities for AsyncTaskFlow development."""

import asyncio
import json
import sys
from typing import Dict, Any

import redis
import httpx


async def check_redis_connection(redis_url: str = "redis://localhost:6379/0") -> Dict[str, Any]:
    """Check Redis connection and basic operations."""
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic operations
        r.ping()
        r.set("test_key", "test_value")
        value = r.get("test_key")
        r.delete("test_key")
        
        return {
            "status": "success",
            "message": "Redis connection successful",
            "test_value": value
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Redis connection failed: {str(e)}"
        }


async def check_api_health(api_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Check API health endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/health", timeout=10.0)
            
            return {
                "status": "success" if response.status_code == 200 else "error",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"API health check failed: {str(e)}"
        }


async def inspect_queues(redis_url: str = "redis://localhost:6379/0") -> Dict[str, Any]:
    """Inspect queue states and contents."""
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        
        queues = {
            "primary": r.llen("tasks:pending:primary"),
            "retry": r.llen("tasks:pending:retry"),
            "scheduled": r.zcard("tasks:scheduled"),
            "dlq": r.llen("dlq:tasks")
        }
        
        # Get sample tasks from each queue
        samples = {}
        if queues["primary"] > 0:
            samples["primary"] = r.lrange("tasks:pending:primary", 0, 4)
        if queues["retry"] > 0:
            samples["retry"] = r.lrange("tasks:pending:retry", 0, 4)
        if queues["dlq"] > 0:
            samples["dlq"] = r.lrange("dlq:tasks", 0, 4)
        
        return {
            "status": "success",
            "queue_lengths": queues,
            "samples": samples
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Queue inspection failed: {str(e)}"
        }


async def main():
    """Run all debug checks."""
    print("AsyncTaskFlow Debug Utility")
    print("=" * 40)
    
    # Check Redis
    print("\n1. Checking Redis connection...")
    redis_result = await check_redis_connection()
    print(json.dumps(redis_result, indent=2))
    
    # Check API
    print("\n2. Checking API health...")
    api_result = await check_api_health()
    print(json.dumps(api_result, indent=2))
    
    # Inspect queues
    print("\n3. Inspecting queues...")
    queue_result = await inspect_queues()
    print(json.dumps(queue_result, indent=2))
    
    print("\nDebug check complete.")


if __name__ == "__main__":
    asyncio.run(main())
