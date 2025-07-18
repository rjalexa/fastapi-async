# AsyncTaskFlow API Service

A production-ready distributed task processing system built with FastAPI, Celery, and Redis. This service provides robust text summarization capabilities with advanced error handling, circuit breaker patterns, and comprehensive monitoring.

## Features

- **Asynchronous Task Processing**: Distributed task queue using Celery with Redis backend
- **Circuit Breaker Protection**: Built-in circuit breaker for external API calls
- **Advanced Retry Logic**: Intelligent retry scheduling with exponential backoff
- **Health Monitoring**: Comprehensive health checks for workers and system components
- **Real-time Monitoring**: Built-in API endpoints for comprehensive system monitoring
- **Production Ready**: Docker-based deployment with proper logging and error handling

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd asynctaskflow
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the services**
   ```bash
   docker compose up -d
   ```

4. **Access the services**
   - API Documentation: http://localhost:8000/docs
   - System Monitoring: http://localhost:8000/health
   - Frontend UI: http://localhost:3000

## Performance Management

The system provides extensive configuration options to optimize performance for different host capabilities and workload requirements.

### Resource Configuration

All performance settings are controlled through environment variables in your `.env` file:

#### Worker Scaling
```bash
# Number of worker containers to run
WORKER_REPLICAS=3

# Tasks processed concurrently per worker
CELERY_WORKER_CONCURRENCY=4

# Tasks prefetched per worker (1 = sequential, higher = parallel)
WORKER_PREFETCH_MULTIPLIER=1
```

#### Memory Management
```bash
# Container-level memory limits
WORKER_MEMORY_LIMIT=512M          # Maximum memory per worker container
WORKER_MEMORY_RESERVATION=256M    # Guaranteed memory per worker container

# Process-level memory limits
WORKER_MAX_MEMORY_PER_CHILD=200000 # Max memory per worker process (KB)
WORKER_MAX_TASKS_PER_CHILD=1000   # Tasks before worker process restart
```

#### CPU Management
```bash
# CPU limits per worker container
WORKER_CPU_LIMIT=1.0              # Maximum CPU cores (1.0 = 1 full core)
WORKER_CPU_RESERVATION=0.5        # Guaranteed CPU cores
```

#### Task Timeouts
```bash
# Task execution limits
CELERY_TASK_TIME_LIMIT=900        # Hard timeout (15 minutes)
CELERY_TASK_SOFT_TIME_LIMIT=600   # Soft warning (10 minutes)
OPENROUTER_TIMEOUT=120            # API call timeout (2 minutes)
```

### Performance Profiles

#### Development Environment (Low Resources)
```bash
# Minimal resource usage for development
WORKER_REPLICAS=1
CELERY_WORKER_CONCURRENCY=2
WORKER_MEMORY_LIMIT=256M
WORKER_MEMORY_RESERVATION=128M
WORKER_CPU_LIMIT=0.5
WORKER_CPU_RESERVATION=0.25
WORKER_PREFETCH_MULTIPLIER=1
```

#### Production Environment (Standard)
```bash
# Balanced configuration for production
WORKER_REPLICAS=3
CELERY_WORKER_CONCURRENCY=4
WORKER_MEMORY_LIMIT=512M
WORKER_MEMORY_RESERVATION=256M
WORKER_CPU_LIMIT=1.0
WORKER_CPU_RESERVATION=0.5
WORKER_PREFETCH_MULTIPLIER=1
```

#### High-Throughput Environment
```bash
# Optimized for high task volume
WORKER_REPLICAS=5
CELERY_WORKER_CONCURRENCY=8
WORKER_MEMORY_LIMIT=1G
WORKER_MEMORY_RESERVATION=512M
WORKER_CPU_LIMIT=2.0
WORKER_CPU_RESERVATION=1.0
WORKER_PREFETCH_MULTIPLIER=2
```

#### Memory-Constrained Environment
```bash
# Optimized for limited memory
WORKER_REPLICAS=2
CELERY_WORKER_CONCURRENCY=2
WORKER_MEMORY_LIMIT=256M
WORKER_MEMORY_RESERVATION=128M
WORKER_CPU_LIMIT=1.0
WORKER_CPU_RESERVATION=0.5
WORKER_MAX_MEMORY_PER_CHILD=100000
WORKER_MAX_TASKS_PER_CHILD=500
```

