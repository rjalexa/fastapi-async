# src/api/main.py
"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import settings
from src.api.routers import (
    health,
    tasks,
    queues,
    summarize,
    workers,
    pdfxtract,
    redis,
    openrouter,
)
from src.api.services import RedisService, TaskService, QueueService, HealthService
import src.api.services as services  # Import the module to modify globals


# Create Celery app for worker communication (broadcast commands)
from celery import Celery

celery_app = Celery(
    "asynctaskflow-api",
    broker=settings.celery_broker_url,
    backend=None,  # No result backend needed for API
)

# Configure Celery for API (minimal config for worker communication)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
)


async def initialize_services() -> tuple[RedisService, TaskService, QueueService, HealthService]:
    """Initialize all services and return them."""
    print(f"Initializing services in process {os.getpid()}")

    # Initialize Redis service with optimized connection pool
    redis_service = RedisService(settings.redis_url)
    await redis_service.initialize()

    # Test Redis connection
    redis_ok = await redis_service.ping()
    print(f"Redis connection: {'OK' if redis_ok else 'FAILED'}")

    if redis_ok:
        # Log connection pool stats
        pool_stats = await redis_service.get_pool_stats()
        print(f"Redis pool initialized: {pool_stats}")
    else:
        print("⚠️  Redis connection failed, but continuing...")

    # Initialize other services
    task_service = TaskService(redis_service)
    queue_service = QueueService(redis_service)
    health_service = HealthService(redis_service, celery_app)

    return redis_service, task_service, queue_service, health_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    print("🚀 Starting AsyncTaskFlow API...")
    print(f"Redis URL: {settings.redis_url}")
    print(f"Debug mode: {settings.debug}")

    try:
        # Initialize services
        redis_svc, task_svc, queue_svc, health_svc = await initialize_services()

        # Set global variables
        services.redis_service = redis_svc
        services.task_service = task_svc
        services.queue_service = queue_svc
        services.health_service = health_svc

        # Also store in app state (fallback for reload mode)
        app.state.redis_service = redis_svc
        app.state.task_service = task_svc
        app.state.queue_service = queue_svc
        app.state.health_service = health_svc

        print("✅ All services initialized successfully")

    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        # Don't raise - let the app start but mark services as unavailable
        services.redis_service = None
        services.task_service = None
        services.queue_service = None
        services.health_service = None

    yield

    # Shutdown
    print("🧹 Cleaning up services...")
    if services.redis_service:
        await services.redis_service.close()
    print("✅ Services cleaned up")


# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set Celery app in task routers
tasks.celery_app = celery_app
summarize.celery_app = celery_app

# Include routers
app.include_router(summarize.router)  # Application endpoints first
app.include_router(pdfxtract.router)  # PDF extraction endpoints
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(queues.router)
app.include_router(workers.router)
app.include_router(redis.router)  # Redis monitoring endpoints
app.include_router(openrouter.router)  # OpenRouter monitoring endpoints


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "AsyncTaskFlow API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
