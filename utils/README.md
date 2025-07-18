# AsyncTaskFlow Utilities

This directory contains utility scripts for maintaining and testing the AsyncTaskFlow system.

## Scripts

### `test_api_endpoints.py`

A comprehensive API endpoint testing utility that exercises all API endpoints and verifies they return expected status codes.

#### Features

- **Comprehensive Coverage**: Tests all 29 API endpoints including:
  - Root and health check endpoints
  - Task creation and management endpoints
  - Queue monitoring endpoints
  - Error condition handling
- **Smart Testing**: Creates real tasks and tests the full workflow
- **Flexible Output**: Supports quiet mode and detailed JSON output
- **Error Detection**: Returns non-zero exit code if any tests fail
- **Response Validation**: Checks both status codes and response content

#### Usage

```bash
# Basic usage - test all endpoints with verbose output
python3 utils/test_api_endpoints.py

# Quiet mode - only show summary
python3 utils/test_api_endpoints.py --quiet

# Save detailed results to JSON file
python3 utils/test_api_endpoints.py --save-results

# Test against different API URL
python3 utils/test_api_endpoints.py --url http://staging.example.com:8000

# Combine options
python3 utils/test_api_endpoints.py --quiet --save-results --url http://localhost:8000
```

#### Command Line Options

- `--url URL`: Base URL for the API (default: http://localhost:8000)
- `--save-results`: Save detailed test results to `api_test_results.json`
- `--quiet`: Only show summary, suppress individual test progress
- `--help`: Show help message

#### Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

#### Example Output

```
Test Summary:
Total endpoints tested: 29
Successful: 29
Failed: 0
Success rate: 100.0%

🎉 All tests passed!
```

#### What It Tests

**Root Endpoints:**
- `GET /` - Root endpoint

**Health Check Endpoints:**
- `GET /health` - Main health check
- `GET /ready` - Readiness check  
- `GET /live` - Liveness check
- `GET /health/workers` - Worker health details
- `POST /health/workers/reset-circuit-breaker` - Reset circuit breakers

**Task Management:**
- `POST /api/v1/tasks/summarize/` - Create summarization task
- `GET /api/v1/tasks/{task_id}` - Get task details
- `POST /api/v1/tasks/{task_id}/retry` - Retry failed task
- `DELETE /api/v1/tasks/{task_id}` - Delete task
- `GET /api/v1/tasks/?status=X` - List tasks by status
- `POST /api/v1/tasks/requeue-orphaned` - Requeue orphaned tasks

**Queue Monitoring:**
- `GET /api/v1/queues/status` - Queue status overview
- `GET /api/v1/queues/dlq` - Dead letter queue tasks
- `GET /api/v1/queues/{queue_name}/tasks` - Tasks in specific queue

**Error Conditions:**
- Invalid endpoints (404 expected)
- Invalid request data (422 expected)
- Invalid parameters (400 expected)

#### Integration with CI/CD

The script is designed to be used in automated testing pipelines:

```bash
# In your CI/CD pipeline
python3 utils/test_api_endpoints.py --quiet --save-results
if [ $? -ne 0 ]; then
    echo "API tests failed!"
    exit 1
fi
```

### `debug.py`

Debug utilities for development and troubleshooting.

#### Usage

```bash
python3 utils/debug.py
```

### `fix_stuck_tasks.py`

Utility for fixing stuck or orphaned tasks in the system.

### `reset_redis.py`

Utility for resetting Redis data during development.

#### Usage

```bash
# Inspect current state
python3 utils/reset_redis.py

# Reset with confirmation
python3 utils/reset_redis.py --confirm

# Or using Docker
docker compose run --rm reset --confirm
```

### `cleanup_celery_meta.py`

Utility for cleaning up Celery result backend keys (`celery-task-meta-*`) from Redis.

Since we've disabled Celery's result backend in favor of our custom `task:{task_id}` storage, this script removes any existing Celery result keys to free up Redis memory.

#### Usage

```bash
# Dry run - see what would be deleted
python3 utils/cleanup_celery_meta.py --dry-run

# Actually delete the keys
python3 utils/cleanup_celery_meta.py

# Use custom Redis URL
python3 utils/cleanup_celery_meta.py --redis-url redis://localhost:6379/1
```

#### Options

- `--redis-url URL`: Redis connection URL (default: redis://localhost:6379/0)
- `--dry-run`: Show what would be deleted without actually deleting
- `--help`: Show help message

#### When to Use

- After upgrading to the new task storage system
- When you notice many `celery-task-meta-*` keys in Redis
- As part of Redis maintenance to free up memory

## Dependencies

The utilities require:
- `httpx` (for API testing)
- `redis` (for Redis utilities)
- Standard library modules

Install dependencies:
```bash
# Using system Python
python3 -m pip install httpx redis --user

# Or using uv (if project build is working)
uv add --dev httpx redis
```

### `initialize_counters.py`

Utility to initialize Redis state counters for the new efficient counter system.

This script scans all existing tasks and creates Redis counters that match the current state distribution. Run this once when deploying the new counter-based queue monitoring system.

#### Usage

```bash
# Initialize counters based on existing tasks
python3 utils/initialize_counters.py
```

#### Features

- Scans all existing `task:*` keys in Redis
- Counts tasks by state (PENDING, ACTIVE, COMPLETED, FAILED, DLQ)
- Creates efficient Redis counters (`metrics:tasks:state:*`)
- Provides progress updates for large datasets
- Verifies counter accuracy after initialization

#### When to Use

- When first deploying the new counter system
- After data migrations or system upgrades
- When counters become out of sync with actual task states

### `test_realtime_updates.py`

Test utility for the real-time Server-Sent Events (SSE) queue monitoring system.

This script connects to the SSE endpoint and displays real-time updates as they occur, useful for testing the WebSocket-like functionality without a frontend.

#### Usage

```bash
# Connect to local API server
python3 utils/test_realtime_updates.py

# Make sure the API server is running on localhost:8000
```

#### Features

- Connects to `/api/v1/queues/status/stream` endpoint
- Displays real-time queue and task state updates
- Shows initial status, task creation, and state changes
- Handles heartbeat messages and error conditions
- Formatted output with timestamps

#### Example Output

```
[14:30:15] initial_status
  Initial Status:
    Queues: {'primary': 5, 'retry': 2, 'scheduled': 0, 'dlq': 1}
    States: {'PENDING': 7, 'ACTIVE': 1, 'COMPLETED': 45, 'FAILED': 0, 'DLQ': 1}
    Retry Ratio: 0.30

[14:30:22] task_created
  Task Created: 550e8400-e29b-41d4-a716-446655440000
    Queue Depths: {'primary': 6, 'retry': 2, 'scheduled': 0, 'dlq': 1}
    State Counts: {'PENDING': 8, 'ACTIVE': 1, 'COMPLETED': 45, 'FAILED': 0, 'DLQ': 1}

[14:30:25] task_state_changed
  Task: 550e8400-e29b-41d4-a716-446655440000
    State: PENDING → ACTIVE
    Queue Depths: {'primary': 5, 'retry': 2, 'scheduled': 0, 'dlq': 1}
    State Counts: {'PENDING': 7, 'ACTIVE': 2, 'COMPLETED': 45, 'FAILED': 0, 'DLQ': 1}
```

#### Dependencies

Requires `aiohttp` for async HTTP client functionality:

```bash
python3 -m pip install aiohttp --user
```

## Development

When adding new API endpoints, make sure to update `test_api_endpoints.py` to include tests for the new endpoints.

### Real-time System Testing

To test the complete real-time monitoring system:

1. **Start the API server:**
   ```bash
   docker compose up api
   ```

2. **Initialize counters (first time only):**
   ```bash
   python3 utils/initialize_counters.py
   ```

3. **Start the real-time monitor:**
   ```bash
   python3 utils/test_realtime_updates.py
   ```

4. **Create test tasks in another terminal:**
   ```bash
   python3 utils/test_api_endpoints.py
   ```

5. **Watch real-time updates** in the monitor terminal as tasks are created and processed.
