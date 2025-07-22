"""
Optimized Redis connection configuration for worker tasks.
Specialized for long-running operations and high-throughput task processing.
"""

import asyncio
import logging
from typing import Optional
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class WorkerRedisConfig:
    """Redis connection pool configuration optimized for worker tasks."""

    # Connection Pool Settings for Workers
    MAX_CONNECTIONS = 30  # Fewer connections than API since workers are more focused
    MIN_IDLE_CONNECTIONS = 3  # Keep minimum connections alive
    MAX_IDLE_TIME = (
        600  # 10 minutes before idle connections are closed (longer for workers)
    )

    # Connection Timeouts (in seconds) - optimized for long-running tasks
    SOCKET_CONNECT_TIMEOUT = 15  # Longer connection timeout for workers
    SOCKET_TIMEOUT = 60  # Longer socket timeout for task processing
    SOCKET_KEEPALIVE = True  # Enable TCP keepalive
    SOCKET_KEEPALIVE_OPTIONS = {
        "TCP_KEEPIDLE": 300,  # Start keepalive after 5 minutes idle
        "TCP_KEEPINTVL": 30,  # Keepalive probe interval
        "TCP_KEEPCNT": 5,  # Number of failed probes before connection is dropped
    }

    # Health Check Settings
    HEALTH_CHECK_INTERVAL = 60  # Check connection health every minute

    # Retry Configuration
    RETRY_ON_ERROR = [
        redis.ConnectionError,
        redis.TimeoutError,
        redis.BusyLoadingError,
    ]
    RETRY_ATTEMPTS = 5  # More retries for workers
    RETRY_BACKOFF = ExponentialBackoff(cap=30, base=2)  # Longer backoff for workers

    # Command Timeouts for Worker Operations
    BLOCKING_TIMEOUT = 300  # 5 minutes for blocking operations like BLPOP
    TASK_UPDATE_TIMEOUT = 30  # 30 seconds for task state updates
    PIPELINE_TIMEOUT = 60  # 1 minute for pipeline operations
    HEARTBEAT_TIMEOUT = 10  # 10 seconds for heartbeat updates


