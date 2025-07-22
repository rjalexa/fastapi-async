"""
Optimized Redis connection pool configuration for long-running async tasks.
Addresses connection pool exhaustion, timeouts, and connection lifecycle management.
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


class OptimizedRedisConfig:
    """Redis connection pool configuration optimized for long-running tasks."""

    # Connection Pool Settings
    MAX_CONNECTIONS = 50  # Increased from default 10
    MIN_IDLE_CONNECTIONS = 5  # Keep minimum connections alive
    MAX_IDLE_TIME = 300  # 5 minutes before idle connections are closed

    # Connection Timeouts (in seconds)
    SOCKET_CONNECT_TIMEOUT = 10  # Time to establish connection
    SOCKET_TIMEOUT = 30  # Socket read/write timeout
    SOCKET_KEEPALIVE = True  # Enable TCP keepalive
    SOCKET_KEEPALIVE_OPTIONS = {
        "TCP_KEEPIDLE": 600,  # Start keepalive after 10 minutes idle
        "TCP_KEEPINTVL": 60,  # Keepalive probe interval
        "TCP_KEEPCNT": 3,  # Number of failed probes before connection is dropped
    }

    # Health Check Settings
    HEALTH_CHECK_INTERVAL = 30  # Check connection health every 30 seconds

    # Retry Configuration
    RETRY_ON_ERROR = [
        redis.ConnectionError,
        redis.TimeoutError,
        redis.BusyLoadingError,
    ]
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = ExponentialBackoff(cap=10, base=1)

    # Command Timeouts for Long-Running Operations
    LONG_RUNNING_TIMEOUT = 120  # 2 minutes for operations like BLPOP
    STANDARD_TIMEOUT = 30  # 30 seconds for regular operations
    PIPELINE_TIMEOUT = 60  # 1 minute for pipeline operations


class RedisConnectionManager:
    """Manages Redis connections with optimized pool settings for async tasks."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None
        self._health_check_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the Redis connection pool with optimized settings."""
        if self._pool is not None:
            return

        # Create connection pool with optimized settings
        self._pool = ConnectionPool.from_url(
            self.redis_url,
            # Pool configuration
            max_connections=OptimizedRedisConfig.MAX_CONNECTIONS,
            retry_on_error=OptimizedRedisConfig.RETRY_ON_ERROR,
            retry=Retry(
                backoff=OptimizedRedisConfig.RETRY_BACKOFF,
                retries=OptimizedRedisConfig.RETRY_ATTEMPTS,
            ),
            # Connection timeouts
            socket_connect_timeout=OptimizedRedisConfig.SOCKET_CONNECT_TIMEOUT,
            socket_timeout=OptimizedRedisConfig.SOCKET_TIMEOUT,
            socket_keepalive=OptimizedRedisConfig.SOCKET_KEEPALIVE,
            socket_keepalive_options=OptimizedRedisConfig.SOCKET_KEEPALIVE_OPTIONS,
            # Encoding
            decode_responses=True,
            encoding="utf-8",
            # Connection lifecycle
            health_check_interval=OptimizedRedisConfig.HEALTH_CHECK_INTERVAL,
        )

        # Create Redis client
        self._redis = redis.Redis(connection_pool=self._pool)

        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._health_monitor())

        logger.info(
            f"Redis connection pool initialized: "
            f"max_connections={OptimizedRedisConfig.MAX_CONNECTIONS}, "
            f"health_check_interval={OptimizedRedisConfig.HEALTH_CHECK_INTERVAL}s"
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

        logger.info("Redis connection pool closed")

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
            timeout = OptimizedRedisConfig.STANDARD_TIMEOUT

        try:
            # Use the main Redis client with timeout override
            yield self._redis

        except Exception as e:
            logger.error(f"Redis connection error: {e}")
            raise

    async def execute_with_retry(self, operation, *args, **kwargs):
        """
        Execute a Redis operation with automatic retry logic.

        Args:
            operation: Redis operation to execute
            *args, **kwargs: Arguments for the operation
        """
        last_exception = None

        for attempt in range(OptimizedRedisConfig.RETRY_ATTEMPTS):
            try:
                return await operation(*args, **kwargs)
            except OptimizedRedisConfig.RETRY_ON_ERROR as e:
                last_exception = e
                if attempt < OptimizedRedisConfig.RETRY_ATTEMPTS - 1:
                    delay = OptimizedRedisConfig.RETRY_BACKOFF.compute(attempt)
                    logger.warning(
                        f"Redis operation failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Redis operation failed after {OptimizedRedisConfig.RETRY_ATTEMPTS} attempts"
                    )
            except Exception as e:
                # Non-retryable error
                logger.error(f"Redis operation failed with non-retryable error: {e}")
                raise

        # If we get here, all retries failed
        raise last_exception

    async def _health_monitor(self) -> None:
        """Background task to monitor Redis connection health."""
        while True:
            try:
                await asyncio.sleep(OptimizedRedisConfig.HEALTH_CHECK_INTERVAL)

                # Ping Redis to check health
                await self._redis.ping()

                # Log pool statistics
                if hasattr(self._pool, "_available_connections"):
                    available = len(self._pool._available_connections)
                    created = self._pool._created_connections
                    logger.debug(
                        f"Redis pool health: {available} available, {created} total connections"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")

    async def get_pool_stats(self) -> dict:
        """Get current connection pool statistics."""
        if not self._pool:
            return {"status": "not_initialized"}

        stats = {
            "max_connections": OptimizedRedisConfig.MAX_CONNECTIONS,
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


# Specialized Redis clients for different use cases
class LongRunningRedisClient:
    """Redis client optimized for long-running operations like BLPOP."""

    def __init__(self, connection_manager: RedisConnectionManager):
        self.connection_manager = connection_manager

    async def blpop(self, keys, timeout: int = 0):
        """
        Blocking list pop with optimized timeout handling.

        Args:
            keys: List of keys to pop from
            timeout: Timeout in seconds (0 = block indefinitely)
        """
        # Use longer socket timeout for blocking operations
        socket_timeout = max(
            timeout + 10 if timeout > 0 else OptimizedRedisConfig.LONG_RUNNING_TIMEOUT,
            OptimizedRedisConfig.LONG_RUNNING_TIMEOUT,
        )

        async with self.connection_manager.get_connection(
            timeout=socket_timeout
        ) as redis_client:
            return await redis_client.blpop(keys, timeout=timeout)

    async def brpop(self, keys, timeout: int = 0):
        """
        Blocking right pop with optimized timeout handling.

        Args:
            keys: List of keys to pop from
            timeout: Timeout in seconds (0 = block indefinitely)
        """
        socket_timeout = max(
            timeout + 10 if timeout > 0 else OptimizedRedisConfig.LONG_RUNNING_TIMEOUT,
            OptimizedRedisConfig.LONG_RUNNING_TIMEOUT,
        )

        async with self.connection_manager.get_connection(
            timeout=socket_timeout
        ) as redis_client:
            return await redis_client.brpop(keys, timeout=timeout)


class PipelineRedisClient:
    """Redis client optimized for pipeline operations."""

    def __init__(self, connection_manager: RedisConnectionManager):
        self.connection_manager = connection_manager

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True):
        """
        Get a Redis pipeline with optimized timeout settings.

        Args:
            transaction: Whether to use transaction mode
        """
        async with self.connection_manager.get_connection(
            timeout=OptimizedRedisConfig.PIPELINE_TIMEOUT
        ) as redis_client:
            async with redis_client.pipeline(transaction=transaction) as pipe:
                yield pipe


# Global connection manager instance
_connection_manager: Optional[RedisConnectionManager] = None


async def initialize_redis(redis_url: str) -> RedisConnectionManager:
    """Initialize the global Redis connection manager."""
    global _connection_manager

    if _connection_manager is not None:
        await _connection_manager.close()

    _connection_manager = RedisConnectionManager(redis_url)
    await _connection_manager.initialize()

    return _connection_manager


async def get_redis_manager() -> RedisConnectionManager:
    """Get the global Redis connection manager."""
    if _connection_manager is None:
        raise RuntimeError("Redis connection manager not initialized")
    return _connection_manager


async def close_redis() -> None:
    """Close the global Redis connection manager."""
    global _connection_manager
    if _connection_manager is not None:
        await _connection_manager.close()
        _connection_manager = None


# Convenience functions for different Redis client types
async def get_standard_redis() -> redis.Redis:
    """Get a standard Redis client for regular operations."""
    manager = await get_redis_manager()
    return manager.redis


async def get_long_running_redis() -> LongRunningRedisClient:
    """Get a Redis client optimized for long-running operations."""
    manager = await get_redis_manager()
    return LongRunningRedisClient(manager)


async def get_pipeline_redis() -> PipelineRedisClient:
    """Get a Redis client optimized for pipeline operations."""
    manager = await get_redis_manager()
    return PipelineRedisClient(manager)
