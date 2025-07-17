"""FastAPI application main module."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery

from config import settings
from routers import health, queues, tasks
from services import (
    HealthService,
    QueueService,
    RedisService,
    TaskService,
)

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "asynctaskflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AsyncTaskFlow API...")

    # Initialize services
    global redis_service, task_service, queue_service, health_service

    redis_service = RedisService(settings.redis_url)
    task_service = TaskService(redis_service)
    queue_service = QueueService(redis_service)
    health_service = HealthService(redis_service, celery_app)

    # Set celery app in tasks router
    tasks.celery_app = celery_app

    logger.info("Services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down AsyncTaskFlow API...")
    if redis_service:
        await redis_service.close()
    logger.info("Cleanup completed")


# Create FastAPI app
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(queues.router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs_url": settings.docs_url,
        "health_url": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
