# AsyncTaskFlow Utilities

This directory contains utility scripts for maintaining and testing the AsyncTaskFlow system.

## Scripts

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
