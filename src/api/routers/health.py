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

    Note: Circuit breaker status is available at /api/v1/workers/
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
