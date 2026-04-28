"""NG-owned LLM completion and streaming helpers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
import functools
import ipaddress
import logging
import os
import re
import time
from types import TracebackType
from typing import Any, TypeVar
from urllib.parse import urlparse
import uuid

from .config import (
    LLMConfig,
    LLMConfigError,
    clear_llm_config_cache,
    find_by_name,
    get_llm_config,
    get_token_limit_kwargs,
    reload_config,
    strip_provider_prefix,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_EXPONENTIAL_BACKOFF = True

API_PROVIDER_PRESETS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "requires_key": True,
        "binding": "anthropic",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "requires_key": True,
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "requires_key": True,
        "models": [],
    },
}

LOCAL_PROVIDER_PRESETS = {
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "requires_key": False,
        "default_key": "ollama",
    },
    "lm_studio": {
        "name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "requires_key": False,
        "default_key": "lm-studio",
    },
    "vllm": {
        "name": "vLLM",
        "base_url": "http://localhost:8000/v1",
        "requires_key": False,
        "default_key": "vllm",
    },
    "llama_cpp": {
        "name": "llama.cpp",
        "base_url": "http://localhost:8080/v1",
        "requires_key": False,
        "default_key": "llama-cpp",
    },
}

CLOUD_DOMAINS = [
    ".openai.com",
    ".anthropic.com",
    ".deepseek.com",
    ".openrouter.ai",
    ".azure.com",
    ".googleapis.com",
    ".cohere.ai",
    ".mistral.ai",
    ".together.ai",
    ".fireworks.ai",
    ".groq.com",
    ".perplexity.ai",
]

LOCAL_PORTS = [
    ":1234",
    ":11434",
    ":8000",
    ":8080",
    ":5000",
    ":3000",
    ":8001",
    ":5001",
]

LOCAL_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # nosec B104
]

V1_SUFFIX_PORTS = {
    ":11434",
    ":1234",
    ":8000",
    ":8001",
    ":8080",
}

PROVIDER_CAPABILITIES: dict[str, dict[str, object]] = {
    "openai": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
        "newer_models_use_max_completion_tokens": True,
    },
    "azure_openai": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
        "newer_models_use_max_completion_tokens": True,
        "requires_api_version": True,
    },
    "anthropic": {
        "supports_response_format": False,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": False,
        "has_thinking_tags": False,
    },
    "claude": {
        "supports_response_format": False,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": False,
        "has_thinking_tags": False,
    },
    "deepseek": {
        "supports_response_format": False,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
        "system_in_messages": True,
        "has_thinking_tags": True,
    },
    "openrouter": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
        "system_in_messages": True,
    },
    "ollama": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
    "lm_studio": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
    "vllm": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
    "llama_cpp": {
        "supports_response_format": True,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_vision": False,
        "system_in_messages": True,
    },
}

DEFAULT_CAPABILITIES: dict[str, object] = {
    "supports_response_format": True,
    "supports_streaming": True,
    "supports_tools": False,
    "supports_vision": False,
    "system_in_messages": True,
    "has_thinking_tags": False,
    "forced_temperature": None,
}

MODEL_OVERRIDES: dict[str, dict[str, object]] = {
    "deepseek": {
        "supports_response_format": False,
        "has_thinking_tags": True,
        "supports_vision": False,
    },
    "deepseek-reasoner": {
        "supports_response_format": False,
        "has_thinking_tags": True,
        "supports_vision": False,
    },
    "qwen": {"has_thinking_tags": True},
    "qwq": {"has_thinking_tags": True},
    "minimax": {"supports_response_format": False},
    "gpt-5": {"forced_temperature": 1.0},
    "o1": {"forced_temperature": 1.0},
    "o3": {"forced_temperature": 1.0},
    "gpt-4o": {"supports_vision": True},
    "gpt-4-turbo": {"supports_vision": True},
    "gpt-4-vision": {"supports_vision": True},
    "claude-3": {"supports_vision": True},
    "claude-4": {"supports_vision": True},
    "gemini": {"supports_vision": True},
    "llava": {"supports_vision": True},
    "bakllava": {"supports_vision": True},
    "moondream": {"supports_vision": True},
    "minicpm-v": {"supports_vision": True},
    "gpt-3.5": {"supports_vision": False},
}


class LLMError(Exception):
    """Base exception for NG LLM errors."""

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.provider = provider

    def __str__(self) -> str:
        provider_prefix = f"[{self.provider}] " if self.provider else ""
        if self.details:
            return f"{provider_prefix}{self.message} (details: {self.details})"
        return f"{provider_prefix}{self.message}"


class LLMProviderError(LLMError):
    """Raised when there is an error with a provider."""


class LLMCircuitBreakerError(LLMError):
    """Raised when a local circuit breaker blocks execution."""


class LLMAPIError(LLMError):
    """Raised when an LLM provider API call fails."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, details, provider)
        self.status_code = status_code

    def __str__(self) -> str:
        parts = []
        if self.provider:
            parts.append(f"[{self.provider}]")
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        parts.append(self.message)
        return " ".join(parts)


