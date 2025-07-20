#!/usr/bin/env python3
"""
Script to fix stuck ACTIVE tasks by moving them to FAILED state so they can be retried.
"""

import redis
import json
from datetime import datetime
import os

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def main():
    # Connect to Redis
    r = redis.from_url(REDIS_URL, decode_responses=True)
    
    print("Scanning for stuck ACTIVE tasks...")
    
    stuck_tasks = []
    
    # Scan all task keys
    for key in r.scan_iter("task:*"):
        task_data = r.hgetall(key)
        if task_data.get("state") == "ACTIVE":
            task_id = key.split(":", 1)[1]
            stuck_tasks.append((task_id, task_data))
    
    print(f"Found {len(stuck_tasks)} stuck ACTIVE tasks")
    
    if not stuck_tasks:
        print("No stuck tasks found!")
        return
    
    for task_id, task_data in stuck_tasks:
        print(f"\nProcessing stuck task: {task_id}")
        print(f"  Started at: {task_data.get('started_at', 'unknown')}")
        print(f"  Worker ID: {task_data.get('worker_id', 'unknown')}")
        
        # Update task state to FAILED so it can be retried
        current_time = datetime.utcnow().isoformat()
        
        # Get current error history
        error_history = []
        if task_data.get("error_history"):
            try:
                error_history = json.loads(task_data["error_history"])
            except (json.JSONDecodeError, TypeError):
                error_history = []
        
        # Add error entry for stuck task
        error_entry = {
            "timestamp": current_time,
            "error": "Task was stuck in ACTIVE state - likely due to worker circuit breaker or crash",
            "error_type": "StuckTask",
            "retry_count": int(task_data.get("retry_count", 0)),
            "state_transition": "ACTIVE -> FAILED"
        }
        error_history.append(error_entry)
        
        # Update task fields
        fields = {
            "state": "FAILED",
            "updated_at": current_time,
            "failed_at": current_time,
            "last_error": "Task was stuck in ACTIVE state - likely due to worker circuit breaker or crash",
            "error_type": "StuckTask",
            "error_history": json.dumps(error_history)
        }
        
        # Update task data and counters atomically
        with r.pipeline(transaction=True) as pipe:
            # Update task data
            pipe.hset(f"task:{task_id}", mapping=fields)
            
            # Update state counters
            pipe.decrby("metrics:tasks:state:active", 1)
            pipe.incrby("metrics:tasks:state:failed", 1)
            
            pipe.execute()
        
        # Add to retry queue for reprocessing
        r.lpush("tasks:pending:retry", task_id)
        
        print(f"  ✅ Moved task {task_id} from ACTIVE to FAILED and queued for retry")
    
    print(f"\n🎉 Successfully processed {len(stuck_tasks)} stuck tasks")
    print("Tasks have been moved to FAILED state and queued for retry")

if __name__ == "__main__":
    main()
