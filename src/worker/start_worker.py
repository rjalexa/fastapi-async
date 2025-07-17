#!/usr/bin/env python3
"""Enhanced Celery worker startup script with monitoring enabled."""

import os
from tasks import app

if __name__ == "__main__":
    # Enable management commands for Flower
    os.environ.setdefault("CELERY_ENABLE_REMOTE_CONTROL", "true")

    # Start worker with enhanced options for monitoring
    argv = [
        "celery",
        "-A",
        "tasks",
        "worker",
        "--loglevel=info",
        f'--concurrency={os.getenv("CELERY_WORKER_CONCURRENCY", "4")}',
        "--without-gossip",  # Reduce network chatter
        "--without-mingle",  # Faster startup
        "--without-heartbeat",  # Reduce heartbeat overhead
        "--enable-events",  # Enable task events for Flower
    ]

    # Add hostname for better identification
    hostname = os.getenv("HOSTNAME", f"worker-{os.getpid()}")
    argv.extend(["--hostname", f"{hostname}@%h"])

    # Execute with the configured arguments
    app.worker_main(argv)
