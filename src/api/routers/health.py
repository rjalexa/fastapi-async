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


@router.get("/health/workers")
async def worker_health_check() -> dict:
    """
    Get detailed health from all workers including their circuit breaker status.

    Queries each worker directly for their internal circuit breaker state.
    """
    try:
        # Import the celery app from the API main module
        try:
            from main import celery_app
        except ImportError:
            return {
                "error": "Cannot connect to worker application - workers may not be running",
                "total_workers": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Use inspect to get stats from all active workers first
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        if not active_workers:
            return {
                "error": "No active workers found",
                "total_workers": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Use Celery's broadcast to send task to ALL workers
        try:
            # Send health check task with broadcast to reach all workers
            job_results = celery_app.control.broadcast(
                "get_worker_health", reply=True, timeout=5.0
            )

            worker_results = []
            if job_results:
                for result in job_results:
                    if result and isinstance(result, dict):
                        worker_results.append(result)

            # If broadcast didn't work, fall back to regular task
            if not worker_results:
                job = celery_app.send_task("get_worker_health")
                result = job.get(timeout=3.0)
                if result:
                    worker_results = [result]

        except Exception as e:
            # Final fallback
            try:
                job = celery_app.send_task("get_worker_health")
                result = job.get(timeout=3.0)
                worker_results = [result] if result else []
            except Exception:
                return {
                    "error": f"Failed to get worker responses: {str(e)}",
                    "total_workers": len(active_workers) if active_workers else 0,
                    "active_worker_names": list(active_workers.keys())
                    if active_workers
                    else [],
                    "timestamp": datetime.utcnow().isoformat(),
                }

        # Aggregate results
        total_workers = len(worker_results)
        healthy_workers = sum(1 for w in worker_results if w.get("status") == "healthy")

        circuit_breaker_states = {}
        for worker in worker_results:
            cb_state = worker.get("circuit_breaker", {}).get("state", "unknown")
            circuit_breaker_states[cb_state] = (
                circuit_breaker_states.get(cb_state, 0) + 1
            )

        return {
            "total_workers": total_workers,
            "healthy_workers": healthy_workers,
            "circuit_breaker_states": circuit_breaker_states,
            "worker_details": worker_results,
            "active_worker_names": list(active_workers.keys())
            if active_workers
            else [],
            "overall_status": "healthy"
            if healthy_workers == total_workers and total_workers > 0
            else "degraded",
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

        # Send reset task to all workers
        job = celery_app.send_task("reset_worker_circuit_breaker")

        try:
            results = job.get(timeout=5.0)
            if not isinstance(results, list):
                results = [results]
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
