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


def get_circuit_breaker_status() -> dict:
    """Get current circuit breaker status for this worker."""
    return {
        "state": openrouter_breaker.current_state,
        "fail_count": openrouter_breaker.fail_counter,
        "success_count": openrouter_breaker.success_counter,
        "last_failure": str(openrouter_breaker.last_failure)
        if openrouter_breaker.last_failure
        else None,
        "worker_pid": os.getpid(),
    }


def reset_circuit_breaker():
    """Manually reset the circuit breaker."""
    openrouter_breaker.reset()
