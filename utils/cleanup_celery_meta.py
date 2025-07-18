#!/usr/bin/env python3
"""
Utility script to clean up existing celery-task-meta-* keys from Redis.

This script removes all Celery result backend keys since we've disabled
the result backend in favor of our custom task:{task_id} storage.
"""

import redis
import sys
from typing import List


def cleanup_celery_meta_keys(redis_url: str = "redis://localhost:6379/0") -> int:
    """
    Remove all celery-task-meta-* keys from Redis.
    
    Args:
        redis_url: Redis connection URL
        
    Returns:
        Number of keys deleted
    """
    try:
        # Connect to Redis
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        r.ping()
        print(f"Connected to Redis at {redis_url}")
        
        # Find all celery-task-meta-* keys
        pattern = "celery-task-meta-*"
        keys = list(r.scan_iter(match=pattern))
        
        if not keys:
            print("No celery-task-meta-* keys found.")
            return 0
        
        print(f"Found {len(keys)} celery-task-meta-* keys to delete.")
        
        # Delete keys in batches for efficiency
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            deleted = r.delete(*batch)
            deleted_count += deleted
            print(f"Deleted batch {i//batch_size + 1}: {deleted} keys")
        
        print(f"Successfully deleted {deleted_count} celery-task-meta-* keys.")
        return deleted_count
        
    except redis.RedisError as e:
        print(f"Redis error: {e}")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 0


def main():
    """Main function to run the cleanup."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean up celery-task-meta-* keys from Redis"
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis connection URL (default: redis://localhost:6379/0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        # Connect and count keys without deleting
        try:
            r = redis.from_url(args.redis_url, decode_responses=True)
            r.ping()
            keys = list(r.scan_iter(match="celery-task-meta-*"))
            print(f"DRY RUN: Would delete {len(keys)} celery-task-meta-* keys")
            if keys:
                print("Sample keys:")
                for key in keys[:5]:  # Show first 5 keys
                    print(f"  - {key}")
                if len(keys) > 5:
                    print(f"  ... and {len(keys) - 5} more")
        except Exception as e:
            print(f"Error during dry run: {e}")
            sys.exit(1)
    else:
        # Actually delete the keys
        deleted = cleanup_celery_meta_keys(args.redis_url)
        if deleted > 0:
            print(f"Cleanup completed successfully. Deleted {deleted} keys.")
        else:
            print("No keys were deleted.")


if __name__ == "__main__":
    main()
