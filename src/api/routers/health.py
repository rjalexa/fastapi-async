# src/api/routers/health.py
"""Health check API endpoints."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, status

from schemas import HealthStatus
from services import health_service

router = APIRouter(tags=["health"])


def get_health_service(request: Request):
    """Get health service from global variable or app state."""
    # Try global service first
    if health_service:
        return health_service

    # Fallback to app state (for reload mode)
    return getattr(request.app.state, "health_service", None)


@router.get("/health", response_model=HealthStatus)
async def health_check(request: Request) -> HealthStatus:
    """
    Comprehensive health check endpoint.

    Checks the status of:
    - Redis connectivity
    - Celery workers

    Returns overall system health and component-specific status.
    Always returns 200 with status details, never raises exceptions.

    Note: Circuit breaker status is available at /health/workers
    """
    current_health_service = get_health_service(request)

    if not current_health_service:
        return HealthStatus(
            status="unhealthy",
            components={
                "redis": False,
                "workers": False,
                "reason": "Health service not initialized",
            },
            timestamp=datetime.utcnow(),
        )

    try:
        health_data = await current_health_service.check_health()
        return HealthStatus(**health_data)
    except Exception as e:
        return HealthStatus(
            status="unhealthy",
            components={
                "redis": False,
                "workers": False,
                "error": str(e),
            },
            timestamp=datetime.utcnow(),
        )


@router.get("/health/workers")
async def worker_health_check(request: Request) -> dict:
    """
    Get detailed health from all workers based on Redis heartbeats.

    Uses Redis heartbeat keys to determine worker health status.
    """
    try:
        current_health_service = get_health_service(request)
        
        if not current_health_service:
            return {
                "error": "Health service not initialized",
                "total_workers": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Get all heartbeat keys
        heartbeat_keys = []
        async for key in current_health_service.redis_service.redis.scan_iter("worker:heartbeat:*"):
            heartbeat_keys.append(key)

        if not heartbeat_keys:
            return {
                "error": "No worker heartbeats found - workers may not be running",
                "total_workers": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Check each heartbeat
        import time
        current_time = time.time()
        worker_details = []
        healthy_workers = 0

        for key in heartbeat_keys:
            worker_id = key.split(":", 2)[2]  # Extract worker ID from key
            try:
                heartbeat_time = await current_health_service.redis_service.redis.get(key)
                if heartbeat_time:
                    heartbeat_timestamp = float(heartbeat_time)
                    age = current_time - heartbeat_timestamp
                    is_healthy = age < 60  # Consider healthy if heartbeat within last 60 seconds
                    
                    if is_healthy:
                        healthy_workers += 1
                    
                    worker_details.append({
                        "worker_id": worker_id,
                        "status": "healthy" if is_healthy else "stale",
                        "last_heartbeat": heartbeat_timestamp,
                        "heartbeat_age_seconds": round(age, 2),
                        "circuit_breaker": {
                            "state": "closed",  # Default assumption for Redis-based workers
                            "note": "Circuit breaker status not available via Redis heartbeat"
                        }
                    })
                else:
                    worker_details.append({
                        "worker_id": worker_id,
                        "status": "no_heartbeat",
                        "last_heartbeat": None,
                        "heartbeat_age_seconds": None,
                        "circuit_breaker": {
                            "state": "unknown"
                        }
                    })
            except (ValueError, TypeError) as e:
                worker_details.append({
                    "worker_id": worker_id,
                    "status": "error",
                    "error": str(e),
                    "circuit_breaker": {
                        "state": "unknown"
                    }
                })

        total_workers = len(worker_details)
        
        # Aggregate circuit breaker states
        circuit_breaker_states = {}
        for worker in worker_details:
            cb_state = worker.get("circuit_breaker", {}).get("state", "unknown")
            circuit_breaker_states[cb_state] = circuit_breaker_states.get(cb_state, 0) + 1

        return {
            "overall_status": "healthy" if healthy_workers == total_workers and total_workers > 0 else "degraded",
            "total_workers": total_workers,
            "healthy_workers": healthy_workers,
            "stale_workers": sum(1 for w in worker_details if w.get("status") == "stale"),
            "circuit_breaker_states": circuit_breaker_states,
            "worker_details": worker_details,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {
            "error": str(e),
            "total_workers": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.post("/health/workers/reset-circuit-breaker")
async def reset_all_circuit_breakers() -> dict:
    """
    Reset circuit breakers on all workers.

    Useful for manual recovery after resolving external service issues.
    """
    try:
        from main import celery_app

        # Use broadcast to send reset task to all workers
        job_results = celery_app.control.broadcast(
            "reset_worker_circuit_breaker", reply=True, timeout=5.0
        )

        results = []
        if job_results:
            for result in job_results:
                if result and isinstance(result, dict):
                    # Extract worker data from nested structure
                    for worker_name, worker_data in result.items():
                        if isinstance(worker_data, dict):
                            worker_data["worker_name"] = worker_name
                            results.append(worker_data)

        # If broadcast didn't work, fall back to regular task
        if not results:
            job = celery_app.send_task("reset_worker_circuit_breaker")
            try:
                result = job.get(timeout=5.0)
                if result:
                    results = [result]
            except Exception:
                results = []

        successful_resets = sum(1 for r in results if r.get("status") == "success")

        return {
            "message": f"Reset attempted on {len(results)} workers",
            "successful_resets": successful_resets,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes-style liveness check.

    Returns 200 if the service process is alive and responding.
    Should only return 503/5xx if the process should be restarted.

    This is a basic "is the web server responding" check.
    Used by Kubernetes to determine if the pod should be restarted.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
async def readiness_check(request: Request) -> dict:
    """
    Kubernetes-style readiness check.

    Returns 200 if the service is ready to accept traffic.
    Returns 503 if not ready (dependencies down, service not initialized).

    Used by load balancers to determine if traffic should be routed here.
    """
    current_health_service = get_health_service(request)

    if not current_health_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "reason": "Health service not initialized"},
        )

    try:
        health_data = await current_health_service.check_health()
        if health_data["status"] == "healthy":
            return {"status": "ready"}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "not ready",
                    "reason": "Dependencies unhealthy",
                    "components": health_data["components"],
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "reason": f"Health check failed: {str(e)}"},
        )
