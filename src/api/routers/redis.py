"""Redis monitoring and statistics endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from src.api.services import RedisService

router = APIRouter(prefix="/api/v1/redis", tags=["redis"])


@router.get("/pool-stats")
async def get_redis_pool_stats() -> Dict[str, Any]:
    """
    Get Redis connection pool statistics.

    Returns detailed information about the current state of the Redis connection pool,
    including connection counts, utilization, and health status.
    """
    if not services.redis_service:
        raise HTTPException(status_code=503, detail="Redis service not available")

    try:
        # Get pool statistics from the Redis service
        pool_stats = await services.redis_service.get_pool_stats()

        # Add additional metadata
        pool_stats["status"] = (
            "healthy" if pool_stats.get("status") != "not_initialized" else "unhealthy"
        )

        # Calculate utilization percentage if we have the data
        if (
            pool_stats.get("max_connections")
            and pool_stats.get("in_use_connections") is not None
        ):
            utilization = (
                pool_stats["in_use_connections"] / pool_stats["max_connections"]
            ) * 100
            pool_stats["utilization_percent"] = round(utilization, 2)

        return {
            "pool_statistics": pool_stats,
            "recommendations": _get_pool_recommendations(pool_stats),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve Redis pool statistics: {str(e)}",
        )


@router.get("/health")
async def get_redis_health() -> Dict[str, Any]:
    """
    Get Redis connection health status.

    Returns basic health information about the Redis connection,
    including connectivity status and response time.
    """
    if not services.redis_service:
        raise HTTPException(status_code=503, detail="Redis service not available")

    try:
        import time

        start_time = time.time()

        # Test Redis connectivity
        is_healthy = await services.redis_service.ping()

        response_time_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "connected": is_healthy,
            "response_time_ms": response_time_ms,
            "timestamp": time.time(),
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "timestamp": time.time(),
        }


def _get_pool_recommendations(pool_stats: Dict[str, Any]) -> Dict[str, str]:
    """Generate recommendations based on pool statistics."""
    recommendations = {}

    # Check if pool statistics are available
    if pool_stats.get("status") == "not_initialized":
        recommendations["initialization"] = "Redis connection pool is not initialized"
        return recommendations

    max_connections = pool_stats.get("max_connections", 0)
    in_use = pool_stats.get("in_use_connections", 0)
    available = pool_stats.get("available_connections", 0)

    if max_connections > 0 and in_use is not None:
        utilization = (in_use / max_connections) * 100

        if utilization > 90:
            recommendations["high_utilization"] = (
                f"Connection pool utilization is high ({utilization:.1f}%). "
                "Consider increasing MAX_CONNECTIONS or optimizing connection usage."
            )
        elif utilization > 75:
            recommendations["moderate_utilization"] = (
                f"Connection pool utilization is moderate ({utilization:.1f}%). "
                "Monitor for potential bottlenecks during peak load."
            )
        elif utilization < 10 and max_connections > 20:
            recommendations["low_utilization"] = (
                f"Connection pool utilization is low ({utilization:.1f}%). "
                "Consider reducing MAX_CONNECTIONS to save resources."
            )

    if available is not None and available == 0 and in_use > 0:
        recommendations["pool_exhaustion"] = (
            "No available connections in the pool. "
            "This may cause connection timeouts. Consider increasing MAX_CONNECTIONS."
        )

    if not recommendations:
        recommendations["status"] = (
            "Connection pool is operating within normal parameters."
        )

    return recommendations
