#!/usr/bin/env python3
"""
Fix the active task counter in Redis metrics.

This script corrects the metrics:tasks:state:active counter to match
the actual number of active tasks in the system.
"""

import asyncio
import redis.asyncio as redis
from typing import Dict, List
import os
import sys

# Add the src directory to the path so we can import from the API
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'api'))

from config import settings


async def count_actual_active_tasks(redis_client: redis.Redis) -> int:
    """Count the actual number of tasks with ACTIVE state."""
    active_count = 0
    
    async for key in redis_client.scan_iter("task:*"):
        task_state = await redis_client.hget(key, "state")
        if task_state == "ACTIVE":
            active_count += 1
    
    return active_count


async def fix_active_counter():
    """Fix the active task counter in Redis metrics."""
    # Connect to Redis
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    
    try:
        # Test connection
        await redis_client.ping()
        print("✓ Connected to Redis")
        
        # Get current counter value
        current_counter = await redis_client.get("metrics:tasks:state:active")
        current_counter = int(current_counter) if current_counter else 0
        print(f"Current metrics counter: {current_counter}")
        
        # Count actual active tasks
        actual_active = await count_actual_active_tasks(redis_client)
        print(f"Actual active tasks: {actual_active}")
        
        if current_counter == actual_active:
            print("✓ Counter is already correct!")
            return
        
        # Fix the counter
        print(f"Fixing counter: {current_counter} → {actual_active}")
        await redis_client.set("metrics:tasks:state:active", actual_active)
        
        # Verify the fix
        new_counter = await redis_client.get("metrics:tasks:state:active")
        new_counter = int(new_counter) if new_counter else 0
        print(f"✓ Counter fixed: {new_counter}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await redis_client.close()
    
    return True


if __name__ == "__main__":
    print("Fixing active task counter...")
    success = asyncio.run(fix_active_counter())
    if success:
        print("✓ Active counter fixed successfully!")
    else:
        print("✗ Failed to fix active counter")
        sys.exit(1)
