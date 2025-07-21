# Redis Connection Pool Optimization for Long-Running Tasks

## Overview

This document describes the Redis connection pool optimizations implemented to address connection issues with long-running async tasks in the FastAPI AsyncTaskFlow system.

## Problem Statement

The original Redis connection setup was experiencing issues with long-running tasks:

- **Connection Pool Exhaustion**: Default Redis connection pools (10 connections) were insufficient for concurrent long-running tasks
- **Connection Timeouts**: Socket timeouts were too short for operations like BLPOP that could block for extended periods
- **Connection Lifecycle Issues**: Connections were not being properly managed for different operation types
- **No Connection Health Monitoring**: Failed connections were not being detected and recovered automatically

## Solution Architecture

### 1. Optimized Connection Pool Configuration

#### API Service Configuration (`src/api/redis_config.py`)
```python
class OptimizedRedisConfig:
    MAX_CONNECTIONS = 50        # Increased from default 10
    SOCKET_TIMEOUT = 30         # 30 seconds for regular operations
    LONG_RUNNING_TIMEOUT = 120  # 2 minutes for blocking operations
    HEALTH_CHECK_INTERVAL = 30  # Health checks every 30 seconds
```

#### Worker Service Configuration (`src/worker/redis_config.py`)
```python
class WorkerRedisConfig:
    MAX_CONNECTIONS = 30        # Optimized for worker focus
    SOCKET_TIMEOUT = 60         # Longer timeout for task processing
    BLOCKING_TIMEOUT = 300      # 5 minutes for BLPOP operations
    HEALTH_CHECK_INTERVAL = 60  # Health checks every minute
```

### 2. Specialized Redis Clients

#### Long-Running Operations Client
- **Purpose**: Optimized for blocking operations like BLPOP/BRPOP
- **Features**: Extended socket timeouts, automatic timeout calculation
- **Usage**: Queue consumption, task waiting operations

#### Pipeline Operations Client
- **Purpose**: Optimized for batch operations and transactions
- **Features**: Transaction support, optimized timeouts for bulk operations
- **Usage**: State updates, counter management, bulk task operations

#### Task Management Client
- **Purpose**: Optimized for frequent task state updates
- **Features**: Heartbeat management, optimized pipeline operations
- **Usage**: Worker heartbeats, task state transitions

### 3. Connection Lifecycle Management

#### Automatic Connection Recovery
```python
async def execute_with_retry(self, operation, *args, **kwargs):
    """Execute Redis operations with automatic retry logic."""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await operation(*args, **kwargs)
        except RETRY_ON_ERROR as e:
            if attempt < RETRY_ATTEMPTS - 1:
                delay = RETRY_BACKOFF.compute(attempt)
                await asyncio.sleep(delay)
```

#### Health Monitoring
```python
async def _health_monitor(self):
    """Background task to monitor Redis connection health."""
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        await self._redis.ping()
        # Log pool statistics
```

### 4. TCP Keepalive Configuration

```python
SOCKET_KEEPALIVE_OPTIONS = {
    'TCP_KEEPIDLE': 600,    # Start keepalive after 10 minutes idle
    'TCP_KEEPINTVL': 60,    # Keepalive probe interval
    'TCP_KEEPCNT': 3        # Failed probes before connection drop
}
```

## Implementation Details

### API Service Integration

1. **Service Initialization**: Updated `RedisService` to use optimized connection manager
2. **Lifecycle Management**: Proper initialization and cleanup in FastAPI lifespan
3. **Pool Statistics**: Added monitoring endpoints for connection pool health

### Worker Service Integration

1. **Task Processing**: Updated task functions to use optimized Redis connections
2. **Error Handling**: Improved error handling with proper connection cleanup
3. **Heartbeat Management**: Optimized worker heartbeat updates

### Connection Pool Statistics

The system now provides detailed connection pool statistics:

```python
{
    "max_connections": 50,
    "created_connections": 15,
    "available_connections": 12,
    "in_use_connections": 3
}
```

## Performance Benefits

### 1. Increased Throughput
- **50 connections** for API service (vs 10 default)
- **30 connections** for worker service (optimized for focused operations)
- **Reduced connection contention** for concurrent operations

### 2. Improved Reliability
- **Automatic retry logic** with exponential backoff
- **Health monitoring** with automatic recovery
- **TCP keepalive** prevents silent connection drops

### 3. Better Resource Management
- **Connection pooling** reduces connection overhead
- **Specialized clients** optimize for specific use cases
- **Proper cleanup** prevents resource leaks

