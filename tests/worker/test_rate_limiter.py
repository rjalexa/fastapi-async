import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from worker.rate_limiter import RedisTokenBucketRateLimiter


class TestRedisTokenBucketRateLimiter:
    """Test cases for the RedisTokenBucketRateLimiter class."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.eval.return_value = [
            1,
            10.0,
            100.0,
            1.0,
        ]  # Success, tokens, capacity, refill_rate
        mock.hmget.return_value = ["10.0", str(time.time()), "100.0", "1.0"]
        mock.hset.return_value = True
        mock.delete.return_value = True
        mock.aclose.return_value = None
        return mock

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create a RedisTokenBucketRateLimiter instance with mocked Redis."""
        with patch("worker.rate_limiter.aioredis.from_url", return_value=mock_redis):
            return RedisTokenBucketRateLimiter()

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test RedisTokenBucketRateLimiter initialization."""
        limiter = RedisTokenBucketRateLimiter(
            redis_url="redis://test:6379", bucket_key="test:bucket"
        )

        assert limiter.redis_url == "redis://test:6379"
        assert limiter.bucket_key == "test:bucket"
        assert limiter.config_key == "openrouter:rate_limit_config"

    @pytest.mark.asyncio
    async def test_acquire_success(self, rate_limiter, mock_redis):
        """Test successful token acquisition."""
        # Mock successful acquisition
        mock_redis.eval.return_value = [1, 9.0, 100.0, 1.0]  # Success

        result = await rate_limiter.acquire(tokens=1, timeout=5.0)

        assert result is True
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_failure_timeout(self, rate_limiter, mock_redis):
        """Test token acquisition failure due to timeout."""
        # Mock failure with wait time
        mock_redis.eval.return_value = [0, 0.0, 100.0, 1.0, 2.0]  # Failure with 2s wait

        result = await rate_limiter.acquire(tokens=1, timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_with_wait(self, rate_limiter, mock_redis):
        """Test token acquisition with waiting."""
        # First call fails, second succeeds
        mock_redis.eval.side_effect = [
            [0, 0.0, 100.0, 1.0, 0.1],  # Failure with short wait
            [1, 9.0, 100.0, 1.0],  # Success
        ]

        with patch("asyncio.sleep") as mock_sleep:
            result = await rate_limiter.acquire(tokens=1, timeout=5.0)

        assert result is True
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bucket_status(self, rate_limiter, mock_redis):
        """Test getting bucket status."""
        current_time = time.time()
        mock_redis.hmget.side_effect = [
            ["10.0", str(current_time - 1), "100.0", "1.0"],  # bucket data
            ["230", "10s", str(current_time)],  # config data
        ]

        status = await rate_limiter.get_bucket_status()

        assert "current_tokens" in status
        assert "capacity" in status
        assert "refill_rate" in status
        assert "config" in status
        assert status["capacity"] == 100.0

    @pytest.mark.asyncio
    async def test_reset_bucket(self, rate_limiter, mock_redis):
        """Test resetting the token bucket."""
        await rate_limiter.reset_bucket()

        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_rate_limit_config(self, rate_limiter, mock_redis):
        """Test updating rate limit configuration."""
        await rate_limiter.update_rate_limit_config(requests=500, interval="30s")

        mock_redis.hset.assert_called_once()
        mock_redis.delete.assert_called_once()  # Reset bucket

    @pytest.mark.asyncio
    async def test_redis_connection_handling(self, rate_limiter, mock_redis):
        """Test Redis connection is properly closed."""
        # This test is no longer valid as we are not closing the connection after each call.
        pass

    @pytest.mark.asyncio
    async def test_lua_script_execution(self, rate_limiter, mock_redis):
        """Test that Lua script is executed with correct parameters."""
        await rate_limiter.acquire(tokens=5, timeout=10.0)

        # Verify Lua script was called with correct parameters
        mock_redis.eval.assert_called_once()
        call_args = mock_redis.eval.call_args

        # Check that tokens parameter (5) is passed
        assert "5" in str(call_args[0])  # tokens parameter
        assert call_args[0][1] == 2  # number of keys

    @pytest.mark.asyncio
    async def test_multiple_token_acquisition(self, rate_limiter, mock_redis):
        """Test acquiring multiple tokens at once."""
        mock_redis.eval.return_value = [1, 5.0, 100.0, 1.0]  # Success

        result = await rate_limiter.acquire(tokens=10, timeout=5.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_bucket_status_with_refill_calculation(
        self, rate_limiter, mock_redis
    ):
        """Test bucket status calculation with token refill."""
        past_time = time.time() - 10  # 10 seconds ago
        mock_redis.hmget.side_effect = [
            ["50.0", str(past_time), "100.0", "2.0"],  # 50 tokens, 2/sec refill rate
            ["230", "10s", str(time.time())],
        ]

        status = await rate_limiter.get_bucket_status()

        # Should have refilled tokens (50 + 10*2 = 70, capped at 100)
        assert status["current_tokens"] >= 50.0
        assert status["utilization_percent"] >= 0

    @pytest.mark.asyncio
    async def test_error_handling(self, rate_limiter, mock_redis):
        """Test error handling in Redis operations."""
        mock_redis.eval.side_effect = Exception("Redis error")

        with pytest.raises(Exception):
            await rate_limiter.acquire(tokens=1)

    @pytest.mark.asyncio
    async def test_concurrent_acquisitions(self, rate_limiter, mock_redis):
        """Test concurrent token acquisitions."""
        mock_redis.eval.return_value = [1, 9.0, 100.0, 1.0]  # Always succeed

        # Run multiple concurrent acquisitions
        tasks = [rate_limiter.acquire(tokens=1, timeout=5.0) for _ in range(5)]

        results = await asyncio.gather(*tasks)

        assert all(results)  # All should succeed
        assert mock_redis.eval.call_count == 5