### Monitoring and Health Checks

Configure health check behavior for different environments:

```bash
# Health check intervals
WORKER_HEALTH_CHECK_INTERVAL=30s  # How often to check
WORKER_HEALTH_CHECK_TIMEOUT=10s   # Timeout per check
WORKER_HEALTH_CHECK_RETRIES=3     # Retries before marking unhealthy
WORKER_HEALTH_CHECK_START_PERIOD=60s # Grace period on startup

# Graceful shutdown
WORKER_STOP_GRACE_PERIOD=30s      # Time for graceful shutdown
```

### Performance Tuning Tips

1. **Worker Scaling**: Start with `WORKER_REPLICAS = CPU_CORES` and adjust based on task type
2. **Concurrency**: For I/O-bound tasks (API calls), use higher concurrency (4-8 per core)
3. **Memory**: Monitor actual usage and set limits 20-30% above peak usage
4. **Prefetch**: Use `WORKER_PREFETCH_MULTIPLIER=1` for long-running tasks to ensure fair distribution
5. **Task Limits**: Set `WORKER_MAX_TASKS_PER_CHILD` to prevent memory leaks in long-running workers

### Monitoring Performance

#### Check Worker Status
```bash
# View worker health and circuit breaker status
curl http://localhost:8000/health/workers

# Get detailed worker diagnostics
curl http://localhost:8000/health/workers/diagnostics
```

#### Monitor Resource Usage
```bash
# Check container resource usage
docker stats

# View worker logs
docker compose logs worker

# Monitor queue status
curl http://localhost:8000/api/v1/queues/status
```

#### Built-in Monitoring Dashboard
Access comprehensive monitoring through the API endpoints:
- Queue status and depths: `GET /api/v1/queues/status`
- Worker health and performance: `GET /health/workers`
- Dead letter queue analysis: `GET /api/v1/queues/dlq`
- Individual task details: `GET /api/v1/tasks/{task_id}`

### Troubleshooting Performance Issues

#### High Memory Usage
1. Reduce `CELERY_WORKER_CONCURRENCY`
2. Lower `WORKER_MAX_TASKS_PER_CHILD`
3. Decrease `WORKER_MEMORY_LIMIT` to force earlier container restarts

#### Slow Task Processing
1. Increase `WORKER_REPLICAS`
2. Increase `CELERY_WORKER_CONCURRENCY`
3. Check `OPENROUTER_TIMEOUT` for API bottlenecks

#### Container Crashes
1. Increase `WORKER_MEMORY_LIMIT`
2. Check logs for out-of-memory errors
3. Reduce `WORKER_MAX_MEMORY_PER_CHILD`

#### Circuit Breaker Activation
1. Check OpenRouter API status
2. Increase `OPENROUTER_TIMEOUT`
3. Reset circuit breakers: `curl -X POST http://localhost:8000/health/workers/reset-circuit-breaker`

## Architecture

### System Components

The system consists of several components:

- **FastAPI Application**: REST API for task management
- **Celery Workers**: Distributed task processors
- **Redis**: Message broker and result backend
- **Custom Queue Consumer**: Intelligent task distribution system
- **Circuit Breaker**: Protection against external service failures

### Task Flow Architecture

The system implements a sophisticated queue architecture that provides fine-grained control over task processing while maintaining scalability and fault tolerance. Here's how a task flows through the system:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Client Request │────▶│   FastAPI App   │────▶│  Redis Storage  │
│                 │     │   (REST API)    │     │ (Task Metadata) │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────┐               │
                        │                 │               │
                        │ Custom Redis    │◀──────────────┘
                        │ Queue (Primary) │
                        │                 │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐     ┌─────────────────┐
                        │                 │     │                 │
                        │ Queue Consumer  │────▶│ Celery Worker   │
                        │ (BLPOP Process) │     │ (Task Execution)│
                        │                 │     │                 │
                        └─────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────┐               │
                        │                 │               │
                        │ OpenRouter API  │◀──────────────┘
                        │ (LLM Backend)   │
                        │                 │
                        └─────────────────┘
