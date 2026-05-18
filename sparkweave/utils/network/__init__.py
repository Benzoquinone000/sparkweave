"""Network utility helpers for ``sparkweave``."""

from .circuit_breaker import (
    CircuitBreaker,
    alert_callback,
    is_call_allowed,
    record_call_failure,
    record_call_success,
)

__all__ = [
    "CircuitBreaker",
    "alert_callback",
    "is_call_allowed",
    "record_call_failure",
    "record_call_success",
]

