#!/usr/bin/env python3
"""
Clean up existing metrics keys from Redis.

This script removes all metrics:tasks:state:* keys from Redis
as part of removing the metrics counter system.
"""

import asyncio
import os

import redis.asyncio as aioredis


async def cleanup_metrics():
    """Remove all metrics keys from Redis."""
    # Use default Redis URL or get from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = aioredis.from_url(redis_url, decode_responses=True)

    try:
        print("🧹 Cleaning up metrics keys from Redis...")

        # Find all metrics keys
        metrics_keys = []
        async for key in redis_conn.scan_iter("metrics:tasks:state:*"):
            metrics_keys.append(key)

        if not metrics_keys:
            print("✅ No metrics keys found - already clean!")
            return

        print(f"Found {len(metrics_keys)} metrics keys:")
        for key in metrics_keys:
            value = await redis_conn.get(key)
            print(f"  - {key}: {value}")

        # Delete all metrics keys
        if metrics_keys:
            deleted_count = await redis_conn.delete(*metrics_keys)
            print(f"✅ Deleted {deleted_count} metrics keys")

        print("🎉 Metrics cleanup completed!")

    except Exception as e:
        print(f"❌ Error cleaning up metrics: {e}")
        raise
    finally:
        await redis_conn.aclose()


if __name__ == "__main__":
    asyncio.run(cleanup_metrics())