class WorkerRedisConnectionManager:
    """Manages Redis connections optimized for worker task processing."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None
        self._health_check_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the Redis connection pool with worker-optimized settings."""
        if self._pool is not None:
            return

        # Create connection pool with worker-optimized settings
        self._pool = ConnectionPool.from_url(
            self.redis_url,
            # Pool configuration
            max_connections=WorkerRedisConfig.MAX_CONNECTIONS,
            retry_on_error=WorkerRedisConfig.RETRY_ON_ERROR,
            retry=Retry(
                backoff=WorkerRedisConfig.RETRY_BACKOFF,
                retries=WorkerRedisConfig.RETRY_ATTEMPTS,
            ),
            # Connection timeouts
            socket_connect_timeout=WorkerRedisConfig.SOCKET_CONNECT_TIMEOUT,
            socket_timeout=WorkerRedisConfig.SOCKET_TIMEOUT,
            socket_keepalive=WorkerRedisConfig.SOCKET_KEEPALIVE,
            socket_keepalive_options=WorkerRedisConfig.SOCKET_KEEPALIVE_OPTIONS,
            # Encoding
            decode_responses=True,
            encoding="utf-8",
            # Connection lifecycle
            health_check_interval=WorkerRedisConfig.HEALTH_CHECK_INTERVAL,
        )

        # Create Redis client
        self._redis = redis.Redis(connection_pool=self._pool)

        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._health_monitor())

        logger.info(
            f"Worker Redis connection pool initialized: "
            f"max_connections={WorkerRedisConfig.MAX_CONNECTIONS}, "
            f"health_check_interval={WorkerRedisConfig.HEALTH_CHECK_INTERVAL}s"
        )

    async def close(self) -> None:
        """Close the Redis connection pool and cleanup resources."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._redis:
            await self._redis.aclose()
            self._redis = None

        if self._pool:
            await self._pool.aclose()
            self._pool = None

        logger.info("Worker Redis connection pool closed")

    @property
    def redis(self) -> redis.Redis:
        """Get the Redis client instance."""
        if self._redis is None:
            raise RuntimeError(
                "Redis connection not initialized. Call initialize() first."
            )
        return self._redis

    @asynccontextmanager
    async def get_connection(self, timeout: Optional[float] = None):
        """
        Get a Redis connection with automatic cleanup.

        Args:
            timeout: Optional timeout for operations using this connection
        """
        if timeout is None:
            timeout = WorkerRedisConfig.TASK_UPDATE_TIMEOUT

        connection = None
        try:
            # Get connection from pool
            connection = await self._pool.get_connection("_")

            # Create Redis instance with this specific connection
            redis_client = redis.Redis(
                connection_pool=self._pool,
                socket_timeout=timeout,
                decode_responses=True,
            )

            yield redis_client

        except Exception as e:
            logger.error(f"Worker Redis connection error: {e}")
            raise
        finally:
            if connection:
                try:
                    await self._pool.release(connection)
                except Exception as e:
                    logger.warning(f"Error releasing worker Redis connection: {e}")

    async def execute_with_retry(self, operation, *args, **kwargs):
        """
        Execute a Redis operation with automatic retry logic.

        Args:
            operation: Redis operation to execute
            *args, **kwargs: Arguments for the operation
        """
        last_exception = None

        for attempt in range(WorkerRedisConfig.RETRY_ATTEMPTS):
            try:
                return await operation(*args, **kwargs)
            except WorkerRedisConfig.RETRY_ON_ERROR as e:
                last_exception = e
                if attempt < WorkerRedisConfig.RETRY_ATTEMPTS - 1:
                    delay = WorkerRedisConfig.RETRY_BACKOFF.compute(attempt)
                    logger.warning(
                        f"Worker Redis operation failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Worker Redis operation failed after {WorkerRedisConfig.RETRY_ATTEMPTS} attempts"
                    )
            except Exception as e:
                # Non-retryable error
                logger.error(
                    f"Worker Redis operation failed with non-retryable error: {e}"
                )
                raise

        # If we get here, all retries failed
        raise last_exception

    async def _health_monitor(self) -> None:
        """Background task to monitor Redis connection health."""
        while True:
            try:
                await asyncio.sleep(WorkerRedisConfig.HEALTH_CHECK_INTERVAL)

                # Ping Redis to check health
                await self._redis.ping()

                # Log pool statistics
                if hasattr(self._pool, "_available_connections"):
                    available = len(self._pool._available_connections)
                    created = self._pool._created_connections
                    logger.debug(
                        f"Worker Redis pool health: {available} available, {created} total connections"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Worker Redis health check failed: {e}")

    async def get_pool_stats(self) -> dict:
        """Get current connection pool statistics."""
        if not self._pool:
            return {"status": "not_initialized"}

        stats = {
            "max_connections": WorkerRedisConfig.MAX_CONNECTIONS,
            "created_connections": getattr(self._pool, "_created_connections", 0),
            "available_connections": len(
                getattr(self._pool, "_available_connections", [])
            ),
            "in_use_connections": None,
        }

        # Calculate in-use connections
        if (
            stats["created_connections"] is not None
            and stats["available_connections"] is not None
        ):
            stats["in_use_connections"] = (
                stats["created_connections"] - stats["available_connections"]
            )

        return stats


# Specialized Redis clients for worker operations
class WorkerBlockingRedisClient:
    """Redis client optimized for blocking operations in workers."""

    def __init__(self, connection_manager: WorkerRedisConnectionManager):
        self.connection_manager = connection_manager

    async def blpop(self, keys, timeout: int = 0):
        """
        Blocking list pop with worker-optimized timeout handling.

        Args:
            keys: List of keys to pop from
            timeout: Timeout in seconds (0 = block indefinitely)
        """
        # Use longer socket timeout for blocking operations
        socket_timeout = max(
            timeout + 30 if timeout > 0 else WorkerRedisConfig.BLOCKING_TIMEOUT,
            WorkerRedisConfig.BLOCKING_TIMEOUT,
        )

        async with self.connection_manager.get_connection(
            timeout=socket_timeout
        ) as redis_client:
            return await redis_client.blpop(keys, timeout=timeout)

    async def brpop(self, keys, timeout: int = 0):
        """
        Blocking right pop with worker-optimized timeout handling.

        Args:
            keys: List of keys to pop from
            timeout: Timeout in seconds (0 = block indefinitely)
        """
        socket_timeout = max(
            timeout + 30 if timeout > 0 else WorkerRedisConfig.BLOCKING_TIMEOUT,
            WorkerRedisConfig.BLOCKING_TIMEOUT,
        )

        async with self.connection_manager.get_connection(
            timeout=socket_timeout
        ) as redis_client:
            return await redis_client.brpop(keys, timeout=timeout)


class WorkerTaskRedisClient:
    """Redis client optimized for task state management in workers."""

    def __init__(self, connection_manager: WorkerRedisConnectionManager):
        self.connection_manager = connection_manager

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True):
        """
        Get a Redis pipeline optimized for task updates.

        Args:
            transaction: Whether to use transaction mode
        """
        async with self.connection_manager.get_connection(
            timeout=WorkerRedisConfig.PIPELINE_TIMEOUT
        ) as redis_client:
            async with redis_client.pipeline(transaction=transaction) as pipe:
                yield pipe

    async def update_heartbeat(self, worker_id: str):
        """Update worker heartbeat with optimized timeout."""
        async with self.connection_manager.get_connection(
            timeout=WorkerRedisConfig.HEARTBEAT_TIMEOUT
        ) as redis_client:
            import time

            current_time = time.time()
            heartbeat_key = f"worker:heartbeat:{worker_id}"
            await redis_client.setex(heartbeat_key, 90, current_time)


# Global connection manager instance for workers
_worker_connection_manager: Optional[WorkerRedisConnectionManager] = None


async def initialize_worker_redis(redis_url: str) -> WorkerRedisConnectionManager:
    """Initialize the global worker Redis connection manager."""
    global _worker_connection_manager

    if _worker_connection_manager is not None:
        await _worker_connection_manager.close()

    _worker_connection_manager = WorkerRedisConnectionManager(redis_url)
    await _worker_connection_manager.initialize()

    return _worker_connection_manager


async def get_worker_redis_manager() -> WorkerRedisConnectionManager:
    """Get the global worker Redis connection manager."""
    if _worker_connection_manager is None:
        raise RuntimeError("Worker Redis connection manager not initialized")
    return _worker_connection_manager


async def close_worker_redis() -> None:
    """Close the global worker Redis connection manager."""
    global _worker_connection_manager
    if _worker_connection_manager is not None:
        await _worker_connection_manager.close()
        _worker_connection_manager = None


# Convenience functions for different Redis client types
async def get_worker_standard_redis() -> redis.Redis:
    """Get a standard Redis client for worker operations."""
    manager = await get_worker_redis_manager()
    return manager.redis


async def get_worker_blocking_redis() -> WorkerBlockingRedisClient:
    """Get a Redis client optimized for blocking operations in workers."""
    manager = await get_worker_redis_manager()
    return WorkerBlockingRedisClient(manager)


async def get_worker_task_redis() -> WorkerTaskRedisClient:
    """Get a Redis client optimized for task management in workers."""
    manager = await get_worker_redis_manager()
    return WorkerTaskRedisClient(manager)
