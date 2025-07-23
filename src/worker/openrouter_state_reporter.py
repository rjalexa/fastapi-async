"""
Worker-side OpenRouter state reporting.

This module allows workers to report OpenRouter API errors to the centralized
state management system, enabling efficient coordination between workers and API.
"""

import os
from typing import Optional
from datetime import datetime, timezone

import redis.asyncio as aioredis
from src.worker.redis_config import get_worker_standard_redis


class WorkerOpenRouterReporter:
    """Reports OpenRouter errors from workers to the centralized state system."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self._worker_id = None

    async def _get_redis(self) -> aioredis.Redis:
        """Get Redis connection, initializing if needed."""
        if self.redis is None:
            try:
                self.redis = await get_worker_standard_redis()
            except Exception:
                # Fallback to basic connection
                from config import settings

                self.redis = aioredis.from_url(
                    settings.redis_url, decode_responses=True
                )
        return self.redis

    def _get_worker_id(self) -> str:
        """Get worker ID for reporting."""
        if self._worker_id is None:
            try:
                # Try to get container ID from cgroup
                with open("/proc/self/cgroup", "r") as f:
                    for line in f:
                        if "docker" in line:
                            parts = line.strip().split("/")
                            for part in reversed(parts):
                                if len(part) == 64 and part.isalnum():
                                    self._worker_id = f"worker-{part[:12]}"
                                    return self._worker_id

                # Fallback to hostname + PID
                hostname = os.uname().nodename
                pid = os.getpid()
                self._worker_id = f"worker-{hostname}-{pid}"

            except Exception:
                self._worker_id = f"worker-unknown-{os.getpid()}"

        return self._worker_id

    async def report_api_error(
        self,
        error_message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
    ) -> bool:
        """
        Report an OpenRouter API error to the state management system.

        Args:
            error_message: The error message from the API call
            status_code: HTTP status code if available
            error_type: Specific error type if known

        Returns:
            True if report was successful, False otherwise
        """
        try:
            redis_client = await self._get_redis()
            worker_id = self._get_worker_id()

            # Classify the error if not provided
            if error_type is None:
                error_type = self._classify_error(error_message, status_code)

            # Use the same state management keys as the API
            STATE_KEY = "openrouter:state"
            LOCK_KEY = "openrouter:state:lock"
            LOCK_TIMEOUT = 10

            # Try to acquire lock for state update
            lock_acquired = await redis_client.set(
                LOCK_KEY, f"worker-{worker_id}", nx=True, ex=LOCK_TIMEOUT
            )

            if not lock_acquired:
                # Another process is updating, just log the error for now
                await self._log_worker_error(
                    redis_client, worker_id, error_type, error_message, status_code
                )
                return False

            try:
                current_time = datetime.now(timezone.utc)

                # Get current state
                current_state_data = await redis_client.hgetall(STATE_KEY)
                consecutive_failures = 0

                if current_state_data:
                    consecutive_failures = int(
                        current_state_data.get("consecutive_failures", 0)
                    )

                # Increment failure count for error states
                if error_type in [
                    "api_key_invalid",
                    "credits_exhausted",
                    "rate_limited",
                    "service_unavailable",
                    "timeout",
                    "network_error",
                ]:
                    consecutive_failures += 1

                # Map error types to states
                error_state_map = {
                    "api_key_invalid": "api_key_invalid",
                    "credits_exhausted": "credits_exhausted",
                    "rate_limited": "rate_limited",
                    "service_unavailable": "service_unavailable",
                    "timeout": "error",
                    "network_error": "error",
                }

                new_state = error_state_map.get(error_type, "error")
                circuit_breaker_open = consecutive_failures >= 5

                # Create error details
                error_details = {
                    "error_type": error_type,
                    "error_message": error_message,
                    "worker_id": worker_id,
                    "timestamp": current_time.isoformat(),
                }

                if status_code:
                    error_details["status_code"] = status_code

                # Update state
                state_data = {
                    "state": new_state,
                    "message": f"Worker reported: {error_type}",
                    "last_check": current_time.isoformat(),
                    "last_api_call": current_time.isoformat(),
                    "consecutive_failures": str(consecutive_failures),
                    "circuit_breaker_open": str(circuit_breaker_open).lower(),
                    "error_details": str(error_details),  # JSON string
                }

                # Handle rate limiting
                if error_type == "rate_limited":
                    # Estimate rate limit reset time (usually 1 minute for OpenRouter)
                    from datetime import timedelta

                    rate_limit_reset = current_time + timedelta(minutes=1)
                    state_data["rate_limit_reset"] = rate_limit_reset.isoformat()

                # Update state in Redis
                await redis_client.hset(STATE_KEY, mapping=state_data)
                await redis_client.expire(STATE_KEY, 600)  # 10 minutes TTL

                # Update metrics
                await self._update_metrics(redis_client, new_state, False)

                # Log the error for debugging
                await self._log_worker_error(
                    redis_client, worker_id, error_type, error_message, status_code
                )

                return True

            finally:
                # Release lock
                await redis_client.delete(LOCK_KEY)

        except Exception as e:
            print(f"Error reporting OpenRouter error from worker: {e}")
            return False

    async def report_api_success(self) -> bool:
        """
        Report a successful OpenRouter API call.

        Returns:
            True if report was successful, False otherwise
        """
        try:
            redis_client = await self._get_redis()
            worker_id = self._get_worker_id()

            STATE_KEY = "openrouter:state"
            LOCK_KEY = "openrouter:state:lock"
            LOCK_TIMEOUT = 10

            # Try to acquire lock for state update
            lock_acquired = await redis_client.set(
                LOCK_KEY, f"worker-{worker_id}", nx=True, ex=LOCK_TIMEOUT
            )

            if not lock_acquired:
                return False  # Another process is updating

            try:
                current_time = datetime.now(timezone.utc)

                # Update state to active with success
                state_data = {
                    "state": "active",
                    "message": "Service active",
                    "last_check": current_time.isoformat(),
                    "last_api_call": current_time.isoformat(),
                    "last_success": current_time.isoformat(),
                    "consecutive_failures": "0",
                    "circuit_breaker_open": "false",
                }

                await redis_client.hset(STATE_KEY, mapping=state_data)
                await redis_client.expire(STATE_KEY, 600)  # 10 minutes TTL

                # Update metrics
                await self._update_metrics(redis_client, "active", True)

                return True

            finally:
                await redis_client.delete(LOCK_KEY)

        except Exception as e:
            print(f"Error reporting OpenRouter success from worker: {e}")
            return False

    def _classify_error(self, error_message: str, status_code: Optional[int]) -> str:
        """Classify error based on message and status code."""
        error_lower = error_message.lower()

        # Check status codes first
        if status_code == 401:
            return "api_key_invalid"
        elif status_code == 402:
            return "credits_exhausted"
        elif status_code == 429:
            return "rate_limited"
        elif status_code == 503:
            return "service_unavailable"

        # Check error message patterns
        if any(
            pattern in error_lower
            for pattern in ["invalid api key", "unauthorized", "authentication failed"]
        ):
            return "api_key_invalid"
        elif any(
            pattern in error_lower
            for pattern in [
                "insufficient credits",
                "credits exhausted",
                "quota exceeded",
            ]
        ):
            return "credits_exhausted"
        elif any(
            pattern in error_lower for pattern in ["rate limit", "too many requests"]
        ):
            return "rate_limited"
        elif any(
            pattern in error_lower
            for pattern in ["service unavailable", "server error", "internal error"]
        ):
            return "service_unavailable"
        elif any(pattern in error_lower for pattern in ["timeout", "timed out"]):
            return "timeout"
        elif any(
            pattern in error_lower for pattern in ["network", "connection", "dns"]
        ):
            return "network_error"

        return "unknown_error"

    async def _update_metrics(
        self, redis_client: aioredis.Redis, state: str, is_success: bool
    ) -> None:
        """Update OpenRouter metrics."""
        try:
            current_time = datetime.now(timezone.utc)
            date_key = current_time.strftime("%Y-%m-%d")
            metrics_key = f"openrouter:metrics:{date_key}"

            async with redis_client.pipeline() as pipe:
                await pipe.hincrby(metrics_key, "total_calls", 1)

                if is_success:
                    await pipe.hincrby(metrics_key, "successful_calls", 1)
                else:
                    await pipe.hincrby(metrics_key, "failed_calls", 1)

                await pipe.hincrby(metrics_key, f"state_{state}", 1)
                await pipe.expire(metrics_key, 30 * 24 * 3600)  # 30 days

                await pipe.execute()

        except Exception as e:
            print(f"Error updating metrics from worker: {e}")

    async def _log_worker_error(
        self,
        redis_client: aioredis.Redis,
        worker_id: str,
        error_type: str,
        error_message: str,
        status_code: Optional[int],
    ) -> None:
        """Log worker error for debugging."""
        try:
            current_time = datetime.now(timezone.utc)
            log_key = f"openrouter:worker_errors:{current_time.strftime('%Y-%m-%d')}"

            error_log = {
                "timestamp": current_time.isoformat(),
                "worker_id": worker_id,
                "error_type": error_type,
                "error_message": error_message,
                "status_code": status_code,
            }

            # Add to list of errors for the day
            await redis_client.lpush(log_key, str(error_log))
            await redis_client.ltrim(log_key, 0, 999)  # Keep last 1000 errors
            await redis_client.expire(log_key, 7 * 24 * 3600)  # Keep for 7 days

        except Exception as e:
            print(f"Error logging worker error: {e}")


# Global instance for easy access
_reporter_instance: Optional[WorkerOpenRouterReporter] = None


def get_openrouter_reporter() -> WorkerOpenRouterReporter:
    """Get global OpenRouter reporter instance."""
    global _reporter_instance
    if _reporter_instance is None:
        _reporter_instance = WorkerOpenRouterReporter()
    return _reporter_instance


async def report_openrouter_error(
    error_message: str,
    status_code: Optional[int] = None,
    error_type: Optional[str] = None,
) -> bool:
    """
    Convenience function to report OpenRouter error from worker.

    Args:
        error_message: The error message
        status_code: HTTP status code if available
        error_type: Specific error type if known

    Returns:
        True if report successful, False otherwise
    """
    reporter = get_openrouter_reporter()
    return await reporter.report_api_error(error_message, status_code, error_type)


async def report_openrouter_success() -> bool:
    """
    Convenience function to report OpenRouter success from worker.

    Returns:
        True if report successful, False otherwise
    """
    reporter = get_openrouter_reporter()
    return await reporter.report_api_success()
