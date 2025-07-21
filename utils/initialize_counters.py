#!/usr/bin/env python3
"""
Initialize Redis counters for task states.

This script scans all existing tasks and initializes the state counters
to match the current state of the system. Run this once when deploying
the new counter system.
"""

import asyncio
import os
import sys
from collections import defaultdict

import redis.asyncio as aioredis

# Add the src directory to the path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "api"))

from config import settings


async def initialize_counters():
    """Initialize state counters based on existing tasks."""
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        print("Scanning existing tasks to initialize counters...")

        # Count tasks by state
        state_counts = defaultdict(int)
        task_count = 0

        async for key in redis_conn.scan_iter("task:*"):
            task_count += 1
            state = await redis_conn.hget(key, "state")
            if state:
                state_counts[state.lower()] += 1

            if task_count % 1000 == 0:
                print(f"Processed {task_count} tasks...")

        print(f"\nFound {task_count} total tasks:")
        for state, count in state_counts.items():
            print(f"  {state.upper()}: {count}")

        # Initialize counters
        print("\nInitializing Redis counters...")
        async with redis_conn.pipeline(transaction=True) as pipe:
            # Clear existing counters first
            for state in [
                "pending",
                "active",
                "completed",
                "failed",
                "scheduled",
                "dlq",
            ]:
                await pipe.delete(f"metrics:tasks:state:{state}")

            # Set new counter values
            for state, count in state_counts.items():
                if count > 0:
                    await pipe.set(f"metrics:tasks:state:{state}", count)

            await pipe.execute()

        print("Counters initialized successfully!")

        # Verify counters
        print("\nVerifying counters:")
        for state in ["pending", "active", "completed", "failed", "scheduled", "dlq"]:
            count = await redis_conn.get(f"metrics:tasks:state:{state}")
            count = int(count) if count else 0
            print(f"  {state.upper()}: {count}")

    except Exception as e:
        print(f"Error initializing counters: {e}")
        raise
    finally:
        await redis_conn.close()


if __name__ == "__main__":
    asyncio.run(initialize_counters())
