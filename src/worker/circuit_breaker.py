# src/worker/circuit_breaker.py
import os
import pybreaker
import httpx
from config import settings

# Create circuit breaker instance
openrouter_breaker = pybreaker.CircuitBreaker(
    fail_max=5,  # Open after 5 failures
    reset_timeout=60,  # Try again after 60 seconds
    exclude=[KeyboardInterrupt],  # Don't count these as failures
)


@openrouter_breaker
async def call_openrouter_api(content: str) -> str:
    """Call OpenRouter API with circuit breaker protection."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [{"role": "user", "content": f"Summarize: {content}"}],
            },
            timeout=settings.openrouter_timeout,
        )

        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}")

        result = response.json()
        return result["choices"][0]["message"]["content"]


def get_container_id() -> str:
    """Get Docker container ID from /proc/self/cgroup or hostname."""
    try:
        # Try to get container ID from cgroup (most reliable method)
        with open('/proc/self/cgroup', 'r') as f:
            for line in f:
                if 'docker' in line:
                    # Extract container ID from cgroup path
                    parts = line.strip().split('/')
                    for part in reversed(parts):
                        if len(part) == 64 and part.isalnum():  # Docker container ID format
                            return part[:12]  # Return short container ID
                        elif part.startswith('docker-') and part.endswith('.scope'):
                            # systemd format: docker-<container_id>.scope
                            container_id = part[7:-6]  # Remove 'docker-' prefix and '.scope' suffix
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
        if hasattr(openrouter_breaker, 'reset'):
            openrouter_breaker.reset()
        elif hasattr(openrouter_breaker, '_reset'):
            openrouter_breaker._reset()
        else:
            # Manual reset by setting state and counters
            if hasattr(openrouter_breaker, '_failure_count'):
                openrouter_breaker._failure_count = 0
            if hasattr(openrouter_breaker, '_state_storage'):
                openrouter_breaker._state_storage.state = 'closed'
            elif hasattr(openrouter_breaker, '_state'):
                openrouter_breaker._state = 'closed'
        return True
    except Exception as e:
        raise Exception(f"Failed to reset circuit breaker: {str(e)}")


def open_circuit_breaker():
    """Manually open the circuit breaker."""
    try:
        # Force the circuit breaker to open by simulating failures
        # Set the failure counter to exceed the threshold
        if hasattr(openrouter_breaker, '_failure_count'):
            openrouter_breaker._failure_count = openrouter_breaker.fail_max + 1
        
        # Try to trigger the state change by calling the failure method
        try:
            # This will force the circuit breaker to open
            openrouter_breaker._on_failure()
        except:
            # If that doesn't work, try setting the state directly
            if hasattr(openrouter_breaker, '_state_storage'):
                openrouter_breaker._state_storage.state = 'open'
            elif hasattr(openrouter_breaker, '_state'):
                openrouter_breaker._state = 'open'
        
        return True
    except Exception as e:
        raise Exception(f"Failed to open circuit breaker: {str(e)}")
