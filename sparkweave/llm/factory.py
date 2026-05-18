"""Create LangChain chat models from SparkWeave's existing provider config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sparkweave.core.dependencies import dependency_error
from sparkweave.services.config import LLMConfig, get_llm_config


@dataclass
class ModelFactory:
    """Factory that hides provider-specific LangChain model construction."""

    config: LLMConfig | None = None

    def create_chat_model(self, **overrides: Any) -> Any:
        cfg = self.config or get_llm_config()
        binding = str(
            overrides.pop("binding", getattr(cfg, "binding", "openai")) or "openai"
        ).lower()
        model = overrides.pop("model", getattr(cfg, "model", None))
        api_key = overrides.pop("api_key", getattr(cfg, "api_key", ""))
        base_url = overrides.pop(
            "base_url",
            getattr(cfg, "effective_url", None) or getattr(cfg, "base_url", None),
        )
        api_version = overrides.pop("api_version", getattr(cfg, "api_version", None))
        temperature = overrides.pop("temperature", getattr(cfg, "temperature", 0.2))

        common = {
            "model": model,
            "temperature": temperature,
            **overrides,
        }

        if binding in {"anthropic", "claude"}:
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError as exc:
                raise dependency_error("langchain-anthropic") from exc
            return ChatAnthropic(api_key=api_key, **common)

        if binding == "azure_openai":
            try:
                from langchain_openai import AzureChatOpenAI
            except ImportError as exc:
                raise dependency_error("langchain-openai") from exc
            return AzureChatOpenAI(
                api_key=api_key,
                azure_endpoint=base_url,
                api_version=api_version,
                azure_deployment=model,
                temperature=temperature,
                **overrides,
            )

        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise dependency_error("langchain-openai") from exc

        return ChatOpenAI(
            api_key=api_key or "sk-no-key-required",
            base_url=base_url,
            **common,
        )


def create_chat_model(**overrides: Any) -> Any:
    """Create a LangChain chat model using the active SparkWeave config."""
    return ModelFactory().create_chat_model(**overrides)

