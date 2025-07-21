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

### `fix_counter_sync.py`

**NEW**: Utility to detect and fix Redis counter synchronization issues.

This script analyzes the current state of all tasks in Redis and compares it with the state counters, then fixes any discrepancies. This is essential for maintaining accurate queue statistics and resolving "phantom" active tasks.

#### Usage

```bash
# Analyze and fix counter synchronization issues
python3 utils/fix_counter_sync.py

# Use custom Redis URL
python3 utils/fix_counter_sync.py redis://localhost:6379/1
```

#### Features

- **Comprehensive Analysis**: Scans all `task:*` keys and counts actual states
- **Counter Comparison**: Compares actual counts with Redis state counters
- **Automatic Fixing**: Updates counters to match actual task states
- **Detailed Reporting**: Shows before/after values and changes made
- **Safe Operation**: Uses atomic Redis transactions for consistency

#### Example Output

```
🔍 Analyzing Redis task state counters...

📊 Analysis Results:
   Total tasks found: 28

📈 Counter Values:
   State        Old    New    Change
   ------------ ------ ------ --------
   PENDING      0      0      0
   ACTIVE       1      0      -1
   COMPLETED    28     28     0
   FAILED       0      0      0
   SCHEDULED    0      0      0
   DLQ          0      0      0

✅ Fixed 1 counter discrepancies:
   - ACTIVE: -1
```

#### When to Use

- **Phantom Active Tasks**: When dashboard shows active tasks but none exist
- **Counter Drift**: When state counters don't match actual task counts
- **After System Issues**: Following worker crashes or Redis connection problems
- **Regular Maintenance**: Periodic verification of counter accuracy
- **Troubleshooting**: When queue statistics seem incorrect

#### Common Issues This Fixes

1. **Stuck Active Counter**: Tasks marked as ACTIVE but actually completed
2. **Missing State Transitions**: Counters not updated during state changes
3. **Worker Crash Recovery**: Counters left inconsistent after worker failures
4. **Manual Task Manipulation**: Counters out of sync after direct Redis operations

#### Integration with Monitoring

This utility can be integrated into monitoring systems:

```bash
# Check for counter issues and alert if found
python3 utils/fix_counter_sync.py | grep "Fixed.*discrepancies" && echo "Counter sync issues detected and fixed"
```

### `inject_test_tasks.py`

**NEW**: Task injection utility specifically designed for testing frontend reactions to multiple task creation and processing.

This script creates exactly 10 tasks (or any specified number) with realistic content and monitors their progress, making it perfect for testing how the frontend dashboard reacts to task creation, queue changes, and real-time updates.

#### Usage

```bash
# Basic usage - inject 10 tasks with 0.5s delay between each
python3 utils/inject_test_tasks.py

# Inject 20 tasks with 1 second delay
python3 utils/inject_test_tasks.py --count 20 --delay 1.0

# Inject tasks and monitor progress for 30 seconds
python3 utils/inject_test_tasks.py --monitor 30

# Show queue status before and after injection
python3 utils/inject_test_tasks.py --show-queue-status

# Clean up created tasks automatically
python3 utils/inject_test_tasks.py --cleanup

# Combine options for comprehensive testing
python3 utils/inject_test_tasks.py --count 15 --delay 0.3 --monitor 45 --show-queue-status --cleanup
```

#### Command Line Options

