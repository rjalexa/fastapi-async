#!/usr/bin/env python3
"""
Simple test script for the distributed rate limiter functionality without Redis dependency.
"""

import asyncio
import time
from datetime import datetime

# Add the worker directory to the path so we can import the rate limiter
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "worker"))

# Import rate limiter components at the top
from rate_limiter import RedisTokenBucketRateLimiter, global_rate_limiter, get_rate_limit_status


# Mock Redis for testing
class MockRedis:
    def __init__(self):
        self.data = {}

    async def eval(self, script, num_keys, *args):
        # Simple mock implementation for testing
        bucket_key = args[0]
        current_time = float(args[2])
        tokens_requested = int(args[3])

        # Initialize bucket if not exists
        if bucket_key not in self.data:
            self.data[bucket_key] = {
                "tokens": 230,  # Start with full capacity
                "capacity": 230,
                "refill_rate": 23.0,  # 230 requests per 10 seconds
                "last_refill": current_time,
            }

        bucket = self.data[bucket_key]

        # Calculate refill
        time_elapsed = current_time - bucket["last_refill"]
        tokens_to_add = time_elapsed * bucket["refill_rate"]
        bucket["tokens"] = min(bucket["capacity"], bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = current_time

        # Check if we have enough tokens
        if bucket["tokens"] >= tokens_requested:
            bucket["tokens"] -= tokens_requested
            return [
                1,
                bucket["tokens"],
                bucket["capacity"],
                bucket["refill_rate"],
            ]  # Success
        else:
            tokens_needed = tokens_requested - bucket["tokens"]
            wait_time = tokens_needed / bucket["refill_rate"]
            return [
                0,
                bucket["tokens"],
                bucket["capacity"],
                bucket["refill_rate"],
                wait_time,
            ]  # Failure

    async def hmget(self, key, *fields):
        if key not in self.data:
            return [None] * len(fields)

        bucket = self.data[key]
        result = []
        for field in fields:
            result.append(
                str(bucket.get(field, 0)) if bucket.get(field) is not None else None
            )
        return result

    async def delete(self, key):
        if key in self.data:
            del self.data[key]

    async def hset(self, key, mapping):
        if key not in self.data:
            self.data[key] = {}
        self.data[key].update(mapping)

    async def aclose(self):
        pass


# Monkey patch the rate limiter to use our mock Redis
original_get_redis = RedisTokenBucketRateLimiter._get_redis_connection
mock_redis = MockRedis()


async def mock_get_redis_connection(self):
    return mock_redis


RedisTokenBucketRateLimiter._get_redis_connection = mock_get_redis_connection


async def test_basic_functionality():
    """Test basic rate limiter functionality with mock Redis."""
    print("🧪 Testing Basic Rate Limiter Functionality (Mock Redis)")
    print("=" * 60)

    # Reset bucket
    await global_rate_limiter.reset_bucket()

    print("📊 Testing token acquisition:")

    # Test acquiring tokens rapidly
    successful = 0
    failed = 0

    for i in range(10):
        start_time = time.time()
        success = await global_rate_limiter.acquire(1, timeout=0.1)  # Short timeout
        elapsed = time.time() - start_time

        if success:
            successful += 1
            print(f"   Request {i+1}: ✅ Acquired token in {elapsed:.3f}s")
        else:
            failed += 1
            print(f"   Request {i+1}: ❌ Timeout after {elapsed:.3f}s")

    print("\n📈 Results:")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Success rate: {successful/(successful + failed)*100:.1f}%")

    # Test status monitoring
    print("\n📊 Rate Limit Status:")
    try:
        status = await get_rate_limit_status()
        print(f"   Current tokens: {status['current_tokens']:.2f}")
        print(f"   Capacity: {status['capacity']}")
        print(f"   Refill rate: {status['refill_rate']:.2f} tokens/second")
        print(f"   Utilization: {status['utilization_percent']:.1f}%")
    except Exception as e:
        print(f"   Status check failed: {e}")


async def test_token_recovery():
    """Test token recovery over time."""
    print("\n" + "=" * 60)
    print("⏰ Testing Token Recovery")
    print("=" * 60)

    # Exhaust some tokens
    print("🔥 Using some tokens...")
    for i in range(5):
        await global_rate_limiter.acquire(1, timeout=0.1)

    print("\n📈 Monitoring token recovery:")
    for i in range(3):
        status = await get_rate_limit_status()
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"   [{timestamp}] Tokens: {status['current_tokens']:.2f}")

        if i < 2:  # Don't sleep after the last iteration
            await asyncio.sleep(1)


async def test_concurrent_access():
    """Test concurrent access simulation."""
    print("\n" + "=" * 60)
    print("👥 Testing Concurrent Access")
    print("=" * 60)

    async def worker_task(worker_id, num_requests):
        successful = 0
        for i in range(num_requests):
            if await global_rate_limiter.acquire(1, timeout=0.5):
                successful += 1
            await asyncio.sleep(0.1)  # Small delay between requests
        return successful

    # Start multiple concurrent workers
    num_workers = 3
    requests_per_worker = 5

    print(f"🚀 Starting {num_workers} workers, {requests_per_worker} requests each:")

    tasks = []
    for i in range(num_workers):
        task = asyncio.create_task(worker_task(i + 1, requests_per_worker))
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    total_successful = sum(results)
    total_requests = num_workers * requests_per_worker

    print("\n📊 Concurrent Access Results:")
    for i, successful in enumerate(results):
        print(f"   Worker {i+1}: {successful}/{requests_per_worker} successful")

    print(f"\n   Total: {total_successful}/{total_requests} successful")
    print(f"   Overall success rate: {total_successful/total_requests*100:.1f}%")


async def main():
    """Run all tests."""
    print("🎯 Distributed Rate Limiter Test Suite (Mock Redis)")
    print("=" * 70)

    try:
        await test_basic_functionality()
        await test_token_recovery()
        await test_concurrent_access()

        print("\n" + "=" * 70)
        print("✅ All tests completed successfully!")
        print("\nNote: This test uses a mock Redis implementation.")
        print(
            "For full testing with real Redis, ensure Redis is running and accessible."
        )

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