```

#### Step-by-Step Task Flow

**1. Task Creation (API Layer)**
```http
POST /api/v1/tasks/summarize/
Content-Type: application/json
{"content": "Text to summarize"}
```
- FastAPI receives the HTTP request
- Creates task metadata in Redis: `task:{task_id}` with state "PENDING"
- Pushes task ID to `tasks:pending:primary` Redis list
- Returns task ID to client immediately
- **No direct Celery interaction** - API is completely decoupled

**2. Task Consumption (Consumer Layer)**
- Dedicated consumer process runs on each worker container
- Uses Redis `BLPOP` operation to atomically pull task IDs from queues
- Implements intelligent queue selection:
  - 70% from `tasks:pending:primary` (new tasks)
  - 30% from `tasks:pending:retry` (failed tasks)
- Ratio adapts based on retry queue pressure

**3. Task Dispatch (Consumer → Celery)**
- Consumer receives task ID from Redis queue
- Updates task state to "ACTIVE" in Redis
- Dispatches to local Celery worker: `celery_app.send_task("summarize_text", args=[task_id])`
- Consumer continues listening for more tasks

**4. Task Execution (Celery Worker)**
- Celery worker receives task from internal queue
- Loads task metadata from Redis using task ID
- Calls OpenRouter API with circuit breaker protection
- Handles retries, errors, and state management

**5. LLM Processing (OpenRouter API)**
- HTTP request to OpenRouter's chat completions endpoint
- Uses configured model (default: `meta-llama/llama-3.2-90b-text-preview`)
- Returns summarized text or error response

**6. Task Completion**
- On success: Updates task state to "COMPLETED" with result
- On failure: Schedules retry or moves to dead letter queue
- All state changes stored in Redis for API queries

#### Queue Management

The system maintains multiple specialized queues:

- **`tasks:pending:primary`**: New tasks from API
- **`tasks:pending:retry`**: Failed tasks eligible for retry  
- **`tasks:scheduled`**: Delayed retries (Redis sorted set)
- **`dlq:tasks`**: Permanently failed tasks

#### Monitoring Integration

**Built-in API Monitoring:**
```bash
# Queue status and depths
curl http://localhost:8000/api/v1/queues/status

# Worker health and performance
curl http://localhost:8000/health/workers

# Dead letter queue analysis
curl http://localhost:8000/api/v1/queues/dlq

# Individual task tracking
curl http://localhost:8000/api/v1/tasks/{task_id}
```

**Understanding Queue Status vs Task States:**

The `/api/v1/queues/status` endpoint returns two distinct types of information:

```json
{
  "queues": {
    "primary": 0,
    "retry": 0,
    "scheduled": 0,
    "dlq": 0
  },
  "states": {
    "COMPLETED": 10,
    "FAILED": 2
  },
  "retry_ratio": 0.3
}
```

- **`queues`**: Shows the number of task IDs currently waiting in Redis lists/sets for processing. These are tasks that need some action (processing, retrying, etc.). When tasks complete successfully, they are removed from all queues, so completed tasks don't appear here.

- **`states`**: Shows the count of all tasks by their current status, regardless of queue membership. This is calculated by scanning all `task:{task_id}` records in Redis and counting their `state` field values. Completed tasks remain in the system for result retrieval via the API.

This design separates "work to be done" (queues) from "historical record keeping" (task states), allowing you to monitor both active workload and overall system activity.

**Complete System Visibility:**
- Real-time queue monitoring shows tasks waiting in custom Redis queues
- Worker health endpoints provide performance metrics and circuit breaker status
- Task lifecycle tracking from creation to completion
- Comprehensive error analysis and retry management

#### Architecture Benefits

✅ **Horizontal Scalability**: Add workers and they automatically participate  
✅ **Fault Tolerance**: Atomic operations prevent task loss  
✅ **Queue Pressure Management**: Adaptive ratios prevent retry storms  
✅ **Clean Separation**: API, queuing, and execution are decoupled  
✅ **Sophisticated Retry Logic**: Primary/retry queue separation  
✅ **Production Monitoring**: Dual monitoring approach provides complete visibility

## API Endpoints

### Task Creation (Application-Specific)
- `POST /api/v1/tasks/summarize/` - Create a new text summarization task

### Task Management (Generic)
- `GET /api/v1/tasks/{task_id}` - Get task details and results (works for any task type)
- `POST /api/v1/tasks/{task_id}/retry` - Manually retry a failed task (works for any task type)
- `GET /api/v1/tasks/` - List tasks by status (works for any task type)
- `POST /api/v1/tasks/requeue-orphaned` - Requeue orphaned tasks (works for any task type)
- `DELETE /api/v1/tasks/{task_id}` - Delete a task (works for any task type)

### Monitoring
- `GET /health` - System health check
- `GET /health/workers` - Worker health and circuit breaker status
- `GET /api/v1/queues/status` - Queue status and metrics

### Queue Management
- `GET /api/v1/queues/dlq` - Dead letter queue contents
- `POST /health/workers/reset-circuit-breaker` - Reset worker circuit breakers

## Configuration

All configuration is managed through environment variables in the `.env` file. Key settings include:

- **Redis**: Connection URLs and configuration
- **OpenRouter**: API credentials and model settings
- **Worker Performance**: Scaling and resource limits
- **Circuit Breaker**: Failure thresholds and timeouts
- **Monitoring**: Health check intervals and logging

## Development

### Running Locally
```bash
# Start development environment
docker compose up -d

