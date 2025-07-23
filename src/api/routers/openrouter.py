# src/api/routers/openrouter.py
"""OpenRouter status monitoring endpoints."""

import json
from typing import Dict, Optional
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.api.config import settings
from src.api.services import get_redis_service
from src.api.openrouter_state import (
    OpenRouterStateManager,
    OpenRouterState,
)


router = APIRouter(prefix="/api/v1/openrouter", tags=["openrouter"])


class OpenRouterStatus(BaseModel):
    """OpenRouter status response model."""

    status: str  # "active", "api_key_missing", "api_key_invalid", "credits_exhausted", "error"
    message: str
    balance: Optional[float] = None
    usage_today: Optional[float] = None
    usage_month: Optional[float] = None
    last_check: Optional[str] = None
    error_details: Optional[str] = None
    consecutive_failures: Optional[int] = None
    circuit_breaker_open: Optional[bool] = None
    cache_hit: Optional[bool] = None


async def check_openrouter_api_key(api_key: str, base_url: str) -> Dict:
    """
    Check OpenRouter API key validity and get credit information.

    Returns:
        Dictionary containing status and credit information
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/auth/key",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

            if response.status_code == 401:
                return {
                    "status": "api_key_invalid",
                    "message": "API key is invalid",
                    "error_details": "Authentication failed",
                }
            elif response.status_code == 403:
                return {
                    "status": "credits_exhausted",
                    "message": "Credits exhausted",
                    "error_details": "Insufficient credits",
                }
            elif response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"API error: {response.status_code}",
                    "error_details": response.text,
                }

            data = response.json()

            # Handle different possible response structures
            if isinstance(data, dict):
                data_section = data.get("data", data)

                # Extract credit information
                balance = 0.0
                usage_today = 0.0
                usage_month = 0.0

                if isinstance(data_section, dict):
                    # OpenRouter API uses 'usage' field for total usage amount
                    total_usage = data_section.get("usage", 0.0)
                    balance = total_usage  # This is actually total usage, not remaining balance
                    usage_today = 0.0  # Not available from this endpoint
                    usage_month = total_usage  # Use total usage as monthly usage

                # Check if credits are exhausted (this is a simplified check)
                # In a real scenario, you'd need to know the actual credit limit
                if balance is not None and balance <= 0:
                    return {
                        "status": "credits_exhausted",
                        "message": "Credits exhausted",
                        "balance": float(balance),
                        "usage_today": float(usage_today),
                        "usage_month": float(usage_month),
                    }

                return {
                    "status": "active",
                    "message": "Service active",
                    "balance": float(balance) if balance is not None else 0.0,
                    "usage_today": float(usage_today)
                    if usage_today is not None
                    else 0.0,
                    "usage_month": float(usage_month)
                    if usage_month is not None
                    else 0.0,
                }
            else:
                return {
                    "status": "error",
                    "message": "Unexpected API response format",
                    "error_details": f"Response type: {type(data)}",
                }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": "API timeout",
            "error_details": "Request timed out",
        }
    except httpx.RequestError as e:
        return {"status": "error", "message": "Network error", "error_details": str(e)}
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "message": "Invalid JSON response",
            "error_details": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Unexpected error",
            "error_details": str(e),
        }


@router.get("/status", response_model=OpenRouterStatus)
async def get_openrouter_status(
    force_refresh: bool = False, redis_service=Depends(get_redis_service)
):
    """
    Get OpenRouter service status with intelligent caching.

    Args:
        force_refresh: Force a fresh API check, bypassing cache

    Returns status with appropriate labels for the frontend badge:
    - "api_key_missing": Red badge
    - "api_key_invalid": Red badge
    - "credits_exhausted": Orange badge
    - "rate_limited": Orange badge
    - "active": Green badge
    - "error": Red badge
    """

    # Check if API key is configured
    if not settings.openrouter_api_key:
        return OpenRouterStatus(
            status="api_key_missing", message="API Key missing", cache_hit=False
        )

    if not redis_service or not redis_service.redis:
        return OpenRouterStatus(
            status="error",
            message="Redis service unavailable",
            error_details="Cannot access state management",
            cache_hit=False,
        )

    try:
        # Initialize state manager
        state_manager = OpenRouterStateManager(redis_service.redis)

        # Try to get cached state first (unless force refresh)
        cached_state = None
        if not force_refresh:
            cached_state = await state_manager.get_state()

        # If we have fresh cached state, use it
        if cached_state and await state_manager.is_fresh():
            return OpenRouterStatus(
                status=cached_state.state.value,
                message=cached_state.message,
                balance=cached_state.balance,
                usage_today=cached_state.usage_today,
                usage_month=cached_state.usage_month,
                last_check=cached_state.last_check.isoformat(),
                error_details=cached_state.error_details,
                consecutive_failures=cached_state.consecutive_failures,
                circuit_breaker_open=cached_state.circuit_breaker_open,
                cache_hit=True,
            )

        # Check if we should skip API call due to circuit breaker or rate limiting
        should_skip, skip_reason = await state_manager.should_skip_api_call()
        if should_skip and cached_state:
            # Return cached state with updated message
            return OpenRouterStatus(
                status=cached_state.state.value,
                message=f"Skipped API call: {skip_reason}",
                balance=cached_state.balance,
                usage_today=cached_state.usage_today,
                usage_month=cached_state.usage_month,
                last_check=cached_state.last_check.isoformat(),
                error_details=cached_state.error_details,
                consecutive_failures=cached_state.consecutive_failures,
                circuit_breaker_open=cached_state.circuit_breaker_open,
                cache_hit=True,
            )

        # Perform fresh API check
        api_result = await check_openrouter_api_key(
            settings.openrouter_api_key, settings.openrouter_base_url
        )

        # Map API result to state
        state_map = {
            "active": OpenRouterState.ACTIVE,
            "api_key_invalid": OpenRouterState.API_KEY_INVALID,
            "credits_exhausted": OpenRouterState.CREDITS_EXHAUSTED,
            "error": OpenRouterState.ERROR,
        }

        new_state = state_map.get(api_result["status"], OpenRouterState.ERROR)
        is_success = api_result["status"] == "active"

        # Handle rate limiting detection
        if "rate limit" in api_result.get("error_details", "").lower():
            new_state = OpenRouterState.RATE_LIMITED

        # Update state in Redis
        await state_manager.update_state(
            state=new_state,
            message=api_result["message"],
            balance=api_result.get("balance"),
            usage_today=api_result.get("usage_today"),
            usage_month=api_result.get("usage_month"),
            error_details=api_result.get("error_details"),
            is_api_success=is_success,
        )

        # Get updated state for response
        updated_state = await state_manager.get_state(force_refresh=True)
        if updated_state:
            return OpenRouterStatus(
                status=updated_state.state.value,
                message=updated_state.message,
                balance=updated_state.balance,
                usage_today=updated_state.usage_today,
                usage_month=updated_state.usage_month,
                last_check=updated_state.last_check.isoformat(),
                error_details=updated_state.error_details,
                consecutive_failures=updated_state.consecutive_failures,
                circuit_breaker_open=updated_state.circuit_breaker_open,
                cache_hit=False,
            )

        # Fallback to API result if state update failed
        return OpenRouterStatus(
            status=api_result["status"],
            message=api_result["message"],
            balance=api_result.get("balance"),
            usage_today=api_result.get("usage_today"),
            usage_month=api_result.get("usage_month"),
            last_check=datetime.now(timezone.utc).isoformat(),
            error_details=api_result.get("error_details"),
            cache_hit=False,
        )

    except Exception as e:
        return OpenRouterStatus(
            status="error",
            message="Status check failed",
            error_details=str(e),
            cache_hit=False,
        )


@router.get("/metrics")
async def get_openrouter_metrics(
    days: int = 7, redis_service=Depends(get_redis_service)
):
    """Get OpenRouter usage metrics for the specified number of days."""
    if not redis_service or not redis_service.redis:
        raise HTTPException(status_code=503, detail="Redis service unavailable")

    try:
        state_manager = OpenRouterStateManager(redis_service.redis)
        metrics = await state_manager.get_metrics(days=days)

        return {
            "metrics": metrics,
            "days": days,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")
