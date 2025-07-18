# src/worker/main.py
"""Celery application main module."""

import logging

from celery import Celery

from config import settings
from tasks import process_scheduled_tasks, summarize_task

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
logger = logging.getLogger(__name__)

# Create Celery app - disable result backend to avoid celery-task-meta-* keys
app = Celery(
    "asynctaskflow-worker",
    broker=settings.celery_broker_url,
    backend=None,  # Disable result backend - we use custom task:{task_id} storage
)

# Configure Celery
app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Worker settings
    worker_concurrency=settings.worker_concurrency,
    worker_prefetch_multiplier=settings.worker_prefetch_multiplier,
    task_soft_time_limit=settings.task_soft_time_limit,
    task_time_limit=settings.task_time_limit,
    # Disable result backend completely
    task_ignore_result=True,
    # Task routing
    task_routes={
        "summarize_text": {"queue": "default"},
        "process_scheduled_tasks": {"queue": "scheduler"},
    },
    # Beat schedule for periodic tasks
    beat_schedule={
        "process-scheduled-tasks": {
            "task": "process_scheduled_tasks",
            "schedule": 1.0,  # Every second
        },
    },
)

if __name__ == "__main__":
    app.start()
