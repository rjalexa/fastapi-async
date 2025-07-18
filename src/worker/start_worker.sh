#!/bin/bash
# src/worker/start_worker.sh
# Enhanced Celery worker startup script with monitoring and error recovery

set -e  # Exit on any error

# Configure logging
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log "Starting Celery worker with enhanced startup..."
log "Working directory: $(pwd)"
log "User: $(whoami)"

# Function to clean Python bytecode cache
clean_pycache() {
    log "Cleaning Python bytecode cache..."
    
    # Remove all __pycache__ directories and .pyc files
    find /app -name "*.pyc" -delete 2>/dev/null || true
    find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log "Python bytecode cache cleaned"
}

# Function to check if Redis is available
check_redis() {
    log "Checking Redis connectivity..."
    
    # Use uv to run a simple Redis connectivity check
    if uv run python -c "import redis; r=redis.from_url('${REDIS_URL:-redis://redis:6379/0}'); r.ping(); print('Redis OK')" 2>/dev/null; then
        log "Redis connection: OK"
        return 0
    else
        log "Redis connection: FAILED"
        return 1
    fi
}

# Function to validate imports
validate_imports() {
    log "Validating imports..."
    
    if uv run python -c "
from tasks import app
from config import settings
from circuit_breaker import get_circuit_breaker_status
print('All imports successful')
" 2>/dev/null; then
        log "Import validation: OK"
        return 0
    else
        log "Import validation: FAILED"
        return 1
    fi
}

# Function to start consumer in background
start_consumer() {
    log "Starting Redis queue consumer..."
    
    # Start the consumer in the background
    uv run python consumer.py &
    CONSUMER_PID=$!
    
    log "Consumer started with PID: $CONSUMER_PID"
    echo $CONSUMER_PID > /tmp/consumer.pid
    
    # Give consumer a moment to start
    sleep 2
    
    # Check if consumer is still running
    if kill -0 $CONSUMER_PID 2>/dev/null; then
        log "Consumer is running successfully"
        return 0
    else
        log "Consumer failed to start"
        return 1
    fi
}

# Function to start worker with retry logic
start_worker_with_retry() {
    local max_retries=3
    local retry_delay=5
    
    for attempt in $(seq 1 $max_retries); do
        log "Starting worker (attempt $attempt/$max_retries)..."
        
        # Clean bytecode cache on each retry
        clean_pycache
        
        # Validate imports
        if ! validate_imports; then
            log "Import validation failed"
            if [ $attempt -lt $max_retries ]; then
                log "Retrying in $retry_delay seconds..."
                sleep $retry_delay
                continue
            else
                log "Max retries exceeded. Worker startup failed."
                exit 1
            fi
        fi
        
        # Start the consumer first
        if ! start_consumer; then
            log "Consumer startup failed"
            if [ $attempt -lt $max_retries ]; then
                log "Retrying in $retry_delay seconds..."
                sleep $retry_delay
                continue
            else
                log "Max retries exceeded. Consumer startup failed."
                exit 1
            fi
        fi
        
        # Environment setup
        export CELERY_ENABLE_REMOTE_CONTROL=true
        export PYTHONDONTWRITEBYTECODE=1
        export PYTHONUNBUFFERED=1
        
        # Build Celery command arguments
        CELERY_ARGS=(
            "celery"
            "-A" "tasks"
            "worker"
            "--loglevel=${LOG_LEVEL:-info}"
            "--concurrency=${CELERY_WORKER_CONCURRENCY:-4}"
            "--prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-1}"
            "--max-tasks-per-child=${WORKER_MAX_TASKS_PER_CHILD:-1000}"
            "--max-memory-per-child=${WORKER_MAX_MEMORY_PER_CHILD:-200000}"
            "--without-gossip"
            "--without-mingle" 
            "--events"
            "--pool=prefork"
            "--time-limit=${CELERY_TASK_TIME_LIMIT:-900}"
            "--soft-time-limit=${CELERY_TASK_SOFT_TIME_LIMIT:-600}"
        )
        
        # Add hostname for better identification
        HOSTNAME=${HOSTNAME:-worker-$}
        CELERY_ARGS+=("--hostname" "${HOSTNAME}@%h")
        
        log "Starting worker with command: uv run ${CELERY_ARGS[*]}"
        
        # Start the worker (this will block)
        if uv run "${CELERY_ARGS[@]}"; then
            log "Worker started successfully"
            return 0
        else
            log "Worker startup failed (attempt $attempt)"
            # Kill consumer if worker fails
            if [ -f /tmp/consumer.pid ]; then
                CONSUMER_PID=$(cat /tmp/consumer.pid)
                kill $CONSUMER_PID 2>/dev/null || true
                rm -f /tmp/consumer.pid
            fi
            
            if [ $attempt -lt $max_retries ]; then
                log "Retrying in $retry_delay seconds..."
                sleep $retry_delay
            else
                log "Max retries exceeded. Worker startup failed."
                exit 1
            fi
        fi
    done
}

# Function to handle shutdown signals
cleanup() {
    log "Received shutdown signal, cleaning up..."
    
    # Kill consumer if running
    if [ -f /tmp/consumer.pid ]; then
        CONSUMER_PID=$(cat /tmp/consumer.pid)
        log "Stopping consumer (PID: $CONSUMER_PID)..."
        kill $CONSUMER_PID 2>/dev/null || true
        rm -f /tmp/consumer.pid
    fi
    
    # Kill any remaining processes
    pkill -f "python consumer.py" 2>/dev/null || true
    
    log "Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Main execution
log "Environment check..."
log "REDIS_URL: ${REDIS_URL:-not set}"
log "CELERY_BROKER_URL: ${CELERY_BROKER_URL:-not set}"
log "CELERY_RESULT_BACKEND: ${CELERY_RESULT_BACKEND:-not set}"

# Health check (non-blocking)
if check_redis; then
    log "Health check: PASSED"
else
    log "Health check: FAILED (continuing anyway)"
fi

# Start worker with retry logic
start_worker_with_retry
