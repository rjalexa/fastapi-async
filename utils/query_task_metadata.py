#!/usr/bin/env python3
"""
Utility to query Redis task metadata without overwhelming output with large payloads.

This script provides several modes to inspect task data:
1. Metadata only (excludes content and result fields)
2. Content summary (shows content/result length instead of full data)
3. Specific field queries
4. Error history and retry information
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional

import redis


def get_redis_connection() -> redis.Redis:
    """Get Redis connection using default settings."""
    return redis.from_url("redis://localhost:6379", decode_responses=True)


def format_timestamp(timestamp_str: Optional[str]) -> str:
    """Format ISO timestamp for display."""
    if not timestamp_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return timestamp_str


def get_content_summary(content: str, max_preview: int = 100) -> Dict[str, Any]:
    """Get summary information about content field."""
    if not content:
        return {"length": 0, "preview": "", "type": "empty"}

    length = len(content)
    preview = content[:max_preview] + "..." if length > max_preview else content

    # Detect content type
    content_type = "text"
    if content.startswith("data:"):
        content_type = "base64_data_url"
    elif content.startswith("/9j/") or content.startswith("iVBORw0KGgo"):
        content_type = "base64_encoded"
    elif content.strip().startswith("{") and content.strip().endswith("}"):
        content_type = "json"

    return {"length": length, "preview": preview, "type": content_type}


def query_task_metadata(redis_conn: redis.Redis, task_id: str) -> Dict[str, Any]:
    """Query task metadata excluding large payload fields."""
    task_data = redis_conn.hgetall(f"task:{task_id}")

    if not task_data:
        return {"error": f"Task {task_id} not found"}

    # Extract metadata fields (excluding large payloads)
    metadata = {}

    # Basic task info
    metadata["task_id"] = task_id
    metadata["state"] = task_data.get("state", "UNKNOWN")
    metadata["task_type"] = task_data.get("task_type", "summarize")
    metadata["retry_count"] = task_data.get("retry_count", "0")
    metadata["max_retries"] = task_data.get("max_retries", "3")

    # Timestamps
    metadata["created_at"] = format_timestamp(task_data.get("created_at"))
    metadata["updated_at"] = format_timestamp(task_data.get("updated_at"))
    metadata["started_at"] = format_timestamp(task_data.get("started_at"))
    metadata["completed_at"] = format_timestamp(task_data.get("completed_at"))
    metadata["failed_at"] = format_timestamp(task_data.get("failed_at"))
    metadata["dlq_at"] = format_timestamp(task_data.get("dlq_at"))
    metadata["retry_after"] = format_timestamp(task_data.get("retry_after"))

    # Error information
    metadata["last_error"] = task_data.get("last_error", "")
    metadata["error_type"] = task_data.get("error_type", "")

    # Worker info
    metadata["worker_id"] = task_data.get("worker_id", "")

    # Content and result summaries (not full content)
    content = task_data.get("content", "")
    result = task_data.get("result", "")

    metadata["content_summary"] = get_content_summary(content)
    metadata["result_summary"] = get_content_summary(result)

    # Parse JSON fields if they exist
    for field in ["error_history", "retry_timestamps", "metadata"]:
        if field in task_data and task_data[field]:
            try:
                metadata[field] = json.loads(task_data[field])
            except json.JSONDecodeError:
                metadata[f"{field}_raw"] = task_data[field]

    return metadata


def query_specific_field(redis_conn: redis.Redis, task_id: str, field: str) -> Any:
    """Query a specific field from task data."""
    value = redis_conn.hget(f"task:{task_id}", field)

    if value is None:
        return {"error": f"Field '{field}' not found in task {task_id}"}

    # Try to parse JSON fields
    if field in ["error_history", "retry_timestamps", "metadata"]:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    return value


def list_task_fields(redis_conn: redis.Redis, task_id: str) -> Dict[str, str]:
    """List all available fields for a task with their types/sizes."""
    task_data = redis_conn.hgetall(f"task:{task_id}")

    if not task_data:
        return {"error": f"Task {task_id} not found"}

    field_info = {}
    for field, value in task_data.items():
        if not value:
            field_info[field] = "empty"
        elif len(value) > 1000:
            field_info[field] = f"large ({len(value)} chars)"
        elif value.strip().startswith("{") and value.strip().endswith("}"):
            field_info[field] = f"json ({len(value)} chars)"
        else:
            field_info[field] = f"text ({len(value)} chars)"

    return field_info


def main():
    parser = argparse.ArgumentParser(
        description="Query Redis task data without overwhelming output"
    )
    parser.add_argument("task_id", help="Task ID to query")
    parser.add_argument(
        "--mode",
        choices=["metadata", "field", "fields", "content-preview", "result-preview"],
        default="metadata",
        help="Query mode (default: metadata)",
    )
    parser.add_argument(
        "--field", help="Specific field to query (required for --mode field)"
    )
    parser.add_argument(
        "--preview-length",
        type=int,
        default=200,
        help="Length of content preview (default: 200)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    try:
        redis_conn = get_redis_connection()

        if args.mode == "metadata":
            result = query_task_metadata(redis_conn, args.task_id)
        elif args.mode == "field":
            if not args.field:
                print("Error: --field is required when using --mode field")
                sys.exit(1)
            result = query_specific_field(redis_conn, args.task_id, args.field)
        elif args.mode == "fields":
            result = list_task_fields(redis_conn, args.task_id)
        elif args.mode == "content-preview":
            content = redis_conn.hget(f"task:{args.task_id}", "content")
            if content:
                result = get_content_summary(content, args.preview_length)
            else:
                result = {"error": "No content found"}
        elif args.mode == "result-preview":
            result_data = redis_conn.hget(f"task:{args.task_id}", "result")
            if result_data:
                result = get_content_summary(result_data, args.preview_length)
            else:
                result = {"error": "No result found"}

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            if isinstance(result, dict) and "error" in result:
                print(f"Error: {result['error']}")
                sys.exit(1)

            if args.mode == "metadata":
                print(f"Task Metadata for {args.task_id}:")
                print("=" * 50)
                for key, value in result.items():
                    if isinstance(value, dict):
                        print(f"{key}:")
                        for subkey, subvalue in value.items():
                            print(f"  {subkey}: {subvalue}")
                    elif isinstance(value, list):
                        print(f"{key}: {len(value)} items")
                        if value:  # Show first few items
                            for i, item in enumerate(value[:3]):
                                print(f"  [{i}]: {item}")
                            if len(value) > 3:
                                print(f"  ... and {len(value) - 3} more")
                    else:
                        print(f"{key}: {value}")
            else:
                print(json.dumps(result, indent=2, default=str))

    except redis.RedisError as e:
        print(f"Redis error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
