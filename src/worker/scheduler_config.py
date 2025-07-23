# src/worker/scheduler_config.py
"""
Minimal configuration for the scheduler (celery beat).
This avoids importing pydantic and other heavy dependencies.
"""

import os

# Basic configuration without pydantic
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
