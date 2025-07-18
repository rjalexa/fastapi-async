#!/usr/bin/env python3
"""
API Endpoint Testing Utility for AsyncTaskFlow

This script exercises all API endpoints and checks if they return expected status codes.
It performs comprehensive testing of all routes including error conditions.
"""

import asyncio
import json
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

import httpx


class APITester:
    """Comprehensive API endpoint tester."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = None
        self.test_results = []
        self.created_task_ids = []  # Track created tasks for cleanup
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def test_endpoint(
        self, 
        method: str, 
        path: str, 
        expected_status: int = 200,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """Test a single endpoint and return results."""
        url = f"{self.base_url}{path}"
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(url, params=params)
            elif method.upper() == "POST":
                response = await self.client.post(url, json=json_data, params=params)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            success = response.status_code == expected_status
            
            result = {
                "method": method.upper(),
                "path": path,
                "url": url,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "success": success,
                "description": description,
                "timestamp": datetime.utcnow().isoformat(),
                "response_size": len(response.content),
            }
            
            # Add response data for successful requests (truncated for readability)
            if success and response.status_code < 400:
                try:
                    response_json = response.json()
                    # Truncate large responses
                    if isinstance(response_json, dict) and len(str(response_json)) > 500:
                        result["response_preview"] = str(response_json)[:500] + "..."
                    else:
                        result["response_preview"] = response_json
                except:
                    result["response_preview"] = response.text[:200] + "..." if len(response.text) > 200 else response.text
            else:
                result["error_detail"] = response.text[:200] + "..." if len(response.text) > 200 else response.text
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            result = {
                "method": method.upper(),
                "path": path,
                "url": url,
                "expected_status": expected_status,
                "actual_status": None,
                "success": False,
                "description": description,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
            }
            self.test_results.append(result)
            return result
    
    async def test_root_endpoints(self):
        """Test root and basic endpoints."""
        print("Testing root endpoints...")
        
        await self.test_endpoint("GET", "/", description="Root endpoint")
        
    async def test_health_endpoints(self):
        """Test all health check endpoints."""
        print("Testing health endpoints...")
        
        await self.test_endpoint("GET", "/health", description="Main health check")
        await self.test_endpoint("GET", "/ready", description="Readiness check")
        await self.test_endpoint("GET", "/live", description="Liveness check")
        await self.test_endpoint("GET", "/health/workers", description="Worker health check")
        await self.test_endpoint("POST", "/health/workers/reset-circuit-breaker", description="Reset circuit breakers")
    
    async def test_task_creation(self) -> Optional[str]:
        """Test task creation and return a task ID for further testing."""
        print("Testing task creation...")
        
        # Test summarization task creation
        task_data = {"content": "This is a test text for summarization. It should be processed by the worker system."}
        result = await self.test_endpoint(
            "POST", 
            "/api/v1/tasks/summarize/", 
            expected_status=201,
            json_data=task_data,
            description="Create summarization task"
        )
        
        # Extract task ID if successful
        task_id = None
        if result["success"] and "response_preview" in result:
            try:
                if isinstance(result["response_preview"], dict):
                    task_id = result["response_preview"].get("task_id")
                elif isinstance(result["response_preview"], str):
                    # Try to parse JSON from string
                    import json
                    data = json.loads(result["response_preview"])
                    task_id = data.get("task_id")
            except:
                pass
        
        if task_id:
            self.created_task_ids.append(task_id)
            print(f"  Created task: {task_id}")
        
        return task_id
    
    async def test_task_management(self, task_id: Optional[str] = None):
        """Test task management endpoints."""
        print("Testing task management endpoints...")
        
        if task_id:
            # Test getting specific task
            await self.test_endpoint("GET", f"/api/v1/tasks/{task_id}", description=f"Get task {task_id}")
            
            # Test retry task (this might fail if task isn't in FAILED state, which is expected)
            await self.test_endpoint(
                "POST", 
                f"/api/v1/tasks/{task_id}/retry", 
                expected_status=400,  # Expect 400 since task likely isn't failed yet
                json_data={"reset_retry_count": False},
                description=f"Retry task {task_id} (expected to fail)"
            )
            
            # Test delete task
            await self.test_endpoint("DELETE", f"/api/v1/tasks/{task_id}", description=f"Delete task {task_id}")
        else:
            # Test with a fake task ID
            fake_task_id = str(uuid.uuid4())
            await self.test_endpoint(
                "GET", 
                f"/api/v1/tasks/{fake_task_id}", 
                expected_status=404,
                description="Get non-existent task (expected 404)"
            )
        
        # Test listing tasks by status
        await self.test_endpoint(
            "GET", 
            "/api/v1/tasks/", 
            params={"status": "PENDING", "limit": 10},
            description="List pending tasks"
        )
        
        await self.test_endpoint(
            "GET", 
            "/api/v1/tasks/", 
            params={"status": "COMPLETED", "limit": 10},
            description="List completed tasks"
        )
        
        await self.test_endpoint(
            "GET", 
            "/api/v1/tasks/", 
            params={"status": "FAILED", "limit": 10},
            description="List failed tasks"
        )
        
        # Test without status parameter (should fail)
        await self.test_endpoint(
            "GET", 
            "/api/v1/tasks/", 
            expected_status=400,
            description="List tasks without status (expected 400)"
        )
        
        # Test requeue orphaned tasks
        await self.test_endpoint("POST", "/api/v1/tasks/requeue-orphaned", description="Requeue orphaned tasks")
    
    async def test_queue_endpoints(self):
        """Test queue monitoring endpoints."""
        print("Testing queue endpoints...")
        
        # Test queue status
        await self.test_endpoint("GET", "/api/v1/queues/status", description="Get queue status")
        
        # Test DLQ tasks
        await self.test_endpoint("GET", "/api/v1/queues/dlq", description="Get DLQ tasks")
        await self.test_endpoint(
            "GET", 
            "/api/v1/queues/dlq", 
            params={"limit": 50},
            description="Get DLQ tasks with limit"
        )
        
        # Test tasks in specific queues
        queue_names = ["primary", "retry", "scheduled", "dlq"]
        for queue_name in queue_names:
            await self.test_endpoint(
                "GET", 
                f"/api/v1/queues/{queue_name}/tasks",
                description=f"Get tasks in {queue_name} queue"
            )
            
            await self.test_endpoint(
                "GET", 
                f"/api/v1/queues/{queue_name}/tasks",
                params={"limit": 5},
                description=f"Get tasks in {queue_name} queue with limit"
            )
    
    async def test_error_conditions(self):
        """Test various error conditions."""
        print("Testing error conditions...")
        
        # Test invalid endpoints
        await self.test_endpoint(
            "GET", 
            "/api/v1/nonexistent", 
            expected_status=404,
            description="Non-existent endpoint (expected 404)"
        )
        
        # Test invalid task creation
        await self.test_endpoint(
            "POST", 
            "/api/v1/tasks/summarize/", 
            expected_status=422,
            json_data={"invalid_field": "test"},
            description="Create task with invalid payload (expected 422)"
        )
        
        # Test invalid queue name
        await self.test_endpoint(
            "GET", 
            "/api/v1/queues/invalid_queue/tasks",
            expected_status=422,
            description="Invalid queue name (expected 422)"
        )
    
    async def run_all_tests(self):
        """Run all endpoint tests."""
        print(f"Starting comprehensive API endpoint testing...")
        print(f"Base URL: {self.base_url}")
        print(f"Started at: {datetime.utcnow().isoformat()}")
        print("=" * 60)
        
        # Run all test suites
        await self.test_root_endpoints()
        await self.test_health_endpoints()
        
        # Create a task for testing task management
        task_id = await self.test_task_creation()
        
        # Wait a moment for task to be processed
        await asyncio.sleep(1)
        
        await self.test_task_management(task_id)
        await self.test_queue_endpoints()
        await self.test_error_conditions()
        
        print("=" * 60)
        print("Testing completed!")
    
    def print_summary(self):
        """Print test results summary."""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - successful_tests
        
        print(f"\nTest Summary:")
        print(f"Total endpoints tested: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {(successful_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    status_info = f"Expected {result['expected_status']}, got {result.get('actual_status', 'ERROR')}"
                    print(f"  ❌ {result['method']} {result['path']} - {status_info}")
                    if "error" in result:
                        print(f"     Error: {result['error']}")
                    elif "error_detail" in result:
                        print(f"     Detail: {result['error_detail']}")
        
        print(f"\nSuccessful Tests:")
        for result in self.test_results:
            if result["success"]:
                print(f"  ✅ {result['method']} {result['path']} - {result['actual_status']}")
    
    def save_detailed_results(self, filename: str = "api_test_results.json"):
        """Save detailed test results to JSON file."""
        with open(filename, "w") as f:
            json.dump({
                "test_run": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "base_url": self.base_url,
                    "total_tests": len(self.test_results),
                    "successful_tests": sum(1 for r in self.test_results if r["success"]),
                    "failed_tests": sum(1 for r in self.test_results if not r["success"]),
                },
                "results": self.test_results
            }, f, indent=2)
        print(f"\nDetailed results saved to: {filename}")


async def main():
    """Main function to run API tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test all AsyncTaskFlow API endpoints")
    parser.add_argument(
        "--url", 
        default="http://localhost:8000", 
        help="Base URL for the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--save-results", 
        action="store_true", 
        help="Save detailed results to JSON file"
    )
    parser.add_argument(
        "--quiet", 
        action="store_true", 
        help="Only show summary, not individual test progress"
    )
    
    args = parser.parse_args()
    
    # Redirect print if quiet mode
    if args.quiet:
        import io
        import contextlib
        
        # Capture prints during testing
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            async with APITester(args.url) as tester:
                await tester.run_all_tests()
        
        # Show summary
        tester.print_summary()
    else:
        async with APITester(args.url) as tester:
            await tester.run_all_tests()
            tester.print_summary()
    
    if args.save_results:
        tester.save_detailed_results()
    
    # Exit with error code if any tests failed
    failed_count = sum(1 for result in tester.test_results if not result["success"])
    if failed_count > 0:
        print(f"\n⚠️  {failed_count} tests failed!")
        sys.exit(1)
    else:
        print(f"\n🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