### 4. Enhanced Monitoring
- **Real-time pool statistics** for operational visibility
- **Health check endpoints** for system monitoring
- **Connection lifecycle logging** for debugging

## Configuration Options

### Environment Variables

```bash
# Redis Connection Pool Settings
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=30
REDIS_HEALTH_CHECK_INTERVAL=30

# Worker-Specific Settings
WORKER_REDIS_MAX_CONNECTIONS=30
WORKER_REDIS_SOCKET_TIMEOUT=60
WORKER_REDIS_BLOCKING_TIMEOUT=300
```

### Tuning Guidelines

#### For High-Throughput APIs
- Increase `MAX_CONNECTIONS` (50-100)
- Reduce `SOCKET_TIMEOUT` for faster failure detection
- Increase `HEALTH_CHECK_INTERVAL` to reduce overhead

#### For Long-Running Tasks
- Increase `BLOCKING_TIMEOUT` for queue operations
- Increase `SOCKET_TIMEOUT` for task processing
- Enable TCP keepalive for stable connections

#### For Memory-Constrained Environments
- Reduce `MAX_CONNECTIONS` (20-30)
- Increase `HEALTH_CHECK_INTERVAL` to reduce overhead
- Use connection pooling more aggressively

## Monitoring and Troubleshooting

### Health Check Endpoints

```bash
# Check Redis connection health
GET /health

# Get detailed pool statistics
GET /api/v1/redis/pool-stats
```

### Log Analysis

Look for these log patterns:

```
# Successful initialization
Redis connection pool initialized: max_connections=50, health_check_interval=30s

# Health monitoring
Redis pool health: 12 available, 15 total connections

# Connection issues
Redis operation failed (attempt 1), retrying in 2s: Connection timeout
```

### Common Issues and Solutions

#### Connection Pool Exhaustion
- **Symptoms**: "ConnectionPool is full" errors
- **Solution**: Increase `MAX_CONNECTIONS` or optimize connection usage

#### Socket Timeouts
- **Symptoms**: "Socket timeout" errors during long operations
- **Solution**: Increase `SOCKET_TIMEOUT` or use specialized clients

#### Connection Drops
- **Symptoms**: Intermittent connection failures
- **Solution**: Enable TCP keepalive and health monitoring

## Migration Guide

### From Basic Redis Client

1. **Update imports**:
```python
# Before
import redis.asyncio as redis

# After
from redis_config import get_standard_redis, get_long_running_redis
```

2. **Update connection creation**:
```python
# Before
redis_conn = redis.from_url(redis_url)

# After
redis_conn = await get_standard_redis()
```

3. **Use specialized clients**:
```python
# For blocking operations
blocking_client = await get_long_running_redis()
result = await blocking_client.blpop(keys, timeout=300)

# For pipeline operations
pipeline_client = await get_pipeline_redis()
async with pipeline_client.pipeline() as pipe:
    # Batch operations
```

### Testing the Migration

1. **Start the services**:
```bash
docker compose up -d
```

2. **Check connection pool status**:
```bash
curl http://localhost:8000/health
```

3. **Monitor pool statistics**:
```bash
# Watch connection usage during load
watch -n 1 'curl -s http://localhost:8000/api/v1/redis/pool-stats'
```

4. **Test long-running operations**:
```bash
# Submit tasks and monitor connection stability
curl -X POST http://localhost:8000/api/v1/summarize \
  -H "Content-Type: application/json" \
  -d '{"content": "Long text to summarize..."}'
```

## Best Practices

### 1. Connection Management
- Always use the appropriate specialized client for your use case
- Don't hold connections longer than necessary
- Use connection pooling for all Redis operations

### 2. Error Handling
- Implement retry logic for transient connection errors
- Use circuit breakers for external service calls
- Log connection issues for monitoring

### 3. Monitoring
- Monitor connection pool statistics regularly
- Set up alerts for connection pool exhaustion
- Track connection health metrics

### 4. Performance Tuning
- Adjust pool sizes based on actual usage patterns
- Monitor connection utilization and adjust accordingly
- Use appropriate timeouts for different operation types

## Conclusion

The Redis connection pool optimization provides:

- **Improved reliability** for long-running tasks
- **Better resource utilization** through connection pooling
- **Enhanced monitoring** for operational visibility
- **Flexible configuration** for different deployment scenarios

This optimization ensures that the AsyncTaskFlow system can handle high-throughput, long-running task processing while maintaining connection stability and performance.
