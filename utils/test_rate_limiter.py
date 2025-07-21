#!/usr/bin/env python3
"""
Test script for the distributed rate limiter functionality.
"""

import asyncio
import time
from datetime import datetime

# Add the worker directory to the path so we can import the rate limiter
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "worker"))

from rate_limiter import global_rate_limiter, get_rate_limit_status


async def test_rate_limiter_basic():
    """Test basic rate limiter functionality."""
    print("🧪 Testing Distributed Rate Limiter")
    print("=" * 50)

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
    print(
        f"   Config: {status['config']['requests']} requests per {status['config']['interval']}"
    )

    # Test acquiring tokens
    print("\n🔄 Testing token acquisition:")
    for i in range(7):  # Try to get more tokens than capacity
        start_time = time.time()
        success = await global_rate_limiter.acquire(1, timeout=2.0)
        elapsed = time.time() - start_time

        if success:
            print(f"   Request {i+1}: ✅ Acquired token in {elapsed:.3f}s")
        else:
            print(f"   Request {i+1}: ❌ Timeout after {elapsed:.3f}s")

        # Show current status
        status = await get_rate_limit_status()
        print(
            f"      Remaining tokens: {status['current_tokens']:.2f} ({status['utilization_percent']:.1f}% utilized)"
        )

    print("\n📈 Final status:")
    status = await get_rate_limit_status()
    print(f"   Current tokens: {status['current_tokens']:.2f}")
    print(f"   Utilization: {status['utilization_percent']:.1f}%")


async def test_rate_limiter_with_openrouter_config():
    """Test rate limiter with actual OpenRouter configuration."""
    print("\n" + "=" * 50)
    print("🌐 Testing with OpenRouter Configuration")
    print("=" * 50)

    # Reset bucket
    await global_rate_limiter.reset_bucket()

    # Set OpenRouter configuration (230 requests per 10s)
    await global_rate_limiter.update_rate_limit_config(230, "10s")

    print("📊 OpenRouter configuration loaded:")
    status = await get_rate_limit_status()
    print(f"   Capacity: {status['capacity']} requests")
    print(f"   Refill rate: {status['refill_rate']:.2f} requests/second")
    print(f"   Max requests per second: {status['refill_rate']:.1f}")

    # Test burst requests
    print("\n🚀 Testing burst requests (simulating multiple workers):")
    burst_size = 10
    start_time = time.time()

    tasks = []
    for i in range(burst_size):
        task = asyncio.create_task(global_rate_limiter.acquire(1, timeout=5.0))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    successful = sum(1 for r in results if r)
    print(
        f"   Burst of {burst_size} requests: {successful} successful in {elapsed:.3f}s"
    )
    print(f"   Effective rate: {successful/elapsed:.2f} requests/second")

    # Show final status
    status = await get_rate_limit_status()
    print(f"   Remaining tokens: {status['current_tokens']:.2f}")
    print(f"   Utilization: {status['utilization_percent']:.1f}%")


async def test_rate_limiter_recovery():
    """Test rate limiter token recovery over time."""
    print("\n" + "=" * 50)
    print("⏰ Testing Token Recovery Over Time")
    print("=" * 50)

    # Use a smaller bucket for faster testing
    await global_rate_limiter.update_rate_limit_config(
        10, "5s"
    )  # 10 requests per 5 seconds

    # Exhaust the bucket
    print("🔥 Exhausting token bucket...")
    for i in range(10):
        success = await global_rate_limiter.acquire(1, timeout=0.1)
        if not success:
            break

    status = await get_rate_limit_status()
    print(f"   Tokens after exhaustion: {status['current_tokens']:.2f}")

    # Monitor recovery
    print("\n📈 Monitoring token recovery:")
    for i in range(6):  # Monitor for 6 seconds
        await asyncio.sleep(1)
        status = await get_rate_limit_status()
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(
            f"   [{timestamp}] Tokens: {status['current_tokens']:.2f} ({status['utilization_percent']:.1f}% utilized)"
        )


async def simulate_multiple_workers():
    """Simulate multiple workers competing for rate limit tokens."""
    print("\n" + "=" * 50)
    print("👥 Simulating Multiple Workers")
    print("=" * 50)

    # Reset and configure
    await global_rate_limiter.update_rate_limit_config(
        20, "10s"
    )  # 20 requests per 10 seconds

    async def worker_simulation(worker_id: int, requests: int):
        """Simulate a worker making multiple requests."""
        successful = 0
        failed = 0
        total_wait_time = 0

        for i in range(requests):
            start_time = time.time()
            success = await global_rate_limiter.acquire(1, timeout=3.0)
            wait_time = time.time() - start_time
            total_wait_time += wait_time

            if success:
                successful += 1
            else:
                failed += 1

            # Small delay between requests
            await asyncio.sleep(0.1)

        avg_wait = total_wait_time / requests
        print(
            f"   Worker {worker_id}: {successful} successful, {failed} failed, avg wait: {avg_wait:.3f}s"
        )
        return successful, failed, avg_wait

    # Start multiple workers
    num_workers = 5
    requests_per_worker = 8

    print(f"🚀 Starting {num_workers} workers, {requests_per_worker} requests each:")

    start_time = time.time()
    tasks = []
    for worker_id in range(num_workers):
        task = asyncio.create_task(
            worker_simulation(worker_id + 1, requests_per_worker)
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    # Aggregate results
    total_successful = sum(r[0] for r in results)
    total_failed = sum(r[1] for r in results)
    avg_wait_times = [r[2] for r in results]

    print("\n📊 Simulation Results:")
    print(f"   Total requests: {total_successful + total_failed}")
    print(f"   Successful: {total_successful}")
    print(f"   Failed: {total_failed}")
    print(
        f"   Success rate: {total_successful/(total_successful + total_failed)*100:.1f}%"
    )
    print(f"   Total time: {elapsed:.2f}s")
    print(f"   Effective rate: {total_successful/elapsed:.2f} requests/second")
    print(f"   Average wait time: {sum(avg_wait_times)/len(avg_wait_times):.3f}s")


async def main():
    """Run all rate limiter tests."""
    print("🎯 Distributed Rate Limiter Test Suite")
    print("=" * 60)

    try:
        await test_rate_limiter_basic()
        await test_rate_limiter_with_openrouter_config()
        await test_rate_limiter_recovery()
        await simulate_multiple_workers()

        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
