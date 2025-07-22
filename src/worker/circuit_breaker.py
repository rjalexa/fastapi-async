# src/worker/circuit_breaker.py
import asyncio
import os
import random
from typing import List, Dict
import pybreaker
import httpx
from config import settings
from rate_limiter import wait_for_rate_limit_token
from openrouter_state_reporter import report_openrouter_error, report_openrouter_success

# Create circuit breaker instance
openrouter_breaker = pybreaker.CircuitBreaker(
    fail_max=10,  # Open after 10 failures
    reset_timeout=120,  # Try again after 120 seconds
    exclude=[KeyboardInterrupt],  # Don't count these as failures
)


def calculate_backoff_delay(
    attempt: int, base_delay: float = 1.0, max_delay: float = 300.0
) -> float:
    """
    Calculate exponential backoff delay with jitter for rate limiting.

    Args:
        attempt: The retry attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential backoff: base_delay * (2 ^ attempt)
    delay = base_delay * (2**attempt)

    # Cap at max_delay
    delay = min(delay, max_delay)

    # Add jitter (±25% of the delay)
    jitter = delay * 0.25 * (2 * random.random() - 1)
    final_delay = delay + jitter

    # Ensure minimum delay of base_delay
    return max(final_delay, base_delay)


@openrouter_breaker
async def call_openrouter_api(
    messages: List[Dict[str, str]], retry_attempt: int = 0
) -> str:
    """
    Generic function to call OpenRouter API with circuit breaker protection and distributed rate limiting.

    Args:
        messages: List of message dictionaries for the chat completion API
                 (e.g., [{"role": "user", "content": "..."}])
        retry_attempt: Current retry attempt number for backoff calculation

    Returns:
        The response content from the API

    Raises:
        Exception: If the API call fails
    """
    # First, acquire a rate limit token from the distributed rate limiter
    # This ensures all workers coordinate to respect OpenRouter's global rate limits
    rate_limit_timeout = 60.0  # Wait up to 60 seconds for a rate limit token

    if not await wait_for_rate_limit_token(tokens=1, timeout=rate_limit_timeout):
        raise Exception(
            f"Rate limit token acquisition timeout after {rate_limit_timeout}s - OpenRouter API may be overloaded"
        )

    max_retries = 5

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.openrouter_model,
                        "messages": messages,
                    },
                    timeout=settings.openrouter_timeout,
                )

                # Handle rate limiting (HTTP 429) with exponential backoff
                if response.status_code == 429:
                    # Report rate limiting to state management
                    try:
                        await report_openrouter_error(
                            error_message="Rate limit exceeded",
                            status_code=429,
                            error_type="rate_limited",
                        )
                    except Exception:
                        pass  # Don't fail the main operation if reporting fails

                    if attempt < max_retries - 1:  # Don't sleep on the last attempt
                        # Check for Retry-After header
                        retry_after = response.headers.get("retry-after")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = calculate_backoff_delay(
                                    attempt, base_delay=60.0
                                )
                        else:
                            # Use exponential backoff for rate limiting
                            delay = calculate_backoff_delay(attempt, base_delay=60.0)

                        # Add extra jitter for thundering herd prevention
                        jitter = random.uniform(0, min(delay * 0.1, 30))
                        total_delay = delay + jitter

                        await asyncio.sleep(total_delay)
                        continue
                    else:
                        raise Exception(
                            f"OpenRouter API rate limit exceeded after {max_retries} attempts: {response.status_code}"
                        )

                # Handle other HTTP errors
                if response.status_code != 200:
                    # Report API error to state management
                    try:
                        error_type = None
                        if response.status_code == 401:
                            error_type = "api_key_invalid"
                        elif response.status_code == 402:
                            error_type = "credits_exhausted"
                        elif response.status_code == 503:
                            error_type = "service_unavailable"

                        await report_openrouter_error(
                            error_message=f"HTTP {response.status_code}: {response.text[:200]}",
                            status_code=response.status_code,
                            error_type=error_type,
                        )
                    except Exception:
                        pass  # Don't fail the main operation if reporting fails

                    # For non-rate-limit errors, don't retry here - let the circuit breaker handle it
                    raise Exception(f"OpenRouter API error: {response.status_code}")

                # Success! Report to state management
                try:
                    await report_openrouter_success()
                except Exception:
                    pass  # Don't fail the main operation if reporting fails

                result = response.json()
                return result["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            # Report timeout error to state management
            if attempt == max_retries - 1:  # Only report on final attempt
                try:
                    await report_openrouter_error(
                        error_message="API request timeout", error_type="timeout"
                    )
                except Exception:
                    pass

            if attempt < max_retries - 1:
                delay = calculate_backoff_delay(attempt, base_delay=2.0, max_delay=60.0)
                await asyncio.sleep(delay)
                continue
            else:
                raise Exception("OpenRouter API timeout after multiple attempts")
        except httpx.RequestError as e:
            # Report network error to state management
            if attempt == max_retries - 1:  # Only report on final attempt
                try:
                    await report_openrouter_error(
                        error_message=f"Network error: {str(e)}",
                        error_type="network_error",
                    )
                except Exception:
                    pass

            if attempt < max_retries - 1:
                delay = calculate_backoff_delay(attempt, base_delay=1.0, max_delay=30.0)
                await asyncio.sleep(delay)
                continue
            else:
                raise Exception(f"OpenRouter API request error: {str(e)}")

    # If we get here, all attempts failed - report general error
    try:
        await report_openrouter_error(
            error_message="All API retry attempts failed",
            error_type="service_unavailable",
        )
    except Exception:
        pass

    raise Exception("OpenRouter API call failed after all retry attempts")


def get_container_id() -> str:
    """Get Docker container ID from /proc/self/cgroup or hostname."""
    try:
        # Try to get container ID from cgroup (most reliable method)
        with open("/proc/self/cgroup", "r") as f:
            for line in f:
                if "docker" in line:
                    # Extract container ID from cgroup path
                    parts = line.strip().split("/")
                    for part in reversed(parts):
                        if (
                            len(part) == 64 and part.isalnum()
                        ):  # Docker container ID format
                            return part[:12]  # Return short container ID
                        elif part.startswith("docker-") and part.endswith(".scope"):
                            # systemd format: docker-<container_id>.scope
                            container_id = part[
                                7:-6
                            ]  # Remove 'docker-' prefix and '.scope' suffix
                            return container_id[:12]

        # Fallback: use hostname (often set to container ID in Docker)
        hostname = os.uname().nodename
        if len(hostname) >= 12:
            return hostname[:12]

        return hostname

    except Exception:
        # Final fallback: use hostname or unknown
        try:
            return os.uname().nodename[:12]
        except Exception:
            return "unknown"


def get_circuit_breaker_status() -> dict:
    """Get current circuit breaker status for this worker."""
    try:
        # Get available attributes safely
        status = {
            "state": openrouter_breaker.current_state,
            "fail_count": getattr(openrouter_breaker, "fail_counter", 0),
            "success_count": getattr(openrouter_breaker, "success_counter", 0),
            "container_id": get_container_id(),
        }

        # Add optional attributes if they exist
        if hasattr(openrouter_breaker, "last_failure_time"):
            status["last_failure_time"] = openrouter_breaker.last_failure_time

        if hasattr(openrouter_breaker, "_last_failure"):
            status["last_failure"] = str(openrouter_breaker._last_failure)

        return status

    except Exception as e:
        return {"state": "error", "error": str(e), "container_id": get_container_id()}


def reset_circuit_breaker():
    """Manually reset the circuit breaker."""
    try:
        # Try different reset methods based on pybreaker version
        if hasattr(openrouter_breaker, "reset"):
            openrouter_breaker.reset()
        elif hasattr(openrouter_breaker, "_reset"):
            openrouter_breaker._reset()
        else:
            # Manual reset by setting state and counters
            if hasattr(openrouter_breaker, "_failure_count"):
                openrouter_breaker._failure_count = 0
            if hasattr(openrouter_breaker, "_state_storage"):
                openrouter_breaker._state_storage.state = "closed"
            elif hasattr(openrouter_breaker, "_state"):
                openrouter_breaker._state = "closed"
        return True
    except Exception as e:
        raise Exception(f"Failed to reset circuit breaker: {str(e)}")


def open_circuit_breaker():
    """Manually open the circuit breaker."""
    try:
        # Force the circuit breaker to open by simulating failures
        # Set the failure counter to exceed the threshold
        if hasattr(openrouter_breaker, "_failure_count"):
            openrouter_breaker._failure_count = openrouter_breaker.fail_max + 1

        # Try to trigger the state change by calling the failure method
        try:
            # This will force the circuit breaker to open
            openrouter_breaker._on_failure()
        except Exception:
            # If that doesn't work, try setting the state directly
            if hasattr(openrouter_breaker, "_state_storage"):
                openrouter_breaker._state_storage.state = "open"
            elif hasattr(openrouter_breaker, "_state"):
                openrouter_breaker._state = "open"

        return True
    except Exception as e:
        raise Exception(f"Failed to open circuit breaker: {str(e)}")
