#!/usr/bin/env python3
"""
Utility script to fix Redis counter synchronization issues.

This script scans all tasks in Redis and recalculates the state counters
to ensure they match the actual task states.
"""

import asyncio
import sys
from collections import defaultdict
from typing import Dict

import redis.asyncio as aioredis


async def fix_counter_sync(redis_url: str = "redis://localhost:6379") -> Dict[str, int]:
    """
    Fix Redis counter synchronization by recalculating all state counters.
    
    Returns:
        Dict with old and new counter values
    """
    redis_conn = aioredis.from_url(redis_url, decode_responses=True)
    
    try:
        # Get current counter values
        old_counters = {}
        for state in ["pending", "active", "completed", "failed", "scheduled", "dlq"]:
            key = f"metrics:tasks:state:{state}"
            value = await redis_conn.get(key)
            old_counters[state] = int(value) if value else 0
        
        # Count actual task states
        actual_counts = defaultdict(int)
        task_count = 0
        
        async for key in redis_conn.scan_iter("task:*"):
            task_count += 1
            state = await redis_conn.hget(key, "state")
            if state:
                actual_counts[state.lower()] += 1
        
        # Update counters to match actual states
        async with redis_conn.pipeline(transaction=True) as pipe:
            for state in ["pending", "active", "completed", "failed", "scheduled", "dlq"]:
                counter_key = f"metrics:tasks:state:{state}"
                actual_count = actual_counts.get(state, 0)
                await pipe.set(counter_key, actual_count)
            await pipe.execute()
        
        # Get new counter values
        new_counters = {}
        for state in ["pending", "active", "completed", "failed", "scheduled", "dlq"]:
            key = f"metrics:tasks:state:{state}"
            value = await redis_conn.get(key)
            new_counters[state] = int(value) if value else 0
        
        return {
            "total_tasks": task_count,
            "old_counters": old_counters,
            "new_counters": new_counters,
            "changes": {
                state: new_counters[state] - old_counters[state]
                for state in old_counters.keys()
                if new_counters[state] != old_counters[state]
            }
        }
        
    finally:
        await redis_conn.close()


async def main():
    """Main function to run the counter sync fix."""
    redis_url = sys.argv[1] if len(sys.argv) > 1 else "redis://localhost:6379"
    
    print("🔍 Analyzing Redis task state counters...")
    
    try:
        result = await fix_counter_sync(redis_url)
        
        print(f"\n📊 Analysis Results:")
        print(f"   Total tasks found: {result['total_tasks']}")
        
        print(f"\n📈 Counter Values:")
        print(f"   {'State':<12} {'Old':<6} {'New':<6} {'Change':<8}")
        print(f"   {'-'*12} {'-'*6} {'-'*6} {'-'*8}")
        
        for state in ["pending", "active", "completed", "failed", "scheduled", "dlq"]:
            old_val = result['old_counters'][state]
            new_val = result['new_counters'][state]
            change = new_val - old_val
            change_str = f"{change:+d}" if change != 0 else "0"
            print(f"   {state.upper():<12} {old_val:<6} {new_val:<6} {change_str:<8}")
        
        if result['changes']:
            print(f"\n✅ Fixed {len(result['changes'])} counter discrepancies:")
            for state, change in result['changes'].items():
                print(f"   - {state.upper()}: {change:+d}")
        else:
            print(f"\n✅ All counters were already synchronized!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
