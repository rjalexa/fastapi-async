# src/api/config.py
"""Configuration settings for the API service."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Celery Configuration
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0"
    )

    # Task Processing Configuration
    default_retry_ratio: float = Field(default=0.3)
    max_retries: int = Field(default=3)
    max_task_age: int = Field(default=3600)  # 1 hour

    # Queue Pressure Thresholds
    retry_queue_warning: int = Field(default=1000)
    retry_queue_critical: int = Field(default=5000)

    # Circuit Breaker Configuration
    circuit_failure_threshold: float = Field(
        default=0.5
    )
    circuit_volume_threshold: int = Field(default=10)
    circuit_timeout: int = Field(default=60)

    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = Field(default=None)
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1"
    )
    openrouter_model: str = Field(
        default="meta-llama/llama-3.2-90b-text-preview"
    )
    openrouter_timeout: int = Field(default=30)

    # Development Configuration
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # API Configuration
    api_title: str = "AsyncTaskFlow API"
    api_description: str = "Production-ready distributed task processing system"
    api_version: str = "0.1.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_prefix": "",
    }


# Global settings instance
settings = Settings()
