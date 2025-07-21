#!/bin/bash
# Redis Task Query Wrapper Script
#
# This script provides convenient alternatives to direct Redis CLI commands
# that avoid overwhelming the context window with large payloads.
#
# Usage examples:
#   ./redis_task_query.sh metadata <task_id>     # Get task metadata without payloads
#   ./redis_task_query.sh fields <task_id>       # List all available fields
#   ./redis_task_query.sh field <task_id> state  # Get specific field value
#   ./redis_task_query.sh preview <task_id>      # Preview content/result

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUERY_SCRIPT="$SCRIPT_DIR/query_task_metadata.py"

# Check if the query script exists
if [[ ! -f "$QUERY_SCRIPT" ]]; then
    echo "Error: query_task_metadata.py not found at $QUERY_SCRIPT"
    exit 1
fi

# Function to show usage
show_usage() {
    echo "Usage: $0 <command> <task_id> [options]"
    echo ""
    echo "Commands:"
    echo "  metadata <task_id>              Show task metadata without large payloads"
    echo "  fields <task_id>                List all available fields with sizes"
    echo "  field <task_id> <field_name>    Get specific field value"
    echo "  content <task_id> [length]      Preview content field (default: 200 chars)"
    echo "  result <task_id> [length]       Preview result field (default: 200 chars)"
    echo "  json <task_id>                  Get metadata as JSON"
    echo ""
    echo "Examples:"
    echo "  $0 metadata 05ade2f8-39da-46ff-8dc2-92f3737273c1"
    echo "  $0 fields 05ade2f8-39da-46ff-8dc2-92f3737273c1"
    echo "  $0 field 05ade2f8-39da-46ff-8dc2-92f3737273c1 state"
    echo "  $0 content 05ade2f8-39da-46ff-8dc2-92f3737273c1 100"
    echo "  $0 result 05ade2f8-39da-46ff-8dc2-92f3737273c1"
    echo ""
    echo "This replaces commands like:"
    echo "  docker compose exec redis redis-cli HGETALL task:<task_id>"
    echo "  docker compose exec redis redis-cli HGET task:<task_id> <field>"
}

# Check minimum arguments
if [[ $# -lt 2 ]]; then
    show_usage
    exit 1
fi

COMMAND="$1"
TASK_ID="$2"

# Validate task ID format (basic UUID check)
if [[ ! "$TASK_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    echo "Warning: Task ID doesn't look like a UUID: $TASK_ID"
    echo "Continuing anyway..."
fi

case "$COMMAND" in
    "metadata"|"meta")
        echo "Querying task metadata for: $TASK_ID"
        echo "This replaces: docker compose exec redis redis-cli HGETALL task:$TASK_ID"
        echo ""
        uv run python "$QUERY_SCRIPT" "$TASK_ID" --mode metadata
        ;;
    
    "fields")
        echo "Listing fields for task: $TASK_ID"
        echo ""
        uv run python "$QUERY_SCRIPT" "$TASK_ID" --mode fields
        ;;
    
    "field")
        if [[ $# -lt 3 ]]; then
            echo "Error: field name required"
            echo "Usage: $0 field <task_id> <field_name>"
            exit 1
        fi
        FIELD_NAME="$3"
        echo "Querying field '$FIELD_NAME' for task: $TASK_ID"
        echo "This replaces: docker compose exec redis redis-cli HGET task:$TASK_ID $FIELD_NAME"
        echo ""
        uv run python "$QUERY_SCRIPT" "$TASK_ID" --mode field --field "$FIELD_NAME"
        ;;
    
    "content")
        PREVIEW_LENGTH="${3:-200}"
        echo "Previewing content field for task: $TASK_ID (first $PREVIEW_LENGTH chars)"
        echo ""
        uv run python "$QUERY_SCRIPT" "$TASK_ID" --mode content-preview --preview-length "$PREVIEW_LENGTH"
        ;;
    
    "result")
        PREVIEW_LENGTH="${3:-200}"
        echo "Previewing result field for task: $TASK_ID (first $PREVIEW_LENGTH chars)"
        echo ""
        uv run python "$QUERY_SCRIPT" "$TASK_ID" --mode result-preview --preview-length "$PREVIEW_LENGTH"
        ;;
    
    "json")
        uv run python "$QUERY_SCRIPT" "$TASK_ID" --mode metadata --json
        ;;
    
    "help"|"-h"|"--help")
        show_usage
        ;;
    
    *)
        echo "Error: Unknown command '$COMMAND'"
        echo ""
        show_usage
        exit 1
        ;;
esac
