"""Simple provider-level circuit breaker."""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Track provider failures and temporarily block unhealthy providers."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count: dict[str, int] = {}
        self.last_failure_time: dict[str, float] = {}
        self.state: dict[str, str] = {}
        self.lock = threading.Lock()

    def call(self, provider: str) -> bool:
        """Return whether a provider call is currently allowed."""
        with self.lock:
            state = self.state.get(provider, "closed")
            if state == "closed":
                return True
            if state == "open":
                elapsed = time.time() - self.last_failure_time.get(provider, 0)
                if elapsed > self.recovery_timeout:
                    self.state[provider] = "half-open"
                    logger.info("Circuit breaker for %s entering half-open state", provider)
                    return True
                return False
            if state == "half-open":
                return True
        logger.error("Circuit breaker for %s has unexpected state: %s", provider, state)
        return False

    def record_success(self, provider: str) -> None:
        """Record a successful provider call."""
        with self.lock:
            if self.state.get(provider) == "half-open":
                self.state[provider] = "closed"
                self.failure_count[provider] = 0
                logger.info("Circuit breaker for %s closed", provider)
            elif self.state.get(provider) == "closed":
                self.failure_count[provider] = 0

    def record_failure(self, provider: str) -> None:
        """Record a failed provider call."""
        with self.lock:
            self.failure_count[provider] = self.failure_count.get(provider, 0) + 1
            self.last_failure_time[provider] = time.time()
            if self.failure_count[provider] >= self.failure_threshold:
                self.state[provider] = "open"
                logger.warning(
                    "Circuit breaker for %s opened due to %s failures",
                    provider,
                    self.failure_count[provider],
                )


circuit_breaker = CircuitBreaker()


def alert_callback(provider: str, _rate: float) -> None:
    """Alert callback used by error-rate trackers."""
    circuit_breaker.record_failure(provider)


def is_call_allowed(provider: str) -> bool:
    """Return whether a provider call is allowed."""
    return circuit_breaker.call(provider)


def record_call_success(provider: str) -> None:
    """Record a successful provider call."""
    circuit_breaker.record_success(provider)


def record_call_failure(provider: str) -> None:
    """Record a failed provider call."""
    circuit_breaker.record_failure(provider)


__all__ = [
    "CircuitBreaker",
    "alert_callback",
    "circuit_breaker",
    "is_call_allowed",
    "record_call_failure",
    "record_call_success",
]
