"""Shared exception classes for NG services and runtime code."""

from __future__ import annotations

from typing import Any


class SparkWeaveError(Exception):
    """Base class for application-level errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(SparkWeaveError):
    """Raised when configuration is invalid or incomplete."""


class ValidationError(SparkWeaveError):
    """Raised when user or API input fails validation."""


class ServiceError(SparkWeaveError):
    """Base class for service-layer failures."""


class LLMServiceError(ServiceError):
    """Base class for LLM service failures."""


class LLMContextError(LLMServiceError):
    """Raised when prompt/input exceeds the model context window."""


class EnvironmentConfigError(ConfigurationError):
    """Raised when environment variables are invalid or incomplete."""


__all__ = [
    "ConfigurationError",
    "SparkWeaveError",
    "EnvironmentConfigError",
    "LLMContextError",
    "LLMServiceError",
    "ServiceError",
    "ValidationError",
]
