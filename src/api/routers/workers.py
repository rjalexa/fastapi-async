# src/api/routers/workers.py
"""Worker management API endpoints."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, status

from services import health_service

router = APIRouter(prefix="/api/v1/workers", tags=["workers-management"])


def get_health_service(request: Request):
    """Get health service from global variable or app state."""
    # Try global service first
    if health_service:
        return health_service

    # Fallback to app state (for reload mode)
    return getattr(request.app.state, "health_service", None)


@router.get("/")
async def get_worker_status(request: Request) -> dict:
    """
    Get detailed health from all workers including real circuit breaker status.

    Uses Celery broadcast to get actual worker health and circuit breaker status,
    with Redis heartbeats as fallback for basic connectivity.
    """
    try:
        current_health_service = get_health_service(request)
        
        if not current_health_service:
            return {
                "error": "Health service not initialized",
                "total_workers": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Try to get real worker health via Celery broadcast first
        worker_details = []
        try:
            from main import celery_app
            
            # Use broadcast to get health from all active workers
            broadcast_results = celery_app.control.broadcast(
                "get_worker_health", reply=True, timeout=5.0
            )
            
            if broadcast_results:
                for result in broadcast_results:
                    if result and isinstance(result, dict):
                        # Extract worker data from nested structure
                        for worker_name, worker_data in result.items():
                            if isinstance(worker_data, dict) and "worker_id" in worker_data:
                                # Add worker name for reference
                                worker_data["worker_name"] = worker_name
                                
                                # Determine overall worker status based on circuit breaker
                                cb_state = worker_data.get("circuit_breaker", {}).get("state", "unknown")
                                if cb_state == "open":
                                    worker_data["status"] = "unhealthy"
                                elif cb_state in ["closed", "half-open"]:
                                    worker_data["status"] = "healthy"
                                else:
                                    worker_data["status"] = "unknown"
                                
                                worker_details.append(worker_data)
        
        except Exception as broadcast_error:
            # If broadcast fails, we'll fall back to heartbeat-only method
            print(f"Broadcast failed: {broadcast_error}")
        
        # If we didn't get worker details from broadcast, fall back to heartbeat method
        if not worker_details:
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

            for key in heartbeat_keys:
                worker_id = key.split(":", 2)[2]  # Extract worker ID from key
                try:
                    heartbeat_time = await current_health_service.redis_service.redis.get(key)
                    if heartbeat_time:
                        heartbeat_timestamp = float(heartbeat_time)
                        age = current_time - heartbeat_timestamp
                        is_healthy = age < 60  # Consider healthy if heartbeat within last 60 seconds
                        
                        worker_details.append({
                            "worker_id": worker_id,
                            "status": "healthy" if is_healthy else "stale",
                            "last_heartbeat": heartbeat_timestamp,
                            "heartbeat_age_seconds": round(age, 2),
                            "circuit_breaker": {
                                "state": "unknown",
                                "note": "Circuit breaker status unavailable - worker not responding to broadcast"
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

        # Calculate summary statistics
        total_workers = len(worker_details)
        healthy_workers = sum(1 for w in worker_details if w.get("status") == "healthy")
        stale_workers = sum(1 for w in worker_details if w.get("status") == "stale")
        
        # Aggregate circuit breaker states
        circuit_breaker_states = {}
        for worker in worker_details:
            cb_state = worker.get("circuit_breaker", {}).get("state", "unknown")
            circuit_breaker_states[cb_state] = circuit_breaker_states.get(cb_state, 0) + 1

        return {
            "overall_status": "healthy" if healthy_workers == total_workers and total_workers > 0 else "degraded",
            "total_workers": total_workers,
            "healthy_workers": healthy_workers,
            "stale_workers": stale_workers,
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


@router.post("/reset-circuit-breaker")
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


@router.post("/open-circuit-breaker")
async def open_all_circuit_breakers() -> dict:
    """
    Open circuit breakers on all workers to stop queue processing.

    This will cause all workers to stop processing tasks until the circuit breakers are reset.
    Tasks will be scheduled for retry rather than processed.
    """
    try:
        from main import celery_app

        # Use broadcast to send open circuit breaker command to all workers
        job_results = celery_app.control.broadcast(
            "open_worker_circuit_breaker", reply=True, timeout=5.0
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
            job = celery_app.send_task("open_worker_circuit_breaker")
            try:
                result = job.get(timeout=5.0)
                if result:
                    results = [result]
            except Exception:
                results = []

        successful_opens = sum(1 for r in results if r.get("status") == "success")

        return {
            "message": f"Open circuit breaker attempted on {len(results)} workers",
            "successful_opens": successful_opens,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
