"""
Simplified Redis connection configuration with fallback compatibility.
"""

import asyncio
import logging
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SimpleRedisManager:
    """Simple Redis connection manager with basic optimization."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        
    async def initialize(self) -> None:
        """Initialize the Redis connection."""
        if self._redis is not None:
            return
            
        try:
            # Create a simple Redis connection with basic optimizations
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=30,
                socket_connect_timeout=10,
                socket_keepalive=True,
                socket_keepalive_options={
                    'TCP_KEEPIDLE': 600,
                    'TCP_KEEPINTVL': 60,
                    'TCP_KEEPCNT': 3
                },
                max_connections=50,
                retry_on_error=[
                    redis.ConnectionError,
                    redis.TimeoutError,
                ]
            )
            
            # Test the connection
            await self._redis.ping()
            
            logger.info("Simple Redis connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            # Create a basic connection as fallback
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
    
    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self._redis = None
            
        logger.info("Redis connection closed")
    
    @property
    def redis(self) -> redis.Redis:
        """Get the Redis client instance."""
        if self._redis is None:
            raise RuntimeError("Redis connection not initialized. Call initialize() first.")
        return self._redis
    
    async def ping(self) -> bool:
        """Test Redis connectivity."""
        try:
            if self._redis is None:
                await self.initialize()
            result = await self._redis.ping()
            return result is True or result == b'PONG' or result == 'PONG'
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def get_pool_stats(self) -> dict:
        """Get basic connection statistics."""
        if not self._redis:
            return {"status": "not_initialized"}
        
        try:
            # Test connection
            is_connected = await self.ping()
            return {
                "status": "connected" if is_connected else "disconnected",
                "max_connections": 50,  # Our configured max
                "created_connections": 1,  # Simple client uses single connection
                "available_connections": 1 if is_connected else 0,
                "in_use_connections": 0 if is_connected else 1,
                "connection_type": "simple_redis_client",
                "fallback_mode": True
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "connection_type": "simple_redis_client",
                "fallback_mode": True
            }


# Global connection manager instance
_simple_manager: Optional[SimpleRedisManager] = None


async def initialize_simple_redis(redis_url: str) -> SimpleRedisManager:
    """Initialize the simple Redis connection manager."""
    global _simple_manager
    
    if _simple_manager is not None:
        await _simple_manager.close()
    
    _simple_manager = SimpleRedisManager(redis_url)
    await _simple_manager.initialize()
    
    return _simple_manager


async def get_simple_redis_manager() -> SimpleRedisManager:
    """Get the simple Redis connection manager."""
    if _simple_manager is None:
        raise RuntimeError("Simple Redis connection manager not initialized")
    return _simple_manager


async def close_simple_redis() -> None:
    """Close the simple Redis connection manager."""
    global _simple_manager
    if _simple_manager is not None:
        await _simple_manager.close()
        _simple_manager = None


async def get_simple_redis() -> redis.Redis:
    """Get a simple Redis client for operations."""
    manager = await get_simple_redis_manager()
    return manager.redis
