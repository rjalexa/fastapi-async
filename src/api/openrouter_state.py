"""
OpenRouter state management with Redis caching.

This module provides centralized state management for OpenRouter API status,
allowing both the API and workers to read and update the state efficiently.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from enum import Enum

import redis.asyncio as aioredis
from pydantic import BaseModel


class OpenRouterState(str, Enum):
    """OpenRouter service states."""

    ACTIVE = "active"
    API_KEY_MISSING = "api_key_missing"
    API_KEY_INVALID = "api_key_invalid"
    CREDITS_EXHAUSTED = "credits_exhausted"
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    ERROR = "error"


class OpenRouterStateData(BaseModel):
    """OpenRouter state data structure."""

    state: OpenRouterState
    message: str
    balance: Optional[float] = None
    usage_today: Optional[float] = None
    usage_month: Optional[float] = None
    last_check: datetime
    last_api_call: Optional[datetime] = None
    error_details: Optional[str] = None
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    circuit_breaker_open: bool = False
    rate_limit_reset: Optional[datetime] = None


class OpenRouterStateManager:
    """Manages OpenRouter state in Redis with efficient caching and updates."""

    # Redis keys
    STATE_KEY = "openrouter:state"
    METRICS_KEY = "openrouter:metrics"
    LOCK_KEY = "openrouter:state:lock"

    # Cache settings
    DEFAULT_TTL = 300  # 5 minutes default TTL
    FRESH_THRESHOLD = 60  # Consider data fresh if less than 1 minute old
    STALE_THRESHOLD = 300  # Force refresh if older than 5 minutes
    LOCK_TIMEOUT = 10  # Lock timeout for state updates

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def get_state(
        self, force_refresh: bool = False
    ) -> Optional[OpenRouterStateData]:
        """
        Get current OpenRouter state from cache.

        Args:
            force_refresh: If True, ignore cache age and return current state

        Returns:
            OpenRouterStateData if available, None if no cached state
        """
        try:
            state_data = await self.redis.hgetall(self.STATE_KEY)
            if not state_data:
                return None

            # Parse the cached state
            last_check_str = state_data.get("last_check")
            if not last_check_str:
                return None

            last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))

            # Check if data is stale and needs refresh
            if not force_refresh:
                age_seconds = (datetime.now(timezone.utc) - last_check).total_seconds()
                if age_seconds > self.STALE_THRESHOLD:
                    return None  # Data too old, caller should refresh

            # Parse optional datetime fields
            last_api_call = None
            if state_data.get("last_api_call"):
                try:
                    last_api_call = datetime.fromisoformat(
                        state_data["last_api_call"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            last_success = None
            if state_data.get("last_success"):
                try:
                    last_success = datetime.fromisoformat(
                        state_data["last_success"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            rate_limit_reset = None
            if state_data.get("rate_limit_reset"):
                try:
                    rate_limit_reset = datetime.fromisoformat(
                        state_data["rate_limit_reset"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            return OpenRouterStateData(
                state=OpenRouterState(state_data.get("state", OpenRouterState.ERROR)),
                message=state_data.get("message", "Unknown state"),
                balance=float(state_data["balance"])
                if state_data.get("balance")
                else None,
                usage_today=float(state_data["usage_today"])
                if state_data.get("usage_today")
                else None,
                usage_month=float(state_data["usage_month"])
                if state_data.get("usage_month")
                else None,
                last_check=last_check,
                last_api_call=last_api_call,
                error_details=state_data.get("error_details"),
                consecutive_failures=int(state_data.get("consecutive_failures", 0)),
                last_success=last_success,
                circuit_breaker_open=state_data.get(
                    "circuit_breaker_open", "false"
                ).lower()
                == "true",
                rate_limit_reset=rate_limit_reset,
            )

        except Exception as e:
            print(f"Error getting OpenRouter state: {e}")
            return None

    async def update_state(
        self,
        state: OpenRouterState,
        message: str,
        balance: Optional[float] = None,
        usage_today: Optional[float] = None,
        usage_month: Optional[float] = None,
        error_details: Optional[str] = None,
        is_api_success: bool = False,
        rate_limit_reset: Optional[datetime] = None,
    ) -> bool:
        """
        Update OpenRouter state in Redis.

        Args:
            state: New state
            message: State message
            balance: Account balance
            usage_today: Today's usage
            usage_month: Monthly usage
            error_details: Error details if applicable
            is_api_success: Whether this update represents a successful API call
            rate_limit_reset: When rate limit resets (if rate limited)

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Acquire lock to prevent concurrent updates
            lock_acquired = await self.redis.set(
                self.LOCK_KEY, "locked", nx=True, ex=self.LOCK_TIMEOUT
            )

            if not lock_acquired:
                # Another process is updating, skip this update
                return False

            try:
                current_time = datetime.now(timezone.utc)

                # Get current state for failure counting
                current_state = await self.get_state(force_refresh=True)
                consecutive_failures = 0
                last_success = None

                if current_state:
                    consecutive_failures = current_state.consecutive_failures
                    last_success = current_state.last_success

                # Update failure count and success timestamp
                if is_api_success:
                    consecutive_failures = 0
                    last_success = current_time
                elif state in [
                    OpenRouterState.ERROR,
                    OpenRouterState.SERVICE_UNAVAILABLE,
                    OpenRouterState.RATE_LIMITED,
                ]:
                    consecutive_failures += 1

                # Determine if circuit breaker should be open
                circuit_breaker_open = (
                    consecutive_failures >= 5
                )  # Open after 5 consecutive failures

                # Prepare state data
                state_data = {
                    "state": state.value,
                    "message": message,
                    "last_check": current_time.isoformat(),
                    "last_api_call": current_time.isoformat(),
                    "consecutive_failures": str(consecutive_failures),
                    "circuit_breaker_open": str(circuit_breaker_open).lower(),
                }

                # Add optional fields
                if balance is not None:
                    state_data["balance"] = str(balance)
                if usage_today is not None:
                    state_data["usage_today"] = str(usage_today)
                if usage_month is not None:
                    state_data["usage_month"] = str(usage_month)
                if error_details:
                    state_data["error_details"] = error_details
                if last_success:
                    state_data["last_success"] = last_success.isoformat()
                if rate_limit_reset:
                    state_data["rate_limit_reset"] = rate_limit_reset.isoformat()

                # Update state in Redis with TTL
                await self.redis.hset(self.STATE_KEY, mapping=state_data)
                await self.redis.expire(
                    self.STATE_KEY, self.DEFAULT_TTL * 2
                )  # 10 minutes TTL

                # Update metrics
                await self._update_metrics(state, is_api_success)

                return True

            finally:
                # Release lock
                await self.redis.delete(self.LOCK_KEY)

        except Exception as e:
            print(f"Error updating OpenRouter state: {e}")
            return False

    async def report_worker_error(
        self,
        error_type: str,
        error_message: str,
        status_code: Optional[int] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Report an OpenRouter error from a worker.

        Args:
            error_type: Type of error (e.g., "api_key_invalid", "credits_exhausted")
            error_message: Error message
            status_code: HTTP status code if applicable
            worker_id: ID of the worker reporting the error

        Returns:
            True if report successful, False otherwise
        """
        try:
            # Map error types to states
            error_state_map = {
                "api_key_invalid": OpenRouterState.API_KEY_INVALID,
                "credits_exhausted": OpenRouterState.CREDITS_EXHAUSTED,
                "rate_limited": OpenRouterState.RATE_LIMITED,
                "service_unavailable": OpenRouterState.SERVICE_UNAVAILABLE,
                "timeout": OpenRouterState.ERROR,
                "network_error": OpenRouterState.ERROR,
            }

            state = error_state_map.get(error_type, OpenRouterState.ERROR)

            # Create error details
            error_details = {
                "error_type": error_type,
                "error_message": error_message,
                "worker_id": worker_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if status_code:
                error_details["status_code"] = status_code

            # Update state
            return await self.update_state(
                state=state,
                message=f"Worker reported: {error_type}",
                error_details=json.dumps(error_details),
                is_api_success=False,
            )

        except Exception as e:
            print(f"Error reporting worker error: {e}")
            return False

    async def is_fresh(self, max_age_seconds: int = None) -> bool:
        """
        Check if cached state is fresh enough.

        Args:
            max_age_seconds: Maximum age in seconds (default: FRESH_THRESHOLD)

        Returns:
            True if state is fresh, False otherwise
        """
        if max_age_seconds is None:
            max_age_seconds = self.FRESH_THRESHOLD

        try:
            last_check_str = await self.redis.hget(self.STATE_KEY, "last_check")
            if not last_check_str:
                return False

            last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - last_check).total_seconds()

            return age_seconds <= max_age_seconds

        except Exception:
            return False

    async def should_skip_api_call(self) -> tuple[bool, Optional[str]]:
        """
        Check if API calls should be skipped due to circuit breaker or rate limiting.

        Returns:
            Tuple of (should_skip, reason)
        """
        try:
            state = await self.get_state(force_refresh=True)
            if not state:
                return False, None

            # Check circuit breaker
            if state.circuit_breaker_open:
                return True, "Circuit breaker is open"

            # Check rate limiting
            if (
                state.state == OpenRouterState.RATE_LIMITED
                and state.rate_limit_reset
                and datetime.now(timezone.utc) < state.rate_limit_reset
            ):
                return True, "Rate limited"

            return False, None

        except Exception:
            return False, None

    async def _update_metrics(self, state: OpenRouterState, is_success: bool) -> None:
        """Update OpenRouter metrics."""
        try:
            current_time = datetime.now(timezone.utc)

            # Update daily metrics
            date_key = current_time.strftime("%Y-%m-%d")
            metrics_key = f"{self.METRICS_KEY}:{date_key}"

            async with self.redis.pipeline() as pipe:
                # Increment counters
                await pipe.hincrby(metrics_key, "total_calls", 1)

                if is_success:
                    await pipe.hincrby(metrics_key, "successful_calls", 1)
                else:
                    await pipe.hincrby(metrics_key, "failed_calls", 1)

                # Track state occurrences
                await pipe.hincrby(metrics_key, f"state_{state.value}", 1)

                # Set expiry for metrics (keep for 30 days)
                await pipe.expire(metrics_key, 30 * 24 * 3600)

                await pipe.execute()

        except Exception as e:
            print(f"Error updating metrics: {e}")

    async def get_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get OpenRouter metrics for the specified number of days.

        Args:
            days: Number of days to retrieve metrics for

        Returns:
            Dictionary containing metrics data
        """
        try:
            metrics = {}
            current_time = datetime.now(timezone.utc)

            for i in range(days):
                from datetime import timedelta

                date = current_time - timedelta(days=i)
                date_key = date.strftime("%Y-%m-%d")
                metrics_key = f"{self.METRICS_KEY}:{date_key}"

                day_metrics = await self.redis.hgetall(metrics_key)
                if day_metrics:
                    # Convert string values to integers
                    parsed_metrics = {}
                    for key, value in day_metrics.items():
                        try:
                            parsed_metrics[key] = int(value)
                        except (ValueError, TypeError):
                            parsed_metrics[key] = value

                    metrics[date_key] = parsed_metrics

            return metrics

        except Exception as e:
            print(f"Error getting metrics: {e}")
            return {}
