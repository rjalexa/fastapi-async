#!/usr/bin/env python3
"""
Utility script to identify and delete defective tasks from Redis.

This script finds and removes tasks with:
- task_id = "unknown_id"
- Invalid timestamps (datetime.min or year 1)
- Any other data corruption indicators

Usage:
    python utils/delete_defective_tasks.py --dry-run  # Preview what would be deleted
    python utils/delete_defective_tasks.py           # Actually delete the tasks
"""

import redis
from datetime import datetime
from typing import List, Dict, Any


def is_defective_task(task_data: Dict[str, str]) -> bool:
    """
    Check if a task is defective based on known corruption patterns.

    Args:
        task_data: Task data from Redis hash

    Returns:
        True if task is defective and should be deleted
    """
    # Check for unknown_id
    if task_data.get("task_id") == "unknown_id":
        return True

    # Check for invalid timestamps
    for date_field in ["created_at", "updated_at", "completed_at"]:
        date_str = task_data.get(date_field)
        if date_str:
            try:
                parsed_date = datetime.fromisoformat(date_str)
                # Check if year is 1 (datetime.min) or other invalid dates
                if parsed_date.year == 1:
                    return True
            except (ValueError, TypeError):
                # Invalid date format is also defective
                return True

    # Check for missing required fields
    required_fields = ["task_id", "state", "created_at"]
    for field in required_fields:
        if not task_data.get(field):
            return True

    return False


def find_defective_tasks(
    redis_url: str = "redis://localhost:6379/0",
) -> List[Dict[str, Any]]:
    """
    Find all defective tasks in Redis.

    Args:
        redis_url: Redis connection URL

    Returns:
        List of defective task information
    """
    defective_tasks = []

    try:
        # Connect to Redis
        r = redis.from_url(redis_url, decode_responses=True)
        r.ping()
        print(f"Connected to Redis at {redis_url}")

        # Scan all task keys
        task_count = 0
        for key in r.scan_iter("task:*"):
            task_count += 1
            task_data = r.hgetall(key)

            if is_defective_task(task_data):
                defective_info = {
                    "redis_key": key,
                    "task_id": task_data.get("task_id", "missing"),
                    "state": task_data.get("state", "missing"),
                    "created_at": task_data.get("created_at", "missing"),
                    "updated_at": task_data.get("updated_at", "missing"),
                    "completed_at": task_data.get("completed_at", "missing"),
                    "task_type": task_data.get("task_type", "missing"),
                    "content_preview": task_data.get("content", "")[:100] + "..."
                    if task_data.get("content", "")
                    else "missing",
                }
                defective_tasks.append(defective_info)

        print(f"Scanned {task_count} total tasks")
        print(f"Found {len(defective_tasks)} defective tasks")

        return defective_tasks

    except redis.RedisError as e:
        print(f"Redis error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


def delete_defective_tasks(
    redis_url: str = "redis://localhost:6379/0", dry_run: bool = False
) -> int:
    """
    Delete defective tasks from Redis.

    Args:
        redis_url: Redis connection URL
        dry_run: If True, only show what would be deleted

    Returns:
        Number of tasks deleted (or would be deleted in dry run)
    """
    defective_tasks = find_defective_tasks(redis_url)

    if not defective_tasks:
        print("No defective tasks found.")
        return 0

    print("\nDefective tasks found:")
    print("-" * 80)
    for i, task in enumerate(defective_tasks, 1):
        print(f"{i}. Redis Key: {task['redis_key']}")
        print(f"   Task ID: {task['task_id']}")
        print(f"   State: {task['state']}")
        print(f"   Created: {task['created_at']}")
        print(f"   Updated: {task['updated_at']}")
        print(f"   Completed: {task['completed_at']}")
        print(f"   Type: {task['task_type']}")
        print(f"   Content: {task['content_preview']}")
        print()

    if dry_run:
        print(f"DRY RUN: Would delete {len(defective_tasks)} defective tasks")
        return len(defective_tasks)

    # Confirm deletion
    response = input(
        f"Are you sure you want to delete {len(defective_tasks)} defective tasks? (yes/no): "
    )
    if response.lower() != "yes":
        print("Deletion cancelled.")
        return 0

    # Actually delete the tasks
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        deleted_count = 0

        for task in defective_tasks:
            redis_key = task["redis_key"]
            task_id = task["task_id"]

            # Use Redis transaction to ensure atomicity
            with r.pipeline(transaction=True) as pipe:
                # Delete the main task hash
                pipe.delete(redis_key)

                # Delete any corresponding dead-letter queue hash
                pipe.delete(f"dlq:task:{task_id}")

                # Remove the task_id from all potential queues
                # (Note: for unknown_id tasks, this might not remove anything, but it's safe)
                pipe.lrem("queue:primary", 0, task_id)
                pipe.lrem("queue:retry", 0, task_id)
                pipe.lrem("queue:dlq", 0, task_id)

                # Remove from scheduled queue (sorted set)
                pipe.zrem("queue:scheduled", task_id)

                pipe.execute()

            deleted_count += 1
            print(f"Deleted task: {redis_key}")

        print(f"Successfully deleted {deleted_count} defective tasks.")
        return deleted_count

    except redis.RedisError as e:
        print(f"Redis error during deletion: {e}")
        return 0
    except Exception as e:
        print(f"Unexpected error during deletion: {e}")
        return 0


def main():
    """Main function to run the defective task cleanup."""
    import argparse

    parser = argparse.ArgumentParser(description="Delete defective tasks from Redis")
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis connection URL (default: redis://localhost:6379/0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    print("Defective Task Cleanup Utility")
    print("=" * 40)
    print(f"Redis URL: {args.redis_url}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'DELETE'}")
    print()

    deleted_count = delete_defective_tasks(args.redis_url, args.dry_run)

    if args.dry_run:
        print(f"\nDry run completed. {deleted_count} defective tasks would be deleted.")
        print("Run without --dry-run to actually delete them.")
    else:
        if deleted_count > 0:
            print(
                f"\nCleanup completed successfully. Deleted {deleted_count} defective tasks."
            )
        else:
            print("\nNo defective tasks were deleted.")


if __name__ == "__main__":
    main()