class LLMTimeoutError(LLMAPIError):
    """Raised when a provider request times out."""

    def __init__(
        self,
        message: str = "Request timed out",
        timeout: float | None = None,
        provider: str | None = None,
    ) -> None:
        super().__init__(message, status_code=408, provider=provider)
        self.timeout = timeout


class LLMRateLimitError(LLMAPIError):
    """Raised when a provider rate-limits a request."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
        provider: str | None = None,
    ) -> None:
        super().__init__(message, status_code=429, provider=provider)
        self.retry_after = retry_after


class LLMAuthenticationError(LLMAPIError):
    """Raised when provider authentication fails."""

    def __init__(self, message: str = "Authentication failed", provider: str | None = None) -> None:
        super().__init__(message, status_code=401, provider=provider)


class LLMModelNotFoundError(LLMAPIError):
    """Raised when the requested model is unavailable."""

    def __init__(
        self,
        message: str = "Model not found",
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        super().__init__(message, status_code=404, provider=provider)
        self.model = model


class LLMParseError(LLMError):
    """Raised when model output cannot be parsed."""


class ProviderQuotaExceededError(LLMRateLimitError):
    """Provider-specific quota exhaustion."""


class ProviderContextWindowError(LLMAPIError):
    """Raised when input exceeds a provider context window."""


@dataclass
class TutorResponse:
    """LLM completion response container."""

    content: str
    raw_response: dict[str, object] = field(default_factory=dict)
    usage: dict[str, int] = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )
    provider: str = ""
    model: str = ""
    finish_reason: str | None = None
    cost_estimate: float = 0.0


@dataclass
class TutorStreamChunk:
    """Chunk emitted during streamed LLM responses."""

    delta: str
    content: str = ""
    provider: str = ""
    model: str = ""
    is_complete: bool = False
    usage: dict[str, int] | None = None


LLMResponse = TutorResponse
StreamChunk = TutorStreamChunk


class TrafficController:
    """Per-provider concurrency and RPM guard for LLM calls."""

    def __init__(
        self,
        provider_name: str,
        max_concurrency: int = 20,
        requests_per_minute: int = 600,
        acquisition_timeout: float = 30.0,
    ) -> None:
        self.provider_name = provider_name
        self.max_concurrency = max_concurrency
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be > 0")
        self.rpm = requests_per_minute
        self.acquisition_timeout = acquisition_timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tokens = float(requests_per_minute)
        self._last_refill = time.monotonic()
        self._fill_rate = requests_per_minute / 60.0
        self._lock = asyncio.Lock()

    async def _wait_for_token(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            new_tokens = elapsed * self._fill_rate
            if new_tokens > 0:
                self._tokens = min(float(self.rpm), self._tokens + new_tokens)
                self._last_refill = now
            if self._tokens >= 1:
                self._tokens -= 1.0
                return
            wait_time = (1.0 - self._tokens) / self._fill_rate

        if wait_time > 0:
            logger.debug("[%s] rate limit active, waiting %.2fs", self.provider_name, wait_time)
            await asyncio.sleep(wait_time)
            await self._wait_for_token()

    async def __aenter__(self) -> "TrafficController":
        await asyncio.wait_for(self._semaphore.acquire(), timeout=self.acquisition_timeout)
        try:
            await self._wait_for_token()
        except Exception:
            self._semaphore.release()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._semaphore.release()


class _ProviderRegistry:
    def __init__(self) -> None:
        self._provider_registry: dict[str, type] = {}

    def register_provider(self, name: str) -> Callable[[type], type]:
        def decorator(cls: type) -> type:
            if name in self._provider_registry:
                raise ValueError(f"Provider '{name}' is already registered")
            self._provider_registry[name] = cls
            setattr(cls, "__provider_name__", name)
            return cls

        return decorator

    def get_provider_class(self, name: str) -> type:
        return self._provider_registry[name]

    def list_providers(self) -> list[str]:
        return list(self._provider_registry.keys())

    def is_provider_registered(self, name: str) -> bool:
        return name in self._provider_registry


registry = _ProviderRegistry()
register_provider = registry.register_provider
get_provider_class = registry.get_provider_class
list_providers = registry.list_providers
is_provider_registered = registry.is_provider_registered


def _message_contains(exc: Exception, *needles: str) -> bool:
    message = str(exc).lower()
    return any(needle in message for needle in needles)


def map_error(exc: Exception, provider: str | None = None) -> LLMError:
    """Map provider/runtime exceptions to NG LLM exception classes."""
    if isinstance(exc, LLMError):
        return exc
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return LLMAuthenticationError(str(exc), provider=provider)
    if status_code == 429:
        return LLMRateLimitError(str(exc), provider=provider)
    if _message_contains(exc, "rate limit", "429", "quota"):
        return LLMRateLimitError(str(exc), provider=provider)
    if _message_contains(exc, "context length", "maximum context"):
        return ProviderContextWindowError(str(exc), provider=provider)
    return LLMAPIError(str(exc), status_code=status_code, provider=provider)


def is_local_llm_server(base_url: str, allow_private: bool | None = None) -> bool:
    """Return whether *base_url* looks like a local/private LLM server."""
    if not base_url:
        return False
    if allow_private is None:
        env_value = os.environ.get("LLM_TREAT_PRIVATE_AS_LOCAL")
        if env_value is not None:
            allow_private = env_value.strip().lower() in ("1", "true", "yes")

    base_url_lower = base_url.lower()
    if any(domain in base_url_lower for domain in CLOUD_DOMAINS):
        return False

    parsed = urlparse(base_url)
    hostname = parsed.hostname or parsed.netloc or base_url
    hostname_lower = hostname.lower()
    if any(host in hostname_lower for host in LOCAL_HOSTS):
        return True

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or (allow_private and ip.is_private):
            return True
    except ValueError:
        pass

    return any(port in base_url_lower for port in LOCAL_PORTS)


def _needs_v1_suffix(base_url: str) -> bool:
    return any(port in base_url for port in V1_SUFFIX_PORTS) and not base_url.endswith("/v1")


def sanitize_url(base_url: str, model: str = "") -> str:
    """Normalize a provider base URL while preserving provider roots."""
    del model
    if not base_url:
        return ""
    if not re.match(r"^[a-zA-Z]+://", base_url):
        base_url = f"http://{base_url}"
    url = base_url.rstrip("/")
    for suffix in ["/chat/completions", "/completions", "/messages", "/embeddings"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    if _needs_v1_suffix(url):
        url = url.rstrip("/") + "/v1"
    return url


def clean_thinking_tags(
    content: str,
    binding: str | None = None,
    model: str | None = None,
) -> str:
    """Remove model thinking tags from output."""
    del binding, model
    if not content:
        return ""
    pattern = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
    return re.sub(pattern, "", content).strip()


def build_chat_url(
    base_url: str,
    api_version: str | None = None,
    binding: str | None = None,
) -> str:
    """Build a chat endpoint URL for a provider binding."""
    base_url = base_url.rstrip("/")
    binding_lower = (binding or "openai").lower()
    if binding_lower in {"anthropic", "claude"}:
        url = f"{base_url}/messages"
    elif binding_lower == "cohere":
        url = f"{base_url}/chat"
    else:
        url = f"{base_url}/chat/completions"
    if api_version:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}api-version={api_version}"
    return url


def build_completion_url(
    base_url: str,
    api_version: str | None = None,
    binding: str | None = None,
) -> str:
    """Build a legacy completion endpoint URL."""
    if not base_url:
        return base_url
    binding_lower = (binding or "").lower()
    if binding_lower in {"anthropic", "claude"}:
        raise ValueError("Anthropic does not support /completions endpoint")
    url = base_url.rstrip("/")
    if not url.endswith("/completions"):
        url += "/completions"
    if api_version:
        separator = "&" if "?" in url else "?"
        url += f"{separator}api-version={api_version}"
    return url


def _extract_content_field(content: object) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, Mapping) and "text" in part:
                parts.append(str(part["text"]))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def extract_response_content(message: object) -> str:
    """Extract textual content from SDK-like response objects."""
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, Mapping):
        content = _extract_content_field(message.get("content"))
        if content:
            return content
        if "text" in message and message["text"] is not None:
            return str(message["text"])
        return ""
    if hasattr(message, "content"):
        content = _extract_content_field(getattr(message, "content"))
        if content:
            return content
    if hasattr(message, "text"):
        text_value = getattr(message, "text")
        if text_value is not None:
            return str(text_value)
    if hasattr(message, "model_dump"):
        try:
            dumped = message.model_dump()
        except Exception:
            dumped = None
        if dumped is not None and dumped is not message:
            return extract_response_content(dumped)
    if isinstance(message, (int, float, bool)):
        return str(message)
    return ""


def _normalize_model_name(entry: object) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, Mapping):
        for key in ("id", "name", "model"):
            value = entry.get(key)
            if isinstance(value, str):
                return value
    return None


def collect_model_names(entries: Sequence[object]) -> list[str]:
    """Collect model ids from provider payload entries."""
    names: list[str] = []
    for entry in entries:
        name = _normalize_model_name(entry)
        if name:
            names.append(name)
    return names


def build_auth_headers(api_key: str | None, binding: str | None = None) -> dict[str, str]:
    """Build provider auth headers."""
    headers = {"Content-Type": "application/json"}
    if not api_key:
        return headers
    binding_lower = (binding or "").lower()
    if binding_lower in {"anthropic", "claude"}:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif binding_lower in {"azure_openai", "azure"}:
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def get_capability(
    binding: str,
    capability: str,
    model: str | None = None,
    default: object = None,
) -> object:
    """Get a provider/model capability value."""
    binding_lower = (binding or "openai").lower()
    if model:
        model_lower = model.lower()
        for pattern, overrides in sorted(MODEL_OVERRIDES.items(), key=lambda x: -len(x[0])):
            if model_lower.startswith(pattern) and capability in overrides:
                return overrides[capability]
    provider_caps = PROVIDER_CAPABILITIES.get(binding_lower, {})
    if capability in provider_caps:
        return provider_caps[capability]
    if capability in DEFAULT_CAPABILITIES:
        return DEFAULT_CAPABILITIES[capability]
    return default


def supports_response_format(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "supports_response_format", model, default=True))


def supports_streaming(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "supports_streaming", model, default=True))


def system_in_messages(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "system_in_messages", model, default=True))


def has_thinking_tags(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "has_thinking_tags", model, default=False))


def supports_tools(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "supports_tools", model, default=False))


def supports_vision(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "supports_vision", model, default=False))


def requires_api_version(binding: str, model: str | None = None) -> bool:
    return bool(get_capability(binding, "requires_api_version", model, default=False))


def get_effective_temperature(
    binding: str,
    model: str | None = None,
    requested_temp: float = 0.7,
) -> float:
    forced_temp = get_capability(binding, "forced_temperature", model)
    if isinstance(forced_temp, (int, float)):
        return float(forced_temp)
    return requested_temp


def track_llm_call(
    provider_name: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async provider call with lightweight debug telemetry."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            logger.debug("LLM call to %s: %s", provider_name, func.__name__)
            try:
                result = await func(*args, **kwargs)
                logger.debug("LLM call to %s completed successfully", provider_name)
                return result
            except Exception as exc:
                logger.warning("LLM call to %s failed: %s", provider_name, exc)
                raise

        return wrapper

    return decorator


class BaseLLMProvider:
    """Base provider with traffic control and simple retry semantics."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.provider_name = getattr(config, "provider_name", None) or getattr(
            config,
            "binding",
            "openai",
        )
        self.api_key = getattr(config, "api_key", "")
        self.base_url = getattr(config, "base_url", None) or getattr(config, "effective_url", None)
        traffic_controller = getattr(config, "traffic_controller", None)
        self.traffic_controller = (
            traffic_controller
            if isinstance(traffic_controller, TrafficController)
            else TrafficController(
                provider_name=self.provider_name,
                max_concurrency=getattr(config, "max_concurrency", 20),
                requests_per_minute=getattr(config, "requests_per_minute", 600),
            )
        )

    async def complete(self, prompt: str, **kwargs: object) -> TutorResponse:
        raise NotImplementedError

    def stream(self, prompt: str, **kwargs: object) -> AsyncGenerator[TutorStreamChunk, None]:
        raise NotImplementedError

    def _map_exception(self, exc: Exception) -> LLMError:
        return map_error(exc, provider=self.provider_name)

    def _should_retry_error(self, error: BaseException) -> bool:
        if isinstance(error, (LLMRateLimitError, LLMTimeoutError)):
            return True
        if isinstance(error, LLMAPIError):
            status_code = error.status_code
            if status_code is None:
                return True
            return status_code >= 500
        return False

    async def _execute_core(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: object,
        **kwargs: object,
    ) -> Any:
        try:
            async with self.traffic_controller:
                return await func(*args, **kwargs)
        except Exception as exc:
            raise self._map_exception(exc) from exc

    async def execute(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: object,
        **kwargs: object,
    ) -> Any:
        return await self._execute_core(func, *args, **kwargs)

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: object,
        max_retries: int = 3,
        sleep: Callable[[int | float], Awaitable[None] | None] | None = None,
        **kwargs: object,
    ) -> Any:
        attempt = 0
        while True:
            try:
                return await self._execute_core(func, *args, **kwargs)
            except Exception as exc:
                attempt += 1
                if attempt > max_retries or not self._should_retry_error(exc):
                    raise
                delay = min(60.0, 1.5**attempt)
                if sleep is None:
                    await asyncio.sleep(delay)
                else:
                    maybe_awaitable = sleep(delay)
                    if maybe_awaitable is not None:
                        await maybe_awaitable


