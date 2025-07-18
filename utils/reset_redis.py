#!/usr/bin/env python3
"""Redis reset utility for AsyncTaskFlow development."""

import asyncio
import json
import os
from typing import Dict, Any

import redis


async def reset_redis_data(
    redis_url: str = "redis://localhost:6379/0",
    confirm: bool = False
) -> Dict[str, Any]:
    """Reset all Redis data by flushing the database."""
    try:
        r = redis.from_url(redis_url, decode_responses=True)

        # Test connection first
        r.ping()

        if not confirm:
            # Get current data stats before reset
            info = r.info()
            db_keys = info.get('db0', {}).get('keys', 0) if 'db0' in info else 0
            
            return {
                "status": "confirmation_required",
                "message": f"Redis contains {db_keys} keys. Use --confirm to proceed with reset.",
                "keys_count": db_keys,
                "redis_url": redis_url
            }

        # Get stats before reset
        info_before = r.info()
        db_keys_before = info_before.get('db0', {}).get('keys', 0) if 'db0' in info_before else 0

        # Perform the reset
        r.flushall()

        # Verify reset
        info_after = r.info()
        db_keys_after = info_after.get('db0', {}).get('keys', 0) if 'db0' in info_after else 0

        return {
            "status": "success",
            "message": "Redis data reset completed successfully",
            "keys_before": db_keys_before,
            "keys_after": db_keys_after,
            "redis_url": redis_url
        }

    except Exception as e:
        return {
            "status": "error", 
            "message": f"Redis reset failed: {str(e)}",
            "redis_url": redis_url
        }


async def inspect_before_reset(redis_url: str = "redis://localhost:6379/0") -> Dict[str, Any]:
    """Inspect current Redis state before reset."""
    try:
        r = redis.from_url(redis_url, decode_responses=True)

        # Get queue lengths
        queues = {
            "primary": r.llen("tasks:pending:primary"),
            "retry": r.llen("tasks:pending:retry"),
            "scheduled": r.zcard("tasks:scheduled"),
            "dlq": r.llen("dlq:tasks"),
        }

        # Count task metadata
        task_keys = list(r.scan_iter("task:*"))
        dlq_task_keys = list(r.scan_iter("dlq:task:*"))

        # Get all keys for overview
        all_keys = list(r.scan_iter())

        return {
            "status": "success",
            "total_keys": len(all_keys),
            "queue_lengths": queues,
            "task_metadata_count": len(task_keys),
            "dlq_task_metadata_count": len(dlq_task_keys),
            "sample_keys": all_keys[:10] if all_keys else []
        }

    except Exception as e:
        return {
            "status": "error", 
            "message": f"Redis inspection failed: {str(e)}"
        }


async def main():
    """Run Redis reset utility."""
    import sys
    
    # Get Redis URL from environment or use default
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Check for confirmation flag
    confirm = "--confirm" in sys.argv or "-y" in sys.argv
    
    print("AsyncTaskFlow Redis Reset Utility")
    print("=" * 40)
    print(f"Redis URL: {redis_url}")

    # Inspect current state
    print("\n1. Inspecting current Redis state...")
    inspection_result = await inspect_before_reset(redis_url)
    print(json.dumps(inspection_result, indent=2))

    # Perform reset
    print("\n2. Resetting Redis data...")
    reset_result = await reset_redis_data(redis_url, confirm=confirm)
    print(json.dumps(reset_result, indent=2))

    if reset_result["status"] == "confirmation_required":
        print("\nTo proceed with the reset, run:")
        print("  python utils/reset_redis.py --confirm")
        print("  # or")
        print("  docker compose run --rm reset --confirm")

    print("\nReset utility complete.")


if __name__ == "__main__":
    asyncio.run(main())