# View logs
docker compose logs -f

# Rebuild after changes
docker compose build && docker compose up -d
```

### System Reset

During development, you may need to completely reset the system state by clearing all Redis data (queues, task metadata, etc.):

```bash
# Reset Redis data using Docker Compose (recommended)
docker compose run --rm reset --confirm

# Or inspect current state first (without resetting)
docker compose run --rm reset

# Alternative: Run reset script directly (if Redis is accessible locally)
python utils/reset_redis.py --confirm
```

The reset utility will:
- Show current Redis state (queue lengths, task counts, etc.)
- Clear all Redis data using `FLUSHALL`
- Confirm the reset was successful

#### Safety Features

**✅ The reset service is completely safe and will NEVER run automatically:**

- **Docker Compose Profiles**: The reset service uses the `tools` profile, which excludes it from normal operations
- **Manual Only**: Only runs when explicitly requested with `docker compose run --rm reset`
- **Double Confirmation**: Requires `--confirm` flag to actually perform the reset
- **Inspection First**: Shows what will be deleted before proceeding

**Normal operations are completely safe:**
```bash
# These commands will NOT run the reset service
docker compose up -d          # Starts: redis, api, worker, scheduler, frontend
docker compose up             # Same as above  
docker compose restart        # Restarts services, no reset
docker compose down           # Stops services, no reset
```

**Reset only happens when explicitly requested:**
```bash
# Only these commands will run the reset service
docker compose run --rm reset                    # Inspect only (safe)
docker compose run --rm reset --confirm          # Actually reset (destructive)
```

**⚠️ Warning**: The reset operation will permanently delete all tasks, queue data, and system state. Only use during development.

### Viewing Redis Data

You can inspect your Redis data using a Redis viewer (like the Redis for VS Code extension). When the system is active, you should see these key structures:

**Queue Keys (Lists/Sets):**
- `tasks:pending:primary` - New tasks waiting to be processed
- `tasks:pending:retry` - Failed tasks waiting for retry
- `tasks:scheduled` - Tasks scheduled for delayed retry (sorted set)
- `dlq:tasks` - Dead letter queue for permanently failed tasks

**Task Metadata (Hashes):**
- `task:{uuid}` - Individual task data and state
- `dlq:task:{uuid}` - Dead letter queue task metadata

**Worker Data:**
- `worker:heartbeat:{worker-id}` - Worker health heartbeats
- `_kombu.binding.*` - Celery internal queues

**Note**: Redis automatically removes empty lists and sets to save memory. If you don't see the queue keys, it means they're currently empty. Create some tasks to see them appear:

```bash
# Create a test task to populate queues
curl -X POST http://localhost:8000/api/v1/tasks/summarize/ \
  -H "Content-Type: application/json" \
  -d '{"content": "This is a test document to summarize."}'

# Check queue status via API
curl http://localhost:8000/api/v1/queues/status
```

### Testing
```bash
# Run tests (when available)
docker compose exec api python -m pytest

# Manual API testing
curl -X POST http://localhost:8000/api/v1/tasks/summarize/ \
  -H "Content-Type: application/json" \
  -d '{"content": "This is a test document to summarize."}'
```

## Production Deployment

1. **Environment Setup**: Configure production values in `.env`
2. **Resource Planning**: Set appropriate worker counts and resource limits
3. **Monitoring**: Set up log aggregation and alerting
4. **Backup**: Configure Redis persistence if needed
5. **Security**: Configure proper network security and API authentication

## License

[Add your license information here]
