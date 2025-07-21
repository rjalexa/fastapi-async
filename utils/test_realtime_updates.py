#!/usr/bin/env python3
"""
Test script for real-time queue updates.

This script connects to the Server-Sent Events endpoint and displays
real-time updates as they occur. Useful for testing the SSE functionality.
"""

import asyncio
import json
import sys
from datetime import datetime

import aiohttp


async def test_sse_stream():
    """Connect to the SSE endpoint and display real-time updates."""
    url = "http://localhost:8000/api/v1/queues/status/stream"

    print(f"Connecting to SSE stream: {url}")
    print("=" * 60)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"Error: HTTP {response.status}")
                    return

                print("Connected! Listening for updates...")
                print("Press Ctrl+C to stop\n")

                async for line in response.content:
                    line = line.decode("utf-8").strip()

                    if line.startswith("data: "):
                        data_json = line[6:]  # Remove 'data: ' prefix
                        try:
                            data = json.loads(data_json)
                            timestamp = datetime.now().strftime("%H:%M:%S")

                            print(f"[{timestamp}] {data.get('type', 'unknown')}")

                            if data.get("type") == "initial_status":
                                print("  Initial Status:")
                                print(f"    Queues: {data.get('queue_depths', {})}")
                                print(f"    States: {data.get('state_counts', {})}")
                                print(
                                    f"    Retry Ratio: {data.get('retry_ratio', 0):.2f}"
                                )

                            elif data.get("type") == "task_created":
                                print(
                                    f"  Task Created: {data.get('task_id', 'unknown')}"
                                )
                                print(
                                    f"    Queue Depths: {data.get('queue_depths', {})}"
                                )
                                print(
                                    f"    State Counts: {data.get('state_counts', {})}"
                                )

                            elif data.get("type") == "task_state_changed":
                                print(f"  Task: {data.get('task_id', 'unknown')}")
                                print(
                                    f"    State: {data.get('old_state', '?')} → {data.get('new_state', '?')}"
                                )
                                print(
                                    f"    Queue Depths: {data.get('queue_depths', {})}"
                                )
                                print(
                                    f"    State Counts: {data.get('state_counts', {})}"
                                )

                            elif data.get("type") == "heartbeat":
                                print("  Heartbeat received")

                            elif data.get("type") == "error":
                                print(
                                    f"  Error: {data.get('message', 'Unknown error')}"
                                )

                            else:
                                print(f"  Data: {data}")

                            print()  # Empty line for readability

                        except json.JSONDecodeError as e:
                            print(f"Failed to parse JSON: {e}")
                            print(f"Raw data: {data_json}")

                    elif line:
                        print(f"Non-data line: {line}")

    except KeyboardInterrupt:
        print("\nDisconnected by user")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("Real-time Queue Updates Test")
    print("Make sure the API server is running on localhost:8000")
    print()

    try:
        asyncio.run(test_sse_stream())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
