#!/usr/bin/env python3
"""
Script to manually trigger Celery tasks for stuck task IDs in Redis.
This fixes the issue where tasks were queued in Redis lists but never sent to Celery.
"""

import redis
from celery import Celery
import os

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


def main():
    # Connect to Redis
    r = redis.from_url(REDIS_URL, decode_responses=True)

    # Create Celery app (matching API configuration)
    celery_app = Celery(
        "fix-stuck-tasks",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_routes={
            "summarize_text": {"queue": "celery"},
        },
    )

    # Get all task IDs from primary queue
    task_ids = r.lrange("tasks:pending:primary", 0, -1)
    print(f"Found {len(task_ids)} tasks in primary queue")

    processed_count = 0
    for task_id in task_ids:
        # Check if task exists in Redis
        task_data = r.hgetall(f"task:{task_id}")
        if not task_data:
            print(f"⚠️  Task {task_id} not found in Redis, skipping")
            continue

        # Check if task is still PENDING
        if task_data.get("state") != "PENDING":
            print(
                f"✅ Task {task_id} already processed (state: {task_data.get('state')})"
            )
            continue

        print(f"🔄 Triggering Celery task for {task_id}")

        try:
            # Send task to Celery
            celery_app.send_task("summarize_text", args=[task_id])
            processed_count += 1
            print(f"✅ Sent task {task_id} to Celery")
        except Exception as e:
            print(f"❌ Failed to send task {task_id}: {e}")

    print(f"\n🎉 Successfully triggered {processed_count} Celery tasks")
    print("Tasks should now be processed by workers")


if __name__ == "__main__":
    main()
