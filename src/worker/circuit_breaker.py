"""Circuit breaker implementation for external service protection."""

import time
from collections import defaultdict
from enum import Enum
from typing import Dict

from config import settings


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for protecting external services.

    Tracks failure rates and automatically opens/closes circuits based on
    configurable thresholds.
    """

    def __init__(
        self,
        failure_threshold: float = None,
        volume_threshold: int = None,
        timeout: int = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failure rate threshold (0.0-1.0)
            volume_threshold: Minimum requests before evaluating failure rate
            timeout: Time in seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold or settings.circuit_failure_threshold
        self.volume_threshold = volume_threshold or settings.circuit_volume_threshold
        self.timeout = timeout or settings.circuit_timeout

        # Per-service tracking
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, float] = {}
        self.state: Dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)

    def record_success(self, service: str) -> None:
        """Record a successful operation for a service."""
        self.success_counts[service] += 1

        # If we're in half-open state and got a success, close the circuit
        if self.state[service] == CircuitState.HALF_OPEN:
            self.state[service] = CircuitState.CLOSED
            self.reset_counts(service)

    def record_failure(self, service: str) -> None:
        """Record a failed operation for a service."""
        self.failure_counts[service] += 1
        self.last_failure_time[service] = time.time()

        # Check if we should open the circuit
        total_requests = self.failure_counts[service] + self.success_counts[service]

        if total_requests >= self.volume_threshold:
            failure_rate = self.failure_counts[service] / total_requests

            if failure_rate >= self.failure_threshold:
                self.state[service] = CircuitState.OPEN

    def can_execute(self, service: str) -> bool:
        """
        Check if a request can be executed for a service.

        Returns:
            True if the request should proceed, False if it should be rejected
        """
        current_state = self.state[service]

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.OPEN:
            # Check if enough time has passed to try recovery
            last_failure = self.last_failure_time.get(service, 0)
            if time.time() - last_failure >= self.timeout:
                self.state[service] = CircuitState.HALF_OPEN
                return True
            return False

        if current_state == CircuitState.HALF_OPEN:
            # Allow one request to test if service is recovered
            return True

        return False

    def get_state(self, service: str) -> CircuitState:
        """Get the current state of the circuit for a service."""
        return self.state[service]

    def get_stats(self, service: str) -> Dict[str, any]:
        """Get statistics for a service."""
        total_requests = self.failure_counts[service] + self.success_counts[service]
        failure_rate = (
            self.failure_counts[service] / total_requests if total_requests > 0 else 0.0
        )

        return {
            "state": self.state[service].value,
            "failure_count": self.failure_counts[service],
            "success_count": self.success_counts[service],
            "total_requests": total_requests,
            "failure_rate": failure_rate,
            "last_failure_time": self.last_failure_time.get(service),
        }

    def reset_counts(self, service: str) -> None:
        """Reset counters for a service."""
        self.failure_counts[service] = 0
        self.success_counts[service] = 0

    def force_open(self, service: str) -> None:
        """Manually open the circuit for a service."""
        self.state[service] = CircuitState.OPEN
        self.last_failure_time[service] = time.time()

    def force_close(self, service: str) -> None:
        """Manually close the circuit for a service."""
        self.state[service] = CircuitState.CLOSED
        self.reset_counts(service)


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()


def get_circuit_breaker_status() -> Dict[str, any]:
    """Get overall circuit breaker status for all services."""
    services = set(
        list(circuit_breaker.failure_counts.keys())
        + list(circuit_breaker.success_counts.keys())
        + list(circuit_breaker.state.keys())
    )

    if not services:
        return {"status": "no_services", "services": {}}

    service_stats = {}
    for service in services:
        service_stats[service] = circuit_breaker.get_stats(service)

    # Determine overall status
    open_circuits = sum(
        1
        for service in services
        if circuit_breaker.get_state(service) == CircuitState.OPEN
    )

    if open_circuits == 0:
        overall_status = "healthy"
    elif open_circuits < len(services):
        overall_status = "degraded"
    else:
        overall_status = "critical"

    return {
        "status": overall_status,
        "open_circuits": open_circuits,
        "total_services": len(services),
        "services": service_stats,
    }