async def local_complete(**kwargs: object) -> str:
    return await complete(**kwargs)


async def cloud_complete(**kwargs: object) -> str:
    return await complete(**kwargs)


async def local_stream(**kwargs: object) -> AsyncGenerator[str, None]:
    async for chunk in stream(**kwargs):
        yield chunk


async def cloud_stream(**kwargs: object) -> AsyncGenerator[str, None]:
    async for chunk in stream(**kwargs):
        yield chunk


def _coerce_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def _coerce_str(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


@register_provider("routing")
class RoutingProvider(BaseLLMProvider):
    """Provider that routes between local and cloud NG completion functions."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        if is_local_llm_server(self.base_url or ""):
            self.provider_name = "local"
        else:
            self.provider_name = "routing"

    async def complete(self, prompt: str, **kwargs: object) -> TutorResponse:
        model = _coerce_str(kwargs.pop("model", None), self.config.model)
        if not model:
            raise LLMConfigError("Model is required")

        max_retries = _coerce_int(kwargs.pop("max_retries", 3), 3)
        sleep_value = kwargs.pop("sleep", None)
        sleep = sleep_value if callable(sleep_value) else None
        call_kwargs = {
            "prompt": prompt,
            "system_prompt": kwargs.pop("system_prompt", "You are a helpful assistant."),
            "model": model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "messages": kwargs.pop("messages", None),
            **kwargs,
        }
        target = local_complete if is_local_llm_server(self.base_url or "") else cloud_complete
        text = await self.execute_with_retry(target, max_retries=max_retries, sleep=sleep, **call_kwargs)
        return TutorResponse(content=str(text), provider=self.provider_name, model=model)

    def stream(self, prompt: str, **kwargs: object) -> AsyncGenerator[TutorStreamChunk, None]:
        model = _coerce_str(kwargs.pop("model", None), self.config.model)
        if not model:
            raise LLMConfigError("Model is required")
        max_retries = _coerce_int(kwargs.pop("max_retries", 3), 3)
        call_kwargs = {
            "prompt": prompt,
            "system_prompt": kwargs.pop("system_prompt", "You are a helpful assistant."),
            "model": model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "messages": kwargs.pop("messages", None),
            **kwargs,
        }
        target = local_stream if is_local_llm_server(self.base_url or "") else cloud_stream

        async def _stream() -> AsyncGenerator[TutorStreamChunk, None]:
            attempt = 0
            while True:
                attempt += 1
                emitted_any = False
                accumulated = ""
                try:
                    async with self.traffic_controller:
                        async for delta in target(**call_kwargs):
                            emitted_any = True
                            accumulated += str(delta)
                            yield TutorStreamChunk(
                                content=accumulated,
                                delta=str(delta),
                                provider=self.provider_name,
                                model=model,
                                is_complete=False,
                            )
                        yield TutorStreamChunk(
                            content=accumulated,
                            delta="",
                            provider=self.provider_name,
                            model=model,
                            is_complete=True,
                        )
                        return
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    mapped = self._map_exception(exc)
                    if emitted_any or attempt > max_retries + 1 or not self._should_retry_error(mapped):
                        raise mapped from exc
                    await asyncio.sleep(min(60.0, 1.5**attempt))

        return _stream()


def _build_messages(
    *,
    prompt: str,
    system_prompt: str,
    messages: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    if messages:
        return messages
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]


def _setup_provider_env(provider_name: str, api_key: str | None, api_base: str | None) -> None:
    spec = find_by_name(provider_name)
    if not spec or not api_key:
        return
    if spec.env_key:
        os.environ.setdefault(spec.env_key, api_key)
    effective_base = api_base or spec.default_api_base
    for env_name, env_val in spec.env_extras:
        resolved = env_val.replace("{api_key}", api_key).replace(
            "{api_base}", effective_base or ""
        )
        os.environ.setdefault(env_name, resolved)


def _resolve_model_and_base(
    provider_name: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> tuple[str, str | None, str | None]:
    spec = find_by_name(provider_name)
    resolved_model = strip_provider_prefix(model, spec) if spec else model
    effective_base = base_url or (spec.default_api_base if spec else None) or None
    effective_key = api_key
    if spec and spec.is_local and not effective_key:
        effective_key = "sk-no-key-required"
    return resolved_model, effective_base, effective_key


def _response_content(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        value = message.get("content", "")
    else:
        value = getattr(message, "content", "")
    if value is None:
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(getattr(item, "text", "") or getattr(item, "content", "") or ""))
        return "".join(parts)
    return str(value)


def _is_retriable_error(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, GeneratorExit)):
        return False
    if isinstance(exc, LLMConfigError):
        return False
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        if status_code == 429 or status_code >= 500:
            return True
        if 400 <= status_code < 500:
            return False
    return True


def _retry_delay(attempt: int, base_delay: float, exponential_backoff: bool) -> float:
    if not exponential_backoff:
        return base_delay
    return min(base_delay * (2**attempt), 120.0)


def _resolve_call_config(
    *,
    model: str | None,
    api_key: str | None,
    base_url: str | None,
    api_version: str | None,
    binding: str | None,
    extra_headers: dict[str, str] | None,
    reasoning_effort: str | None,
) -> tuple[
    str,
    str | None,
    str | None,
    str | None,
    str,
    str,
    dict[str, str],
    str | None,
    str,
]:
    provider_name = binding or "openai"
    provider_mode = "standard"
    resolved_headers: dict[str, str] = {}

    if not model or not base_url or api_key is None or not binding:
        config = get_llm_config()
        model = model or config.model
        api_key = api_key if api_key is not None else config.api_key
        base_url = base_url or config.effective_url or config.base_url
        api_version = api_version or config.api_version
        binding = binding or config.binding or "openai"
        provider_name = getattr(config, "provider_name", binding or "openai")
        provider_mode = getattr(config, "provider_mode", "standard")
        resolved_headers = dict(getattr(config, "extra_headers", {}) or {})
        if reasoning_effort is None:
            reasoning_effort = getattr(config, "reasoning_effort", None)
    else:
        spec = find_by_name(provider_name)
        if spec is not None:
            provider_name = spec.name
            provider_mode = spec.mode

    if not model:
        raise LLMConfigError("Model is required for an NG LLM call")

    if extra_headers:
        resolved_headers.update(extra_headers)

    return (
        model,
        api_key,
        base_url,
        api_version,
        binding or provider_name,
        provider_name,
        resolved_headers,
        reasoning_effort,
    ) + (provider_mode,)


def _token_payload(model: str, kwargs: dict[str, object]) -> dict[str, object]:
    if "max_completion_tokens" in kwargs:
        return {"max_completion_tokens": kwargs.pop("max_completion_tokens")}
    max_tokens = int(kwargs.pop("max_tokens", 4096) or 4096)
    return get_token_limit_kwargs(model, max_tokens)


def _client_kwargs(
    *,
    provider_name: str,
    api_key: str | None,
    base_url: str | None,
    api_version: str | None,
    extra_headers: dict[str, str],
) -> tuple[type[Any], dict[str, Any]]:
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    headers = {"x-session-affinity": uuid.uuid4().hex}
    headers.update(extra_headers)
    spec = find_by_name(provider_name)
    if provider_name == "azure_openai":
        return (
            AsyncAzureOpenAI,
            {
                "api_key": api_key or "no-key",
                "azure_endpoint": base_url,
                "api_version": api_version or "2024-02-15-preview",
                "default_headers": headers,
                "max_retries": 0,
            },
        )

    default_base = spec.default_api_base if spec else None
    return (
        AsyncOpenAI,
        {
            "api_key": api_key or "no-key",
            "base_url": base_url or default_base,
            "default_headers": headers,
            "max_retries": 0,
        },
    )


async def sdk_complete(
    *,
    prompt: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    api_version: str | None,
    provider_name: str,
    binding: str | None = None,
    messages: list[dict[str, object]] | None,
    extra_headers: dict[str, str],
    reasoning_effort: str | None,
    kwargs: dict[str, object],
) -> str:
    del binding
    _setup_provider_env(provider_name, api_key, base_url)
    resolved_model, effective_base, effective_key = _resolve_model_and_base(
        provider_name, model, api_key, base_url
    )
    client_cls, client_kwargs = _client_kwargs(
        provider_name=provider_name,
        api_key=effective_key,
        base_url=effective_base,
        api_version=api_version,
        extra_headers=extra_headers,
    )
    client = client_cls(**client_kwargs)

    payload: dict[str, object] = {
        "model": resolved_model,
        "messages": _build_messages(
            prompt=prompt,
            system_prompt=system_prompt,
            messages=messages,
        ),
        "temperature": float(kwargs.pop("temperature", 0.7) or 0.7),
    }
    payload.update(_token_payload(resolved_model, kwargs))
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    payload.update(kwargs)

    response = await client.chat.completions.create(**payload)
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None and isinstance(choice, dict):
        message = choice.get("message")
    return _response_content(message)


async def sdk_stream(
    *,
    prompt: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    api_version: str | None,
    provider_name: str,
    binding: str | None = None,
    messages: list[dict[str, object]] | None,
    extra_headers: dict[str, str],
    reasoning_effort: str | None,
    kwargs: dict[str, object],
) -> AsyncGenerator[str, None]:
    del binding
    _setup_provider_env(provider_name, api_key, base_url)
    resolved_model, effective_base, effective_key = _resolve_model_and_base(
        provider_name, model, api_key, base_url
    )
    client_cls, client_kwargs = _client_kwargs(
        provider_name=provider_name,
        api_key=effective_key,
        base_url=effective_base,
        api_version=api_version,
        extra_headers=extra_headers,
    )
    client = client_cls(**client_kwargs)
    call_kwargs = dict(kwargs)
    payload: dict[str, object] = {
        "model": resolved_model,
        "messages": _build_messages(
            prompt=prompt,
            system_prompt=system_prompt,
            messages=messages,
        ),
        "temperature": float(call_kwargs.pop("temperature", 0.7) or 0.7),
        "stream": True,
    }
    payload.update(_token_payload(resolved_model, call_kwargs))
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    payload.update(call_kwargs)

    stream_response = await client.chat.completions.create(**payload)
    async for chunk in stream_response:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        choice = choices[0]
        delta = getattr(choice, "delta", None)
        if delta is None and isinstance(choice, dict):
            delta = choice.get("delta")
        content = _response_content(delta)
        if content:
            yield content


def litellm_available() -> bool:
    """Return whether LiteLLM is available for gateway providers."""
    try:
        import litellm  # noqa: F401
    except ImportError:
        return False
    return True


async def litellm_complete(**kwargs: object) -> str:
    return await sdk_complete(**kwargs)  # type: ignore[arg-type]


async def litellm_stream(**kwargs: object) -> AsyncGenerator[str, None]:
    async for chunk in sdk_stream(**kwargs):  # type: ignore[arg-type]
        yield chunk


async def complete(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    api_version: str | None = None,
    binding: str | None = None,
    messages: list[dict[str, object]] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    exponential_backoff: bool = DEFAULT_EXPONENTIAL_BACKOFF,
    **kwargs: object,
) -> str:
    """Call the configured chat-completion provider and return text."""
    caller_headers = kwargs.pop("extra_headers", None)
    extra_headers = caller_headers if isinstance(caller_headers, dict) else None
    reasoning_effort = kwargs.pop("reasoning_effort", None)
    (
        model,
        api_key,
        base_url,
        api_version,
        _binding,
        provider_name,
        resolved_headers,
        resolved_reasoning_effort,
        provider_mode,
    ) = _resolve_call_config(
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        binding=binding,
        extra_headers=extra_headers,
        reasoning_effort=str(reasoning_effort) if reasoning_effort else None,
    )

    if provider_mode == "oauth":
        raise LLMConfigError(
            f"{provider_name} requires OAuth session. Run provider login before using it."
        )

    total_attempts = max_retries + 1
    last_exc: BaseException | None = None
    for attempt in range(total_attempts):
        try:
            executor = (
                litellm_complete
                if provider_mode != "direct" and litellm_available()
                else sdk_complete
            )
            return await executor(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                api_key=api_key,
                base_url=base_url,
                api_version=api_version,
                binding=_binding,
                provider_name=provider_name,
                messages=messages,
                extra_headers=resolved_headers,
                reasoning_effort=resolved_reasoning_effort,
                kwargs=dict(kwargs),
            )
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not _is_retriable_error(exc):
                raise
            delay = _retry_delay(attempt, retry_delay, exponential_backoff)
            logger.warning(
                "NG LLM call failed (attempt %s/%s), retrying in %.1fs: %s",
                attempt + 1,
                total_attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc
    return ""


async def stream(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    api_version: str | None = None,
    binding: str | None = None,
    messages: list[dict[str, object]] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    exponential_backoff: bool = DEFAULT_EXPONENTIAL_BACKOFF,
    **kwargs: object,
) -> AsyncGenerator[str, None]:
    """Stream text chunks from the configured chat-completion provider."""
    caller_headers = kwargs.pop("extra_headers", None)
    extra_headers = caller_headers if isinstance(caller_headers, dict) else None
    reasoning_effort = kwargs.pop("reasoning_effort", None)
    (
        model,
        api_key,
        base_url,
        api_version,
        _binding,
        provider_name,
        resolved_headers,
        resolved_reasoning_effort,
        provider_mode,
    ) = _resolve_call_config(
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        binding=binding,
        extra_headers=extra_headers,
        reasoning_effort=str(reasoning_effort) if reasoning_effort else None,
    )

    if provider_mode == "oauth":
        raise LLMConfigError(
            f"{provider_name} requires OAuth session. Run provider login before using it."
        )

    total_attempts = max_retries + 1
    last_exc: BaseException | None = None
    for attempt in range(total_attempts):
        emitted_any = False
        try:
            executor = (
                litellm_stream
                if provider_mode != "direct" and litellm_available()
                else sdk_stream
            )
            async for content in executor(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                api_key=api_key,
                base_url=base_url,
                api_version=api_version,
                binding=_binding,
                provider_name=provider_name,
                messages=messages,
                extra_headers=resolved_headers,
                reasoning_effort=resolved_reasoning_effort,
                kwargs=dict(kwargs),
            ):
                emitted_any = True
                yield content
            return
        except Exception as exc:
            last_exc = exc
            if emitted_any or attempt >= max_retries or not _is_retriable_error(exc):
                raise
            delay = _retry_delay(attempt, retry_delay, exponential_backoff)
            logger.warning(
                "NG LLM stream failed (attempt %s/%s), retrying in %.1fs: %s",
                attempt + 1,
                total_attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc


class LLMClient:
    """Small convenience wrapper around the NG completion functions."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> str:
        return await complete(
            prompt=prompt,
            system_prompt=system_prompt or "You are a helpful assistant.",
            model=kwargs.pop("model", self.config.model),
            api_key=kwargs.pop("api_key", self.config.api_key),
            base_url=kwargs.pop("base_url", self.config.effective_url or self.config.base_url),
            api_version=kwargs.pop("api_version", self.config.api_version),
            binding=kwargs.pop("binding", self.config.binding),
            messages=kwargs.pop("messages", history),
            **kwargs,
        )

    def complete_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> str:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.complete(
                    prompt,
                    system_prompt=system_prompt,
                    history=history,
                    **kwargs,
                )
            )
        raise RuntimeError("complete_sync cannot be called from a running event loop")

    def get_model_func(self) -> Callable[..., Awaitable[str]]:
        async def _model_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, str]] | None = None,
            **kwargs: object,
        ) -> str:
            return await self.complete(
                prompt,
                system_prompt=system_prompt,
                history=history_messages,
                **kwargs,
            )

        return _model_func

    def get_vision_model_func(self) -> Callable[..., Awaitable[str]]:
        async def _vision_func(
            prompt: str,
            image_data: str | None = None,
            messages: list[dict[str, object]] | None = None,
            **kwargs: object,
        ) -> str:
            return await self.complete(
                prompt,
                messages=messages,
                image_data=image_data,
                **kwargs,
            )

        return _vision_func


