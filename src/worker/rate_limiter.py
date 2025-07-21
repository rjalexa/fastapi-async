#!/usr/bin/env python3
"""
Distributed Rate Limiter for OpenRouter API

This module implements a Redis-based token bucket rate limiter that coordinates
rate limiting across multiple Celery workers to respect OpenRouter's API limits.
"""

import asyncio
import time
from typing import Dict, Any
import redis.asyncio as aioredis
from config import settings


class RedisTokenBucketRateLimiter:
    """
    Distributed token bucket rate limiter using Redis.

    This implementation uses Redis Lua scripts to ensure atomic operations
    and prevent race conditions between multiple workers.
    """

    def __init__(
        self, redis_url: str = None, bucket_key: str = "openrouter:rate_limit:bucket"
    ):
        """
        Initialize the rate limiter.

        Args:
            redis_url: Redis connection URL (defaults to settings.redis_url)
            bucket_key: Redis key for the token bucket
        """
        self.redis_url = redis_url or settings.redis_url
        self.bucket_key = bucket_key
        self.config_key = "openrouter:rate_limit_config"

        # Lua script for atomic token bucket operations
        self.lua_script = """
        local bucket_key = KEYS[1]
        local config_key = KEYS[2]
        local current_time = tonumber(ARGV[1])
        local tokens_requested = tonumber(ARGV[2])
        
        -- Get current bucket state
        local bucket_data = redis.call('HMGET', bucket_key, 'tokens', 'last_refill', 'capacity', 'refill_rate')
        local tokens = tonumber(bucket_data[1]) or 0
        local last_refill = tonumber(bucket_data[2]) or current_time
        local capacity = tonumber(bucket_data[3]) or 0
        local refill_rate = tonumber(bucket_data[4]) or 0
        
        -- If capacity is 0, try to load from config
        if capacity == 0 then
            local config_data = redis.call('HMGET', config_key, 'requests', 'interval')
            local requests = tonumber(config_data[1]) or 230
            local interval = config_data[2] or '10s'
            
            -- Parse interval (e.g., "10s" -> 10)
            local interval_seconds = 10
            if interval then
                local num = string.match(interval, '(%d+)')
                if num then
                    interval_seconds = tonumber(num)
                end
            end
            
            capacity = requests
            refill_rate = requests / interval_seconds
            tokens = capacity  -- Start with full bucket
        end
        
        -- Calculate tokens to add based on time elapsed
        local time_elapsed = current_time - last_refill
        local tokens_to_add = time_elapsed * refill_rate
        tokens = math.min(capacity, tokens + tokens_to_add)
        
        -- Check if we have enough tokens
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            
            -- Update bucket state
            redis.call('HMSET', bucket_key, 
                'tokens', tokens,
                'last_refill', current_time,
                'capacity', capacity,
                'refill_rate', refill_rate
            )
            
            -- Set expiration (cleanup after 1 hour of inactivity)
            redis.call('EXPIRE', bucket_key, 3600)
            
            return {1, tokens, capacity, refill_rate}  -- Success
        else
            -- Not enough tokens, calculate wait time
            local tokens_needed = tokens_requested - tokens
            local wait_time = tokens_needed / refill_rate
            
            -- Update bucket state (even on failure, to track refill time)
            redis.call('HMSET', bucket_key, 
                'tokens', tokens,
                'last_refill', current_time,
                'capacity', capacity,
                'refill_rate', refill_rate
            )
            
            redis.call('EXPIRE', bucket_key, 3600)
            
            return {0, tokens, capacity, refill_rate, wait_time}  -- Failure with wait time
        end
        """

    async def _get_redis_connection(self) -> aioredis.Redis:
        """Get an async Redis connection."""
        return aioredis.from_url(self.redis_url, decode_responses=True)

    async def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire (default: 1)
            timeout: Maximum time to wait for tokens (seconds)

        Returns:
            True if tokens were acquired, False if timeout occurred

        Raises:
            Exception: If Redis operation fails
        """
        redis_conn = await self._get_redis_connection()

        try:
            start_time = time.time()

            while time.time() - start_time < timeout:
                current_time = time.time()

                # Execute the Lua script
                result = await redis_conn.eval(
                    self.lua_script,
                    2,  # Number of keys
                    self.bucket_key,
                    self.config_key,
                    current_time,
                    tokens,
                )

                success = bool(result[0])

                if success:
                    return True

                # Calculate wait time (result[4] contains wait time if available)
                if len(result) > 4:
                    wait_time = float(result[4])
                    # Cap wait time to remaining timeout
                    remaining_timeout = timeout - (time.time() - start_time)
                    actual_wait = min(wait_time, remaining_timeout)

                    if actual_wait > 0:
                        await asyncio.sleep(actual_wait)
                    else:
                        break
                else:
                    # Fallback: short wait
                    await asyncio.sleep(0.1)

            return False  # Timeout occurred

        finally:
            await redis_conn.aclose()

    async def get_bucket_status(self) -> Dict[str, Any]:
        """
        Get current bucket status for monitoring.

        Returns:
            Dictionary with bucket status information
        """
        redis_conn = await self._get_redis_connection()

        try:
            # Get bucket state
            bucket_data = await redis_conn.hmget(
                self.bucket_key, "tokens", "last_refill", "capacity", "refill_rate"
            )

            # Get rate limit config
            config_data = await redis_conn.hmget(
                self.config_key, "requests", "interval", "updated_at"
            )

            current_time = time.time()

            # Parse bucket data
            tokens = float(bucket_data[0]) if bucket_data[0] else 0
            last_refill = float(bucket_data[1]) if bucket_data[1] else current_time
            capacity = float(bucket_data[2]) if bucket_data[2] else 0
            refill_rate = float(bucket_data[3]) if bucket_data[3] else 0

            # Calculate current tokens (with refill)
            if refill_rate > 0:
                time_elapsed = current_time - last_refill
                tokens_to_add = time_elapsed * refill_rate
                current_tokens = min(capacity, tokens + tokens_to_add)
            else:
                current_tokens = tokens

            return {
                "current_tokens": current_tokens,
                "capacity": capacity,
                "refill_rate": refill_rate,
                "last_refill": last_refill,
                "utilization_percent": (1 - current_tokens / capacity) * 100
                if capacity > 0
                else 0,
                "config": {
                    "requests": config_data[0],
                    "interval": config_data[1],
                    "updated_at": config_data[2],
                },
                "timestamp": current_time,
            }

        finally:
            await redis_conn.aclose()

    async def reset_bucket(self) -> None:
        """Reset the token bucket to full capacity."""
        redis_conn = await self._get_redis_connection()

        try:
            await redis_conn.delete(self.bucket_key)
        finally:
            await redis_conn.aclose()

    async def update_rate_limit_config(self, requests: int, interval: str) -> None:
        """
        Manually update rate limit configuration.

        Args:
            requests: Number of requests allowed
            interval: Time interval (e.g., "10s", "1m")
        """
        redis_conn = await self._get_redis_connection()

        try:
            await redis_conn.hset(
                self.config_key,
                mapping={
                    "requests": str(requests),
                    "interval": interval,
                    "updated_at": time.time(),
                },
            )

            # Reset bucket to apply new configuration
            await self.reset_bucket()

        finally:
            await redis_conn.aclose()


# Global rate limiter instance
global_rate_limiter = RedisTokenBucketRateLimiter()


async def wait_for_rate_limit_token(tokens: int = 1, timeout: float = 30.0) -> bool:
    """
    Convenience function to acquire rate limit tokens.

    Args:
        tokens: Number of tokens to acquire
        timeout: Maximum wait time in seconds

    Returns:
        True if tokens were acquired, False if timeout
    """
    return await global_rate_limiter.acquire(tokens, timeout)


async def get_rate_limit_status() -> Dict[str, Any]:
    """Get current rate limit status for monitoring."""
    return await global_rate_limiter.get_bucket_status()


# Test function for development
async def test_rate_limiter():
    """Test the rate limiter functionality."""
    print("🧪 Testing Redis Token Bucket Rate Limiter")

    # Reset bucket for clean test
    await global_rate_limiter.reset_bucket()

    # Set test configuration (lower limits for testing)
    await global_rate_limiter.update_rate_limit_config(
        5, "10s"
    )  # 5 requests per 10 seconds

    print("📊 Initial status:")
    status = await get_rate_limit_status()
    print(f"   Capacity: {status['capacity']}")
    print(f"   Current tokens: {status['current_tokens']:.2f}")
    print(f"   Refill rate: {status['refill_rate']:.2f} tokens/second")

    # Test acquiring tokens
    print("\n🔄 Testing token acquisition:")
    for i in range(7):  # Try to get more tokens than capacity
        start_time = time.time()
        success = await wait_for_rate_limit_token(1, timeout=2.0)
        elapsed = time.time() - start_time

        if success:
            print(f"   Request {i+1}: ✅ Acquired token in {elapsed:.3f}s")
        else:
            print(f"   Request {i+1}: ❌ Timeout after {elapsed:.3f}s")

        # Show current status
        status = await get_rate_limit_status()
        print(f"      Remaining tokens: {status['current_tokens']:.2f}")

    print("\n📈 Final status:")
    status = await get_rate_limit_status()
    print(f"   Current tokens: {status['current_tokens']:.2f}")
    print(f"   Utilization: {status['utilization_percent']:.1f}%")


if __name__ == "__main__":
    asyncio.run(test_rate_limiter())