- `--count N`: Number of tasks to create (default: 10)
- `--delay N`: Delay between task creation in seconds (default: 0.5)
- `--url URL`: Base URL for the API (default: http://localhost:8000)
- `--monitor N`: Monitor task progress for N seconds after creation
- `--cleanup`: Clean up created tasks after completion
- `--show-queue-status`: Show queue status before and after injection

#### Features

- **Realistic Test Data**: Uses 10 different realistic content samples that rotate
- **Progress Tracking**: Shows task creation progress with success/failure indicators
- **Queue Monitoring**: Optional queue status display before/after injection
- **Task Progress Monitoring**: Optional monitoring of task state changes over time
- **Automatic Cleanup**: Optional cleanup of created tasks
- **Frontend Testing Focus**: Designed specifically to test frontend reactions
- **Flexible Timing**: Configurable delays between task creation
- **Error Handling**: Comprehensive error reporting and recovery

#### Perfect for Testing

- **Dashboard Responsiveness**: See how the dashboard reacts to multiple tasks
- **Real-time Updates**: Test SSE/WebSocket functionality with actual task flow
- **Queue Visualization**: Verify queue depth changes are reflected in UI
- **Task State Transitions**: Monitor how frontend shows PENDING → ACTIVE → COMPLETED
- **Performance**: Test frontend performance with multiple simultaneous tasks

#### Example Output

```
AsyncTaskFlow Task Injection Utility
Target: http://localhost:8000
Tasks to create: 10
Delay between tasks: 0.5s

Injecting 10 test tasks...
Delay between tasks: 0.5s
Batch size: 1
Target API: http://localhost:8000
Creating task 1/10...
  ✅ Task 1 created: 550e8400-e29b-41d4-a716-446655440000
Creating task 2/10...
  ✅ Task 2 created: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
...

TASK INJECTION SUMMARY
Total tasks attempted: 10
Successfully created: 10
Failed: 0
Success rate: 100.0%

Created Task IDs:
  Task 1: 550e8400-e29b-41d4-a716-446655440000
  Task 2: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
  ...

🎉 All 10 tasks created successfully!
💡 Use --cleanup flag to automatically delete created tasks
```

### `gen_10_summaries_multilingual.py`

**NEW**: Multilingual fake news summarization task generator that creates and submits 10 diverse summarization tasks for testing multilingual content processing.

This script generates 5 Italian fake news articles (~300 words each) and 5 articles in other widespread languages (Spanish, French, German, Portuguese, English), then submits them all as summarization tasks to test the system's multilingual capabilities.

#### Usage

```bash
# Basic usage - generate and submit all 10 tasks
python3 utils/gen_10_summaries_multilingual.py

# Custom delay between submissions
python3 utils/gen_10_summaries_multilingual.py --delay 1.0

# Show queue status before and after
python3 utils/gen_10_summaries_multilingual.py --show-queue-status

# Monitor task progress for 60 seconds after creation
python3 utils/gen_10_summaries_multilingual.py --monitor 60

# Target different API URL
python3 utils/gen_10_summaries_multilingual.py --url http://staging.example.com:8000

# Combine all options
python3 utils/gen_10_summaries_multilingual.py --delay 0.5 --show-queue-status --monitor 30
```

#### Command Line Options

- `--delay N`: Delay between task submissions in seconds (default: 1.0)
- `--url URL`: Base URL for the API (default: http://localhost:8000)
- `--monitor N`: Monitor task progress for N seconds after creation (default: 0 = no monitoring)
- `--show-queue-status`: Show queue status before and after task generation

#### Features

- **Multilingual Content**: 5 Italian + 5 other languages (Spanish, French, German, Portuguese, English)
- **Realistic Fake News**: Each article ~300 words with authentic fake news patterns
- **Diverse Topics**: Health misinformation, political conspiracies, economic scandals, celebrity gossip, technology fears
- **Progress Tracking**: Real-time feedback on task creation success/failure
- **Queue Monitoring**: Optional before/after queue status display
- **Task Progress Monitoring**: Optional monitoring of task state transitions
- **Content Variety**: Different conspiracy theories and misinformation patterns per language
- **Character Count Tracking**: Shows content length for each submitted task

#### Generated Content Types

**Italian Articles:**
1. Health misinformation (COVID-19 vaccine nanochips)
2. Political conspiracy (Salvini-Putin secret agreement)
3. Economic conspiracy (Bank of Italy printing fake money for mafia)
4. Celebrity scandal (Chiara Ferragni organ trafficking)
5. Environmental conspiracy (Vesuvius eruption cover-up)

**Other Languages:**
1. **Spanish**: Political conspiracy (Sánchez-Soros destruction plan)
2. **French**: Health misinformation (Macron hiding vaccine deaths)
3. **German**: Economic conspiracy (Scholz selling Germany to China)
4. **Portuguese**: Celebrity scandal (Cristiano Ronaldo money laundering)
5. **English**: Technology conspiracy (Musk's Neuralink prisoner experiments)

#### Perfect for Testing

- **Multilingual Processing**: Test summarization across different languages
- **Content Variety**: Diverse fake news patterns and conspiracy theories
- **System Load**: 10 simultaneous tasks to test worker capacity
- **Language Detection**: Verify system handles different character sets
- **Content Length**: All articles ~300 words for consistent processing time
- **Real-world Scenarios**: Authentic fake news patterns for realistic testing

#### Example Output

```
Multilingual Fake News Summarization Task Generator
Target: http://localhost:8000
Tasks to create: 10 (5 Italian + 5 other languages)
Delay between submissions: 0.5s

Generating 10 multilingual fake news summarization tasks...
Submitting Italian Fake News #1 (1510 chars)...
  ✅ Created: df0235f3-fc9e-4a30-afc1-6911230cd24a
Submitting Italian Fake News #2 (1454 chars)...
  ✅ Created: 5c1d5af9-4c85-4bc8-8c3a-763adc4c1eb7
...
Submitting English Fake News #5 (1533 chars)...
  ✅ Created: f0f7bd4e-c96d-4840-bc42-d792f5db6f59

MULTILINGUAL FAKE NEWS TASK GENERATION SUMMARY
Total tasks attempted: 10
Successfully created: 10
Failed: 0
Success rate: 100.0%

Language Distribution:
  Italian articles: 5
  Other languages: 5

🎉 All 10 multilingual tasks created successfully!
💡 Use --monitor flag to track task processing progress
```

#### Dependencies

Requires `httpx` for async HTTP client functionality:

```bash
python3 -m pip install httpx --user
```

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

### `delete_defective_tasks.py`

**NEW**: Utility to identify and delete defective tasks from Redis that have corrupted data.

This script finds and removes tasks with missing or invalid data such as:
- Missing task_id (shows as "unknown_id" in frontend)
- Invalid timestamps (datetime.min or year 1)
- Missing required fields (task_id, state, created_at)

#### Usage

```bash
# Dry run - see what would be deleted without actually deleting
python3 utils/delete_defective_tasks.py --dry-run

# Actually delete the defective tasks
python3 utils/delete_defective_tasks.py

# Use custom Redis URL
python3 utils/delete_defective_tasks.py --redis-url redis://localhost:6379/1
```

#### Command Line Options

- `--redis-url URL`: Redis connection URL (default: redis://localhost:6379/0)
- `--dry-run`: Show what would be deleted without actually deleting
- `--help`: Show help message

#### Features

- **Comprehensive Detection**: Identifies multiple types of data corruption
- **Safe Operation**: Dry-run mode to preview changes before deletion
- **Detailed Reporting**: Shows all defective task details before deletion
- **Atomic Deletion**: Uses Redis transactions for safe cleanup
- **Queue Cleanup**: Removes task references from all queues
- **Interactive Confirmation**: Requires explicit confirmation before deletion

#### Defective Task Patterns Detected

1. **Missing Task ID**: Tasks without a valid task_id field
2. **Invalid Timestamps**: Tasks with datetime.min or year 1 dates
3. **Missing Required Fields**: Tasks lacking essential fields like state or created_at
4. **Corrupted Date Formats**: Tasks with unparseable date strings

#### Example Output

```
Defective Task Cleanup Utility
Redis URL: redis://localhost:6379/0
Mode: DRY RUN

Connected to Redis at redis://localhost:6379/0
Scanned 27 total tasks
Found 3 defective tasks

Defective tasks found:
--------------------------------------------------------------------------------
1. Redis Key: task:52334909-bf63-4a69-b326-edb40ef2916a
   Task ID: missing
   State: COMPLETED
   Created: missing
   Updated: 2025-07-20T19:16:09.875503
   Completed: 2025-07-20T19:16:09.875503
   Type: missing
   Content: missing

DRY RUN: Would delete 3 defective tasks
```

#### When to Use

- **Data Corruption**: When frontend shows tasks with "unknown_id" or invalid dates
- **Development Issues**: After development bugs that created malformed tasks
- **System Cleanup**: Regular maintenance to remove corrupted data
- **Migration Recovery**: After data migration issues or system upgrades
- **Frontend Debugging**: When UI shows strange task entries

#### Safety Features

- **Dry-run Mode**: Always test with `--dry-run` first
- **Interactive Confirmation**: Requires typing "yes" to proceed with deletion
- **Detailed Preview**: Shows exactly what will be deleted
- **Transaction Safety**: Uses Redis pipelines for atomic operations
- **Comprehensive Cleanup**: Removes tasks from all queues and storage locations

#### Integration with Monitoring

Can be used in automated maintenance scripts:

```bash
# Check for defective tasks and alert if found
DEFECTIVE_COUNT=$(python3 utils/delete_defective_tasks.py --dry-run | grep "Found.*defective tasks" | awk '{print $2}')
if [ "$DEFECTIVE_COUNT" -gt 0 ]; then
    echo "WARNING: $DEFECTIVE_COUNT defective tasks found in Redis"
    # Send alert or notification
fi
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
