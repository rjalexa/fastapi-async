#!/usr/bin/env python3
"""
DLQ Task Injection Utility for Frontend Testing

This script creates test tasks directly in the Dead Letter Queue (DLQ)
with proper metadata including error history, retry counts, and state transitions.
Useful for testing frontend DLQ handling, error display, and retry functionality.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid

import redis.asyncio as redis


class DLQTaskInjector:
    """Utility for injecting test tasks directly into the DLQ."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.created_tasks = []

    async def __aenter__(self):
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis:
            await self.redis.close()

    async def create_dlq_task(
        self, content: str, task_number: int, error_scenario: str
    ) -> Dict[str, Any]:
        """Create a single task directly in the DLQ with realistic error metadata."""
        task_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Create realistic error scenarios
        error_scenarios = {
            "timeout": {
                "error_type": "TimeoutError",
                "last_error": "Task execution timed out after 300 seconds. The external API did not respond within the configured timeout period.",
                "error_history": [
                    {
                        "error": "Connection timeout to external service",
                        "timestamp": (now - timedelta(hours=2)).isoformat(),
                        "retry_count": 1,
                    },
                    {
                        "error": "API rate limit exceeded, retrying after backoff",
                        "timestamp": (now - timedelta(hours=1, minutes=30)).isoformat(),
                        "retry_count": 2,
                    },
                    {
                        "error": "Task execution timed out after 300 seconds",
                        "timestamp": (now - timedelta(minutes=45)).isoformat(),
                        "retry_count": 3,
                    },
                ],
            },
            "api_error": {
                "error_type": "APIError",
                "last_error": "External API returned HTTP 503: Service temporarily unavailable. The summarization service is experiencing high load.",
                "error_history": [
                    {
                        "error": "HTTP 429: Too Many Requests",
                        "timestamp": (now - timedelta(hours=3)).isoformat(),
                        "retry_count": 1,
                    },
                    {
                        "error": "HTTP 502: Bad Gateway",
                        "timestamp": (now - timedelta(hours=2, minutes=15)).isoformat(),
                        "retry_count": 2,
                    },
                    {
                        "error": "HTTP 503: Service temporarily unavailable",
                        "timestamp": (now - timedelta(hours=1)).isoformat(),
                        "retry_count": 3,
                    },
                ],
            },
            "validation_error": {
                "error_type": "ValidationError",
                "last_error": "Content validation failed: Text contains unsupported characters or exceeds maximum length limit of 10,000 characters.",
                "error_history": [
                    {
                        "error": "Content too short for meaningful summarization",
                        "timestamp": (now - timedelta(hours=4)).isoformat(),
                        "retry_count": 1,
                    },
                    {
                        "error": "Invalid character encoding detected",
                        "timestamp": (now - timedelta(hours=3, minutes=30)).isoformat(),
                        "retry_count": 2,
                    },
                    {
                        "error": "Content exceeds maximum length limit",
                        "timestamp": (now - timedelta(hours=2, minutes=45)).isoformat(),
                        "retry_count": 3,
                    },
                ],
            },
        }

        scenario_data = error_scenarios.get(error_scenario, error_scenarios["timeout"])

        # Create comprehensive state history
        state_history = [
            {"state": "PENDING", "timestamp": (now - timedelta(hours=5)).isoformat()},
            {
                "state": "ACTIVE",
                "timestamp": (now - timedelta(hours=4, minutes=45)).isoformat(),
            },
            {
                "state": "FAILED",
                "timestamp": (now - timedelta(hours=4, minutes=30)).isoformat(),
            },
            {
                "state": "PENDING",
                "timestamp": (now - timedelta(hours=3, minutes=45)).isoformat(),
            },
            {
                "state": "ACTIVE",
                "timestamp": (now - timedelta(hours=3, minutes=30)).isoformat(),
            },
            {
                "state": "FAILED",
                "timestamp": (now - timedelta(hours=3, minutes=15)).isoformat(),
            },
            {
                "state": "PENDING",
                "timestamp": (now - timedelta(hours=2, minutes=30)).isoformat(),
            },
            {
                "state": "ACTIVE",
                "timestamp": (now - timedelta(hours=2, minutes=15)).isoformat(),
            },
            {"state": "FAILED", "timestamp": (now - timedelta(hours=2)).isoformat()},
            {"state": "DLQ", "timestamp": (now - timedelta(hours=1)).isoformat()},
        ]

        # Task metadata with comprehensive error information
        task_data = {
            "task_id": task_id,
            "content": f"Test DLQ task #{task_number}: {content}",
            "state": "DLQ",
            "retry_count": 3,  # Max retries reached
            "max_retries": 3,
            "last_error": scenario_data["last_error"],
            "error_type": scenario_data["error_type"],
            "retry_after": "",  # No more retries scheduled
            "created_at": (now - timedelta(hours=5)).isoformat(),
            "updated_at": (now - timedelta(hours=1)).isoformat(),
            "completed_at": "",  # Never completed
            "result": "",  # No result due to failure
            "error_history": json.dumps(scenario_data["error_history"]),
            "state_history": json.dumps(state_history),
        }

        try:
            # Use Redis transaction to ensure atomicity
            async with self.redis.pipeline(transaction=True) as pipe:
                # Store task metadata in both locations for compatibility
                await pipe.hset(f"task:{task_id}", mapping=task_data)
                await pipe.hset(f"dlq:task:{task_id}", mapping=task_data)

                # Add to DLQ queue
                await pipe.lpush("dlq:tasks", task_id)

                # Update state counters
                await pipe.incrby("metrics:tasks:state:dlq", 1)

                await pipe.execute()

            self.created_tasks.append(
                {
                    "task_id": task_id,
                    "task_number": task_number,
                    "content": content,
                    "error_scenario": error_scenario,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "injected_to_dlq",
                }
            )

            return {
                "success": True,
                "task_id": task_id,
                "task_number": task_number,
                "error_scenario": error_scenario,
                "message": f"Task {task_number} injected into DLQ with {scenario_data['error_type']} scenario",
            }

        except Exception as e:
            return {"success": False, "task_number": task_number, "error": str(e)}

    async def inject_dlq_tasks(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        Inject multiple test tasks directly into the DLQ.

        Args:
            count: Number of tasks to create (default: 3)
        """
        print(f"Injecting {count} test tasks directly into DLQ...")
        print(f"Redis URL: {self.redis_url}")
        print("=" * 60)

        results = []

        # Test content for DLQ tasks
        test_contents = [
            "This is a comprehensive analysis of modern web development practices that failed to process due to external service issues.",
            "Exploring the benefits of containerized applications in microservices architecture - this task encountered validation errors during processing.",
            "Understanding the role of asynchronous task processing in building responsive web applications - processing timed out multiple times.",
        ]

        # Error scenarios to simulate
        error_scenarios = ["timeout", "api_error", "validation_error"]

        for i in range(count):
            task_number = i + 1
            content = test_contents[i % len(test_contents)]
            error_scenario = error_scenarios[i % len(error_scenarios)]

            print(
                f"Creating DLQ task {task_number}/{count} with {error_scenario} scenario..."
            )

            result = await self.create_dlq_task(content, task_number, error_scenario)
            results.append(result)

            if result["success"]:
                print(f"  ✅ DLQ Task {task_number} created: {result['task_id']}")
                print(f"     Error scenario: {result['error_scenario']}")
            else:
                print(f"  ❌ DLQ Task {task_number} failed: {result['error']}")

            # Small delay between tasks
            await asyncio.sleep(0.1)

        return results

    async def get_dlq_status(self) -> Dict[str, Any]:
        """Get current DLQ status."""
        try:
            dlq_depth = await self.redis.llen("dlq:tasks")
            dlq_counter = await self.redis.get("metrics:tasks:state:dlq")
            dlq_counter = int(dlq_counter) if dlq_counter else 0

            return {
                "dlq_queue_depth": dlq_depth,
                "dlq_state_counter": dlq_counter,
                "status": "healthy",
            }
        except Exception as e:
            return {"error": str(e)}

    async def verify_dlq_tasks(self) -> Dict[str, Any]:
        """Verify that the injected tasks are properly stored in DLQ."""
        if not self.created_tasks:
            return {"error": "No tasks to verify"}

        print(f"\nVerifying {len(self.created_tasks)} DLQ tasks...")
        print("=" * 60)

        verification_results = []

        for task_info in self.created_tasks:
            task_id = task_info["task_id"]

            try:
                # Check if task exists in DLQ queue
                dlq_tasks = await self.redis.lrange("dlq:tasks", 0, -1)
                in_dlq_queue = task_id in dlq_tasks

                # Check if task metadata exists
                task_data = await self.redis.hgetall(f"task:{task_id}")
                dlq_task_data = await self.redis.hgetall(f"dlq:task:{task_id}")

                has_task_data = bool(task_data)
                has_dlq_data = bool(dlq_task_data)
                correct_state = task_data.get("state") == "DLQ" if task_data else False

                verification_results.append(
                    {
                        "task_id": task_id,
                        "task_number": task_info["task_number"],
                        "in_dlq_queue": in_dlq_queue,
                        "has_task_data": has_task_data,
                        "has_dlq_data": has_dlq_data,
                        "correct_state": correct_state,
                        "valid": in_dlq_queue and has_task_data and correct_state,
                    }
                )

                status = (
                    "✅" if (in_dlq_queue and has_task_data and correct_state) else "❌"
                )
                print(f"  {status} Task {task_info['task_number']} ({task_id[:8]}...)")
                print(f"     In DLQ queue: {in_dlq_queue}")
                print(f"     Has metadata: {has_task_data}")
                print(f"     Correct state: {correct_state}")

            except Exception as e:
                verification_results.append(
                    {
                        "task_id": task_id,
                        "task_number": task_info["task_number"],
                        "error": str(e),
                        "valid": False,
                    }
                )
                print(f"  ❌ Task {task_info['task_number']}: Verification error: {e}")

        valid_count = sum(1 for r in verification_results if r.get("valid", False))

        return {
            "total_tasks": len(self.created_tasks),
            "valid_tasks": valid_count,
            "verification_results": verification_results,
            "success_rate": (valid_count / len(self.created_tasks)) * 100
            if self.created_tasks
            else 0,
        }

    def print_summary(self, results: List[Dict[str, Any]]):
        """Print injection summary."""
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        print("\n" + "=" * 60)
        print("DLQ TASK INJECTION SUMMARY")
        print("=" * 60)
        print(f"Total DLQ tasks attempted: {len(results)}")
        print(f"Successfully created: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(results)*100):.1f}%")

        if successful > 0:
            print("\nCreated DLQ Task IDs:")
            for task_info in self.created_tasks:
                print(f"  Task {task_info['task_number']}: {task_info['task_id']}")
                print(f"    Error scenario: {task_info['error_scenario']}")

        if failed > 0:
            print("\nFailed Tasks:")
            for result in results:
                if not result["success"]:
                    print(f"  Task {result['task_number']}: {result['error']}")

    async def cleanup_dlq_tasks(self):
        """Clean up created DLQ tasks."""
        if not self.created_tasks:
            return

        print(f"\nCleaning up {len(self.created_tasks)} created DLQ tasks...")

        for task_info in self.created_tasks:
            task_id = task_info["task_id"]
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    # Remove from DLQ queue
                    await pipe.lrem("dlq:tasks", 0, task_id)
                    # Remove task metadata
                    await pipe.delete(f"task:{task_id}")
                    await pipe.delete(f"dlq:task:{task_id}")
                    # Decrement DLQ counter
                    await pipe.decrby("metrics:tasks:state:dlq", 1)
                    await pipe.execute()

                print(f"  ✅ Cleaned up DLQ task {task_info['task_number']}")
            except Exception as e:
                print(
                    f"  ❌ Failed to clean up DLQ task {task_info['task_number']}: {e}"
                )


async def main():
    """Main function for DLQ task injection."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Inject test tasks directly into DLQ for frontend testing"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of DLQ tasks to create (default: 3)",
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379",
        help="Redis URL (default: redis://localhost:6379)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that tasks were properly injected into DLQ",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up created DLQ tasks after completion",
    )
    parser.add_argument(
        "--show-dlq-status",
        action="store_true",
        help="Show DLQ status before and after injection",
    )

    args = parser.parse_args()

    print("AsyncTaskFlow DLQ Task Injection Utility")
    print(f"Redis: {args.redis_url}")
    print(f"DLQ tasks to create: {args.count}")
    print()

    async with DLQTaskInjector(args.redis_url) as injector:
        # Show initial DLQ status
        if args.show_dlq_status:
            print("Initial DLQ status:")
            initial_status = await injector.get_dlq_status()
            print(json.dumps(initial_status, indent=2))
            print()

        # Inject DLQ tasks
        results = await injector.inject_dlq_tasks(count=args.count)

        # Show final DLQ status
        if args.show_dlq_status:
            print("\nFinal DLQ status:")
            final_status = await injector.get_dlq_status()
            print(json.dumps(final_status, indent=2))

        # Verify tasks if requested
        if args.verify:
            verification_results = await injector.verify_dlq_tasks()
            print("\nVerification completed:")
            print(f"  Total tasks: {verification_results.get('total_tasks', 0)}")
            print(f"  Valid tasks: {verification_results.get('valid_tasks', 0)}")
            print(f"  Success rate: {verification_results.get('success_rate', 0):.1f}%")

        # Print summary
        injector.print_summary(results)

        # Cleanup if requested
        if args.cleanup:
            await injector.cleanup_dlq_tasks()

        # Exit with appropriate code
        failed_count = sum(1 for r in results if not r["success"])
        if failed_count > 0:
            print(f"\n⚠️  {failed_count} DLQ tasks failed to create!")
            sys.exit(1)
        else:
            print(f"\n🎉 All {len(results)} DLQ tasks created successfully!")
            if not args.cleanup:
                print("💡 Use --cleanup flag to automatically delete created DLQ tasks")
            print("💡 Use --verify flag to verify task injection")
            print("💡 Check your frontend to see the DLQ tasks in the UI")
            sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
