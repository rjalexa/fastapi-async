"""Health check API endpoints."""

from fastapi import APIRouter, HTTPException, status

from schemas import HealthStatus
from services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Comprehensive health check endpoint.

    Checks the status of:
    - Redis connectivity
    - Celery workers
    - Circuit breaker status

    Returns overall system health and component-specific status.
    """
    if not health_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health service not available",
        )

    try:
        health_data = await health_service.check_health()
        return HealthStatus(**health_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get("/ready")
async def readiness_check() -> dict:
    """
    Kubernetes-style readiness check.

    Returns 200 if the service is ready to accept traffic.
    """
    if not health_service:
        return {"status": "not ready", "reason": "Health service not available"}

    try:
        health_data = await health_service.check_health()
        if health_data["status"] == "healthy":
            return {"status": "ready"}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Readiness check failed: {str(e)}",
        )


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes-style liveness check.

    Returns 200 if the service is alive (basic functionality).
    """
    return {"status": "alive"}
