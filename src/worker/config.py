# src/worker/config.py
"""Configuration settings for the worker service."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Worker application settings."""

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # Celery Configuration
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0", env="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND"
    )

    # Task Processing Configuration
    default_retry_ratio: float = Field(default=0.3, env="DEFAULT_RETRY_RATIO")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    max_task_age: int = Field(default=3600, env="MAX_TASK_AGE")  # 1 hour

    # Queue Pressure Thresholds
    retry_queue_warning: int = Field(default=1000, env="RETRY_QUEUE_WARNING")
    retry_queue_critical: int = Field(default=5000, env="RETRY_QUEUE_CRITICAL")

    # Circuit Breaker Configuration
    circuit_failure_threshold: float = Field(
        default=0.5, env="CIRCUIT_FAILURE_THRESHOLD"
    )
    circuit_volume_threshold: int = Field(default=10, env="CIRCUIT_VOLUME_THRESHOLD")
    circuit_timeout: int = Field(default=60, env="CIRCUIT_TIMEOUT")

    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL"
    )
    openrouter_model: str = Field(
        default="meta-llama/llama-3.2-90b-text-preview", env="OPENROUTER_MODEL"
    )
    openrouter_timeout: int = Field(default=30, env="OPENROUTER_TIMEOUT")

    # Development Configuration
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Worker Configuration
    worker_concurrency: int = Field(default=4, env="WORKER_CONCURRENCY")
    worker_prefetch_multiplier: int = Field(default=1, env="WORKER_PREFETCH_MULTIPLIER")
    task_soft_time_limit: int = Field(
        default=300, env="TASK_SOFT_TIME_LIMIT"
    )  # 5 minutes
    task_time_limit: int = Field(default=600, env="TASK_TIME_LIMIT")  # 10 minutes

    # Celery Monitoring Configuration (for Flower)
    celery_worker_send_task_events: bool = Field(
        default=True, env="CELERY_WORKER_SEND_TASK_EVENTS"
    )
    celery_task_send_sent_event: bool = Field(
        default=True, env="CELERY_TASK_SEND_SENT_EVENT"
    )
    celery_worker_disable_rate_limits: bool = Field(
        default=True, env="CELERY_WORKER_DISABLE_RATE_LIMITS"
    )
    celery_task_track_started: bool = Field(
        default=True, env="CELERY_TASK_TRACK_STARTED"
    )
    celery_task_time_limit: int = Field(default=600, env="CELERY_TASK_TIME_LIMIT")
    celery_task_soft_time_limit: int = Field(
        default=300, env="CELERY_TASK_SOFT_TIME_LIMIT"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
