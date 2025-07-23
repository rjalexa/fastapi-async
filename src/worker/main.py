"""
Main Celery application module for the worker service.
This module creates and configures the Celery app instance.
"""

import os
from celery import Celery

# Create Celery app instance using environment variables directly
app = Celery(
    'asynctaskflow',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    include=['tasks']  # Include tasks module
)

# Configure Celery
app.conf.update(
    # Task routing
    task_routes={
        'tasks.*': {'queue': 'celery'},
    },
    
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Worker settings
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Task time limits
    task_time_limit=int(os.getenv('CELERY_TASK_TIME_LIMIT', '900')),  # 15 minutes hard limit
    task_soft_time_limit=int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '600')),  # 10 minutes soft limit
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Redis connection pool settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Task result settings
    result_backend_transport_options={
        'master_name': 'mymaster',
        'retry_on_timeout': True,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            'TCP_KEEPIDLE': 1,
            'TCP_KEEPINTVL': 3,
            'TCP_KEEPCNT': 5,
        },
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'process-scheduled-tasks': {
            'task': 'process_scheduled_tasks',
            'schedule': 30.0,  # Run every 30 seconds
            'options': {'queue': 'celery'}
        },
    },
)

# Health check task
@app.task(bind=True)
def health_check(self):
    """Simple health check task."""
    return {
        'status': 'healthy',
        'worker_id': self.request.id,
        'timestamp': str(app.now())
    }

if __name__ == '__main__':
    app.start()
