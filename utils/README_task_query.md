# Redis Task Query Utilities

This directory contains utilities to query Redis task data without overwhelming the context window with large payloads (especially for PDF extraction tasks).

## Problem

When using `docker compose exec redis redis-cli HGETALL task:<task_id>` for PDF extraction tasks, the output includes the entire base64-encoded PDF content and extracted text, which can be hundreds of thousands of characters and overwhelm terminal output or context windows.

## Solution

Two new utilities provide filtered access to task data:

### 1. `query_task_metadata.py` - Python Script

A Python script that connects directly to Redis and provides filtered views of task data.

**Usage:**
```bash
# Get task metadata without large payloads
python3 utils/query_task_metadata.py <task_id>

# List all available fields with their sizes
python3 utils/query_task_metadata.py <task_id> --mode fields

# Get a specific field value
python3 utils/query_task_metadata.py <task_id> --mode field --field state

# Preview content field (first 200 chars)
python3 utils/query_task_metadata.py <task_id> --mode content-preview

# Preview result field (first 200 chars)
python3 utils/query_task_metadata.py <task_id> --mode result-preview

# Get metadata as JSON
python3 utils/query_task_metadata.py <task_id> --json
```

**Modes:**
- `metadata` (default): Shows all task metadata excluding large content/result fields
- `fields`: Lists all available fields with their sizes
- `field`: Gets a specific field value
- `content-preview`: Shows a preview of the content field
- `result-preview`: Shows a preview of the result field

### 2. `redis_task_query.sh` - Shell Wrapper

A convenient shell script wrapper that provides easy-to-remember commands.

**Usage:**
```bash
# Get task metadata (replaces HGETALL)
./utils/redis_task_query.sh metadata 05ade2f8-39da-46ff-8dc2-92f3737273c1

# List all fields
./utils/redis_task_query.sh fields 05ade2f8-39da-46ff-8dc2-92f3737273c1

# Get specific field (replaces HGET)
./utils/redis_task_query.sh field 05ade2f8-39da-46ff-8dc2-92f3737273c1 state

# Preview content (first 200 chars)
./utils/redis_task_query.sh content 05ade2f8-39da-46ff-8dc2-92f3737273c1

# Preview content (first 100 chars)
./utils/redis_task_query.sh content 05ade2f8-39da-46ff-8dc2-92f3737273c1 100

# Preview result
./utils/redis_task_query.sh result 05ade2f8-39da-46ff-8dc2-92f3737273c1

# Get metadata as JSON
./utils/redis_task_query.sh json 05ade2f8-39da-46ff-8dc2-92f3737273c1
```

## What You Get

### Metadata Mode Output
Instead of overwhelming output, you get structured information like:

```
Task Metadata for 05ade2f8-39da-46ff-8dc2-92f3737273c1:
==================================================
task_id: 05ade2f8-39da-46ff-8dc2-92f3737273c1
state: COMPLETED
task_type: pdfxtract
retry_count: 0
max_retries: 3
created_at: 2025-01-21 14:15:30 UTC
updated_at: 2025-01-21 14:16:45 UTC
completed_at: 2025-01-21 14:16:45 UTC
content_summary:
  length: 1234567
  preview: /9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/...
  type: base64_encoded
result_summary:
  length: 45678
  preview: {"filename": "il-manifesto-del-31-dicembre-2023.pdf", "issue_date": "2023-12-31", "pages": [{"page_number": 1, "status": "processed"...
  type: json
error_history: 0 items
```

### Fields Mode Output
```
{
  "content": "large (1234567 chars)",
  "result": "large (45678 chars)",
  "state": "text (9 chars)",
  "task_type": "text (9 chars)",
  "created_at": "text (27 chars)",
  "error_history": "json (2 chars)"
}
```

## Command Replacements

| Old Command | New Command |
|-------------|-------------|
| `docker compose exec redis redis-cli HGETALL task:05ade2f8-39da-46ff-8dc2-92f3737273c1` | `./utils/redis_task_query.sh metadata 05ade2f8-39da-46ff-8dc2-92f3737273c1` |
| `docker compose exec redis redis-cli HGET task:05ade2f8-39da-46ff-8dc2-92f3737273c1 state` | `./utils/redis_task_query.sh field 05ade2f8-39da-46ff-8dc2-92f3737273c1 state` |

## Requirements

- Python 3.6+
- `redis` Python package (install with `pip install redis`)
- Redis server running on localhost:6379 (or modify the connection string in the script)

## Benefits

1. **No Context Window Overflow**: Large payloads are summarized, not displayed in full
2. **Structured Output**: Clean, readable format for task metadata
3. **Selective Querying**: Get only the information you need
4. **Content Type Detection**: Automatically detects base64, JSON, or text content
5. **Timestamp Formatting**: Human-readable timestamp display
6. **Error History**: Parsed and formatted error history and retry information

## Use Cases

- **Debugging Tasks**: Quickly check task state, errors, and timing without payload noise
- **Monitoring**: Get overview of task progress and health
- **Troubleshooting**: Examine error history and retry patterns
- **Content Inspection**: Preview content without full display
- **API Development**: Get structured data for integration with monitoring tools
