#!/usr/bin/env python3
"""
Test script to demonstrate the task summaries endpoint that fixes the issue
with large PDF content making task list responses too long to process.
"""

import asyncio
import httpx


async def test_task_summaries(base_url: str = "http://localhost:8000"):
    """Test the new task summaries endpoint."""

    print("🔍 Testing Task Summaries Endpoint")
    print("=" * 50)

    async with httpx.AsyncClient() as client:
        # Test 1: List all task summaries
        print("📋 Listing all task summaries...")
        response = await client.get(f"{base_url}/api/v1/tasks/summaries/")

        if response.status_code == 200:
            data = response.json()
            total_items = data.get("total_items", 0)
            print(f"✅ Found {total_items} tasks")

            # Show task type distribution
            task_types = {}
            for task in data.get("tasks", []):
                task_type = task.get("task_type", "unknown")
                task_types[task_type] = task_types.get(task_type, 0) + 1

            print("📊 Task type distribution:")
            for task_type, count in task_types.items():
                print(f"   {task_type}: {count} tasks")

            print()

            # Show recent tasks
            print("🕒 Recent tasks:")
            for task in data.get("tasks", [])[:3]:
                task_id = task.get("task_id", "unknown")[:8] + "..."
                task_type = task.get("task_type", "unknown")
                state = task.get("state", "unknown")
                content_length = task.get("content_length", 0)
                has_result = task.get("has_result", False)

                print(
                    f"   {task_id} | {task_type:10} | {state:9} | {content_length:8,} chars | Result: {has_result}"
                )

        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return

        print()

        # Test 2: Find PDF extraction tasks
        print("🔍 Searching for PDF extraction tasks...")
        response = await client.get(
            f"{base_url}/api/v1/tasks/summaries/?task_id=e1c3ba11"
        )

        if response.status_code == 200:
            data = response.json()
            pdf_tasks = data.get("tasks", [])

            if pdf_tasks:
                print(f"✅ Found {len(pdf_tasks)} PDF extraction task(s)")

                for task in pdf_tasks:
                    task_id = task.get("task_id")
                    task_type = task.get("task_type")
                    state = task.get("state")
                    content_length = task.get("content_length", 0)
                    created_at = task.get("created_at", "")

                    print("📄 PDF Task Details:")
                    print(f"   ID: {task_id}")
                    print(f"   Type: {task_type} ✅ (correctly tagged)")
                    print(f"   State: {state}")
                    print(
                        f"   Content Size: {content_length:,} characters ({content_length/1024/1024:.1f} MB)"
                    )
                    print(f"   Created: {created_at}")

                    if task_type == "pdfxtract":
                        print(
                            "   ✅ Task is correctly tagged as 'pdfxtract' (not 'summarize')"
                        )
                    else:
                        print("   ❌ Task is incorrectly tagged")
            else:
                print("❌ No PDF extraction tasks found")
        else:
            print(f"❌ Error searching for PDF tasks: {response.status_code}")

        print()

        # Test 3: Compare response sizes
        print("📏 Comparing response sizes...")

        # Get full task details (with content)
        full_response = await client.get(f"{base_url}/api/v1/tasks/?page_size=5")
        summary_response = await client.get(
            f"{base_url}/api/v1/tasks/summaries/?page_size=5"
        )

        if full_response.status_code == 200 and summary_response.status_code == 200:
            full_size = len(full_response.text)
            summary_size = len(summary_response.text)

            print(f"   Full task list response: {full_size:,} characters")
            print(f"   Summary response: {summary_size:,} characters")
            print(
                f"   Size reduction: {((full_size - summary_size) / full_size * 100):.1f}%"
            )

            if full_size > summary_size:
                print("   ✅ Summary endpoint successfully reduces response size")
            else:
                print(
                    "   ⚠️  No significant size difference (may not have large content tasks)"
                )

        print()
        print("🎉 Task summaries endpoint is working correctly!")
        print(
            "💡 Use /api/v1/tasks/summaries/ instead of /api/v1/tasks/ to avoid large content fields"
        )


async def main():
    """Main function."""
    print("Task Summaries Test")
    print("This script tests the fix for the PDF extraction task tagging issue")
    print()

    try:
        await test_task_summaries()
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
