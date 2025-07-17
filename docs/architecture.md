# AsyncTaskFlow Architecture

This document describes the high-level architecture of the AsyncTaskFlow system.

## System Overview

AsyncTaskFlow is a production-ready distributed task processing system built with FastAPI, Redis, and Celery. It implements a robust architecture for handling long-running text summarization tasks via OpenRouter API.

## Components

### API Service (`src/api/`)
- FastAPI application serving REST endpoints
- Task management and queue monitoring
- Health checks and system status

### Worker Service (`src/worker/`)
- Celery workers for task execution
- Circuit breaker pattern implementation
- Retry logic and error handling

### Frontend (`frontend/`)
- React/TypeScript web interface
- Real-time task monitoring
- Queue management dashboard

### Infrastructure
- Redis for message brokering and caching
- Docker containers for all services
- Nginx for frontend serving and API proxying

## Data Flow

1. User submits task via frontend
2. API creates task record in Redis
3. Task queued for worker processing
4. Worker executes task with retry logic
5. Results stored and status updated
6. Frontend displays real-time progress

## Key Features

- Dual-queue system (primary/retry)
- Circuit breaker protection
- Dead letter queue management
- Exponential backoff retry strategy
- Comprehensive monitoring and health checks

For detailed implementation information, see the project specification in `.clinerules/project-definition.md`.
