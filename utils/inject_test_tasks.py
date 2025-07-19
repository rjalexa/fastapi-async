#!/usr/bin/env python3
"""
Task Injection Utility for Frontend Testing

This script creates multiple test tasks to verify that the frontend
reacts properly to task creation and state changes. Useful for testing
real-time updates, queue monitoring, and dashboard responsiveness.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import List, Dict, Any
import uuid

import httpx


class TaskInjector:
    """Utility for injecting test tasks and monitoring frontend reactions."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = None
        self.created_tasks = []
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def create_task(self, content: str, task_number: int) -> Dict[str, Any]:
        """Create a single summarization task."""
        task_data = {
            "content": f"Test task #{task_number}: {content}"
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/tasks/summarize/",
                json=task_data
            )
            
            if response.status_code == 201:
                result = response.json()
                task_id = result.get("task_id")
                self.created_tasks.append({
                    "task_id": task_id,
                    "task_number": task_number,
                    "content": content,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "created"
                })
                return {
                    "success": True,
                    "task_id": task_id,
                    "task_number": task_number,
                    "response": result
                }
            else:
                return {
                    "success": False,
                    "task_number": task_number,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "task_number": task_number,
                "error": str(e)
            }
    
    async def inject_tasks(
        self, 
        count: int = 10, 
        delay_between: float = 0.5,
        batch_size: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Inject multiple test tasks.
        
        Args:
            count: Number of tasks to create
            delay_between: Delay in seconds between task creation
            batch_size: Number of tasks to create in each batch
        """
        print(f"Injecting {count} test tasks...")
        print(f"Delay between tasks: {delay_between}s")
        print(f"Batch size: {batch_size}")
        print(f"Target API: {self.base_url}")
        print("=" * 60)
        
        results = []
        
        # Generate varied test content
        test_contents = [
            "This is a comprehensive analysis of modern web development practices and their impact on user experience.",
            "Exploring the benefits of containerized applications in microservices architecture for scalable systems.",
            "Understanding the role of asynchronous task processing in building responsive web applications.",
            "A detailed examination of real-time data streaming and its applications in modern dashboard interfaces.",
            "Investigating the performance implications of different database indexing strategies in high-traffic applications.",
            "Analyzing the security considerations when implementing API authentication and authorization mechanisms.",
            "Evaluating the trade-offs between different frontend frameworks for building interactive user interfaces.",
            "Discussing the importance of monitoring and observability in distributed system architectures.",
            "Examining best practices for error handling and recovery in asynchronous processing systems.",
            "A comprehensive guide to implementing efficient caching strategies in web application development."
        ]
        
        for i in range(count):
            task_number = i + 1
            content = test_contents[i % len(test_contents)]
            
            print(f"Creating task {task_number}/{count}...")
            
            # Create tasks in batches
            if batch_size == 1:
                result = await self.create_task(content, task_number)
                results.append(result)
                
                if result["success"]:
                    print(f"  ✅ Task {task_number} created: {result['task_id']}")
                else:
                    print(f"  ❌ Task {task_number} failed: {result['error']}")
            else:
                # Batch creation (for future enhancement)
                result = await self.create_task(content, task_number)
                results.append(result)
                
                if result["success"]:
                    print(f"  ✅ Task {task_number} created: {result['task_id']}")
                else:
                    print(f"  ❌ Task {task_number} failed: {result['error']}")
            
            # Delay between tasks (except for the last one)
            if i < count - 1 and delay_between > 0:
                await asyncio.sleep(delay_between)
        
        return results
    
    async def monitor_task_progress(self, duration: int = 30) -> Dict[str, Any]:
        """
        Monitor the progress of created tasks for a specified duration.
        
        Args:
            duration: How long to monitor in seconds
        """
        if not self.created_tasks:
            return {"error": "No tasks to monitor"}
        
        print(f"\nMonitoring task progress for {duration} seconds...")
        print("=" * 60)
        
        start_time = datetime.utcnow()
        task_states = {}
        
        for elapsed in range(0, duration + 1, 5):  # Check every 5 seconds
            print(f"[{elapsed:02d}s] Checking task states...")
            
            for task_info in self.created_tasks:
                task_id = task_info["task_id"]
                
                try:
                    response = await self.client.get(f"{self.base_url}/api/v1/tasks/{task_id}")
                    
                    if response.status_code == 200:
                        task_data = response.json()
                        current_state = task_data.get("state", "UNKNOWN")
                        
                        # Track state changes
                        if task_id not in task_states:
                            task_states[task_id] = []
                        
                        if not task_states[task_id] or task_states[task_id][-1] != current_state:
                            task_states[task_id].append(current_state)
                            task_num = task_info["task_number"]
                            print(f"  Task {task_num} ({task_id[:8]}...): {current_state}")
                    
                except Exception as e:
                    print(f"  Error checking task {task_id}: {e}")
            
            if elapsed < duration:
                await asyncio.sleep(5)
        
        return {
            "monitoring_duration": duration,
            "task_states": task_states,
            "total_tasks": len(self.created_tasks)
        }
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/queues/status")
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": str(e)}
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print injection summary."""
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        print("\n" + "=" * 60)
        print("TASK INJECTION SUMMARY")
        print("=" * 60)
        print(f"Total tasks attempted: {len(results)}")
        print(f"Successfully created: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(results)*100):.1f}%")
        
        if successful > 0:
            print(f"\nCreated Task IDs:")
            for task_info in self.created_tasks:
                print(f"  Task {task_info['task_number']}: {task_info['task_id']}")
        
        if failed > 0:
            print(f"\nFailed Tasks:")
            for result in results:
                if not result["success"]:
                    print(f"  Task {result['task_number']}: {result['error']}")
    
    async def cleanup_tasks(self):
        """Clean up created tasks (optional)."""
        if not self.created_tasks:
            return
        
        print(f"\nCleaning up {len(self.created_tasks)} created tasks...")
        
        for task_info in self.created_tasks:
            task_id = task_info["task_id"]
            try:
                response = await self.client.delete(f"{self.base_url}/api/v1/tasks/{task_id}")
                if response.status_code == 200:
                    print(f"  ✅ Deleted task {task_info['task_number']}")
                else:
                    print(f"  ⚠️  Task {task_info['task_number']} delete returned {response.status_code}")
            except Exception as e:
                print(f"  ❌ Failed to delete task {task_info['task_number']}: {e}")


async def main():
    """Main function for task injection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Inject test tasks for frontend testing")
    parser.add_argument(
        "--count", 
        type=int, 
        default=10, 
        help="Number of tasks to create (default: 10)"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=0.5, 
        help="Delay between task creation in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--url", 
        default="http://localhost:8000", 
        help="Base URL for the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--monitor", 
        type=int, 
        default=0, 
        help="Monitor task progress for N seconds after creation (default: 0 = no monitoring)"
    )
    parser.add_argument(
        "--cleanup", 
        action="store_true", 
        help="Clean up created tasks after completion"
    )
    parser.add_argument(
        "--show-queue-status", 
        action="store_true", 
        help="Show queue status before and after injection"
    )
    
    args = parser.parse_args()
    
    print("AsyncTaskFlow Task Injection Utility")
    print(f"Target: {args.url}")
    print(f"Tasks to create: {args.count}")
    print(f"Delay between tasks: {args.delay}s")
    if args.monitor > 0:
        print(f"Monitoring duration: {args.monitor}s")
    print()
    
    async with TaskInjector(args.url) as injector:
        # Show initial queue status
        if args.show_queue_status:
            print("Initial queue status:")
            initial_status = await injector.get_queue_status()
            print(json.dumps(initial_status, indent=2))
            print()
        
        # Inject tasks
        results = await injector.inject_tasks(
            count=args.count,
            delay_between=args.delay
        )
        
        # Show final queue status
        if args.show_queue_status:
            print("\nFinal queue status:")
            final_status = await injector.get_queue_status()
            print(json.dumps(final_status, indent=2))
        
        # Monitor progress if requested
        if args.monitor > 0:
            monitoring_results = await injector.monitor_task_progress(args.monitor)
            print(f"\nMonitoring completed:")
            print(f"  Tracked {monitoring_results.get('total_tasks', 0)} tasks")
            print(f"  Monitoring duration: {monitoring_results.get('monitoring_duration', 0)}s")
        
        # Print summary
        injector.print_summary(results)
        
        # Cleanup if requested
        if args.cleanup:
            await injector.cleanup_tasks()
        
        # Exit with appropriate code
        failed_count = sum(1 for r in results if not r["success"])
        if failed_count > 0:
            print(f"\n⚠️  {failed_count} tasks failed to create!")
            sys.exit(1)
        else:
            print(f"\n🎉 All {len(results)} tasks created successfully!")
            if not args.cleanup:
                print("💡 Use --cleanup flag to automatically delete created tasks")
            sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
