"""Shared base class for NG-owned agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Awaitable, Callable
import inspect
import logging
import os
from typing import Any

from sparkweave.services import llm
from sparkweave.services.config import get_agent_params
from sparkweave.services.llm import get_llm_config, get_token_limit_kwargs
from sparkweave.services.prompting import get_prompt_manager


class BaseAgent(ABC):
    """Small NG base agent with config, prompts, tracing, and LLM helpers."""

    TraceCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

    def __init__(
        self,
        module_name: str,
        agent_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        api_version: str | None = None,
        language: str = "zh",
        binding: str | None = None,
        config: dict[str, Any] | None = None,
        token_tracker: Any | None = None,
        log_dir: str | None = None,
    ) -> None:
        del log_dir
        self.module_name = module_name
        self.agent_name = agent_name
        self.language = language
        self.config = config if isinstance(config, dict) else {}
        self.token_tracker = token_tracker
        self._trace_callback: BaseAgent.TraceCallback | None = None
        self._agent_params = get_agent_params(module_name)

        try:
            env_llm = get_llm_config()
            self.api_key = api_key or env_llm.api_key
            self.base_url = base_url or env_llm.base_url
            self.model = model or env_llm.model
            self.api_version = api_version or getattr(env_llm, "api_version", None)
            self.binding = binding or getattr(env_llm, "binding", "openai")
        except Exception:
            self.api_key = api_key or os.getenv("LLM_API_KEY")
            self.base_url = base_url or os.getenv("LLM_HOST")
            self.model = model or os.getenv("LLM_MODEL")
            self.api_version = api_version or os.getenv("LLM_API_VERSION")
            self.binding = binding or os.getenv("LLM_BINDING", "openai")

        self.agent_config = self.config.get("agents", {}).get(agent_name, {})
        self.llm_config = self.config.get("llm", {})
        self.enabled = self.agent_config.get("enabled", True)
        self.logger = logging.getLogger(f"{module_name}.{agent_name}")
        self.prompts = get_prompt_manager().load_prompts(
            module_name=module_name,
            agent_name=agent_name,
            language=language,
        )

    def get_model(self) -> str:
        """Return the active model for this agent."""
        configured = self.agent_config.get("model") or self.llm_config.get("model") or self.model
        if configured:
            return str(configured)
        env_model = os.getenv("LLM_MODEL")
        if env_model:
            return env_model
        raise ValueError(f"Model not configured for agent {self.agent_name}.")

    def get_temperature(self) -> float:
        return float(self._agent_params["temperature"])

    def get_max_tokens(self) -> int:
        return int(self._agent_params["max_tokens"])

    def get_max_retries(self) -> int:
        return int(self.agent_config.get("max_retries", 3))

    def refresh_config(self) -> None:
        """Refresh LLM runtime settings."""
        llm_config = get_llm_config()
        self.api_key = llm_config.api_key
        self.base_url = llm_config.base_url
        self.model = llm_config.model
        self.api_version = getattr(llm_config, "api_version", None)
        self.binding = getattr(llm_config, "binding", "openai")

    def set_trace_callback(self, callback: TraceCallback | None) -> None:
        self._trace_callback = callback

    async def _emit_trace_event(self, payload: dict[str, Any]) -> None:
        callback = self._trace_callback
        if callback is None:
            return
        result = callback(payload)
        if inspect.isawaitable(result):
            await result

    async def call_llm(
        self,
        user_prompt: str,
        system_prompt: str,
        messages: list[dict[str, Any]] | None = None,
        response_format: dict[str, str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Call the configured LLM and return text."""
        resolved_model = model or self.get_model()
        call_kwargs: dict[str, Any] = {
            "temperature": temperature if temperature is not None else self.get_temperature(),
            **kwargs,
        }
        limit = max_tokens if max_tokens is not None else self.get_max_tokens()
        if limit:
            call_kwargs.update(get_token_limit_kwargs(resolved_model, limit))
        if response_format and llm.supports_response_format(self.binding, resolved_model):
            call_kwargs["response_format"] = response_format
        return await llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=resolved_model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            binding=self.binding,
            messages=messages,
            max_retries=self.get_max_retries(),
            **call_kwargs,
        )

    async def stream_llm(
        self,
        user_prompt: str,
        system_prompt: str,
        messages: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from the configured LLM."""
        resolved_model = model or self.get_model()
        call_kwargs: dict[str, Any] = {
            "temperature": temperature if temperature is not None else self.get_temperature(),
            **kwargs,
        }
        limit = max_tokens if max_tokens is not None else self.get_max_tokens()
        if limit:
            call_kwargs.update(get_token_limit_kwargs(resolved_model, limit))
        async for chunk in llm.stream(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=resolved_model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            binding=self.binding,
            messages=messages,
            max_retries=self.get_max_retries(),
            **call_kwargs,
        ):
            yield chunk

    def get_prompt(
        self,
        section_or_type: str = "system",
        field_or_fallback: str | None = None,
        fallback: str = "",
    ) -> str | None:
        """Return a simple or nested prompt value."""
        if not self.prompts:
            return fallback or field_or_fallback
        value = self.prompts.get(section_or_type)
        if isinstance(value, dict) and field_or_fallback is not None:
            return value.get(field_or_fallback) or fallback or None
        if value is not None:
            return str(value)
        return field_or_fallback or fallback or None

    def has_prompts(self) -> bool:
        return self.prompts is not None

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    @abstractmethod
    async def process(self, *args: Any, **kwargs: Any) -> Any:
        """Run the agent."""


__all__ = ["BaseAgent"]

