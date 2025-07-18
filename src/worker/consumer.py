#!/usr/bin/env python3
"""
Consumer entry point for AsyncTaskFlow workers.
This starts the Redis queue consumer that pulls task IDs and dispatches them to workers.
"""

import logging
import signal
import sys
import time
from tasks import consume_tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down consumer...")
    sys.exit(0)

def main():
    """Main entry point for the consumer."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting AsyncTaskFlow Redis Queue Consumer")
    
    try:
        # Import the consumer logic directly
        import logging
        import redis
        import random
        import time
        import os
        from config import settings
        from tasks import app as celery_app, calculate_adaptive_retry_ratio
        
        logger.info("Starting Redis queue consumer...")
        
        # Use synchronous Redis for BLPOP
        redis_conn = redis.from_url(settings.redis_url, decode_responses=True)
        
        # Generate unique worker ID for heartbeat
        worker_id = f"worker-{os.getpid()}-{int(time.time())}"
        heartbeat_key = f"worker:heartbeat:{worker_id}"
        
        processed_count = 0
        last_heartbeat = 0
        
        while True:
            try:
                current_time = time.time()
                
                # Update heartbeat every 30 seconds
                if current_time - last_heartbeat > 30:
                    redis_conn.setex(heartbeat_key, 90, current_time)  # Expire after 90 seconds
                    last_heartbeat = current_time
                    logger.debug(f"Updated heartbeat for worker {worker_id}")
                
                # Get current retry queue depth for adaptive ratio
                retry_depth = redis_conn.llen("tasks:pending:retry")
                retry_ratio = calculate_adaptive_retry_ratio(retry_depth)
                
                # Decide which queue to check first based on retry ratio
                if random.random() > retry_ratio:
                    # Try primary queue first (70% of the time by default)
                    queues = ["tasks:pending:primary", "tasks:pending:retry"]
                else:
                    # Try retry queue first (30% of the time by default)
                    queues = ["tasks:pending:retry", "tasks:pending:primary"]
                
                # Use BLPOP to wait for a task ID from either queue (timeout: 5 seconds)
                result = redis_conn.blpop(queues, timeout=5)
                
                if result is None:
                    # Timeout occurred, continue loop (this is normal)
                    continue
                
                queue_name, task_id = result
                logger.info(f"Received task {task_id} from {queue_name}")
                
                # Now trigger the actual summarization task using the correct task name
                celery_app.send_task("summarize_text", args=[task_id])
                
                processed_count += 1
                logger.info(f"Dispatched task {task_id} for processing (total: {processed_count})")
                
            except redis.RedisError as e:
                logger.error(f"Redis error in consumer: {e}")
                time.sleep(5)  # Wait before retrying
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error in consumer: {e}")
                time.sleep(1)  # Brief pause before continuing
                continue
        
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except Exception as e:
        logger.error(f"Consumer failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