async def fetch_models(
    binding: str,
    base_url: str,
    api_key: str | None = None,
) -> list[str]:
    """Fetch model ids from an OpenAI-compatible endpoint."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key or "no-key", base_url=base_url, max_retries=0)
    response = await client.models.list()
    return [str(item.id) for item in getattr(response, "data", [])]


def get_provider_presets() -> dict[str, dict[str, dict[str, object]]]:
    """Return provider presets for UI/CLI consumers."""
    return {"api": API_PROVIDER_PRESETS, "local": LOCAL_PROVIDER_PRESETS}


def reset_llm_client() -> None:
    """Compatibility reset hook for callers that expect an LLM client cache."""
    clear_llm_config_cache()


__all__ = [
    "API_PROVIDER_PRESETS",
    "BaseLLMProvider",
    "CLOUD_DOMAINS",
    "DEFAULT_CAPABILITIES",
    "DEFAULT_EXPONENTIAL_BACKOFF",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY",
    "LLMCircuitBreakerError",
    "LLMAPIError",
    "LLMAuthenticationError",
    "LLMClient",
    "LLMConfig",
    "LLMConfigError",
    "LLMError",
    "LLMModelNotFoundError",
    "LLMParseError",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMTimeoutError",
    "LOCAL_PROVIDER_PRESETS",
    "LOCAL_HOSTS",
    "LOCAL_PORTS",
    "MODEL_OVERRIDES",
    "PROVIDER_CAPABILITIES",
    "ProviderContextWindowError",
    "ProviderQuotaExceededError",
    "RoutingProvider",
    "StreamChunk",
    "TrafficController",
    "TutorResponse",
    "TutorStreamChunk",
    "V1_SUFFIX_PORTS",
    "build_auth_headers",
    "build_chat_url",
    "build_completion_url",
    "clean_thinking_tags",
    "cloud_complete",
    "cloud_stream",
    "collect_model_names",
    "complete",
    "extract_response_content",
    "fetch_models",
    "get_capability",
    "get_effective_temperature",
    "get_provider_class",
    "get_llm_config",
    "get_provider_presets",
    "get_token_limit_kwargs",
    "has_thinking_tags",
    "is_local_llm_server",
    "is_provider_registered",
    "list_providers",
    "litellm_available",
    "litellm_complete",
    "litellm_stream",
    "local_complete",
    "local_stream",
    "map_error",
    "register_provider",
    "registry",
    "requires_api_version",
    "reload_config",
    "reset_llm_client",
    "sanitize_url",
    "sdk_complete",
    "sdk_stream",
    "stream",
    "supports_response_format",
    "supports_streaming",
    "supports_tools",
    "supports_vision",
    "system_in_messages",
    "track_llm_call",
]
