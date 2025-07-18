# src/api/config.py
"""Configuration settings for the API service."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

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

    # API Configuration
    api_title: str = "AsyncTaskFlow API"
    api_description: str = "Production-ready distributed task processing system"
    api_version: str = "0.1.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
