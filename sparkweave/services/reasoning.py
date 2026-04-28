"""Reasoning and brainstorming services for NG tools."""

from __future__ import annotations

import logging
from typing import Any

from sparkweave.services.llm import (
    get_llm_config,
    get_token_limit_kwargs,
)
from sparkweave.services.llm import (
    stream as llm_stream,
)

logger = logging.getLogger(__name__)

_BRAINSTORM_SYSTEM_PROMPT = """\
You are a breadth-first brainstorming engine.

Given a topic and optional supporting context, explore multiple promising
directions instead of converging too early on one answer.

Requirements:
- Generate 5-8 distinct possibilities from different angles when possible.
- Keep each possibility concrete and easy to scan.
- For each possibility, include a short rationale explaining why it is worth exploring.
- Prefer variety: methods, framing, applications, risks, experiments, or product directions.
- Do not pretend uncertain facts are verified.
- Keep the response concise, structured, and actionable.

Output in Markdown using this structure:

# Brainstorm

## 1. <short title>
- Direction: <1-2 sentence idea>
- Rationale: <brief why>

Continue for the remaining ideas.
"""

_REASON_SYSTEM_PROMPT = """\
You are a deep reasoning engine. You receive a problem context and a specific
reasoning focus. Perform rigorous, step-by-step logical analysis and arrive at
a clear conclusion.

Guidelines:
- Think carefully and systematically.
- Show your reasoning chain explicitly and number each step.
- If mathematical derivation is needed, show each algebraic step.
- If logical deduction is needed, state premises and inferences clearly.
- Synthesize provided context but do not fabricate facts or citations.
- Conclude with a concise, clearly labeled answer or conclusion.
"""


def _resolve_llm_args(
    *,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
    max_tokens: int | None,
    temperature: float | None,
    default_max_tokens: int,
    default_temperature: float,
) -> tuple[str | None, str | None, str, int, float]:
    try:
        config = get_llm_config()
        api_key = api_key or config.api_key
        base_url = base_url or config.base_url
        model = model or config.model
    except Exception:
        pass

    if not model:
        raise ValueError("No model configured for reasoning tool")

    return (
        api_key,
        base_url,
        model,
        max_tokens if max_tokens is not None else default_max_tokens,
        temperature if temperature is not None else default_temperature,
    )


async def _collect_stream(
    *,
    prompt: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    max_tokens: int,
    temperature: float,
) -> str:
    kwargs: dict[str, Any] = {"temperature": temperature}
    if max_tokens:
        kwargs.update(get_token_limit_kwargs(model, max_tokens))

    chunks: list[str] = []
    async for chunk in llm_stream(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        api_key=api_key,
        base_url=base_url,
        **kwargs,
    ):
        chunks.append(chunk)
    return "".join(chunks).strip()


async def brainstorm(
    *,
    topic: str,
    context: str = "",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Generate breadth-first ideas for a topic via one LLM call."""
    api_key, base_url, model, max_tokens, temperature = _resolve_llm_args(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        default_max_tokens=2048,
        default_temperature=0.8,
    )

    parts: list[str] = [f"## Topic\n{topic.strip()}"]
    if context and context.strip():
        parts.append(f"## Context\n{context.strip()}")
    user_prompt = "\n\n".join(parts)

    logger.debug("brainstorm tool: model=%s, topic=%s...", model, topic[:80])
    answer = await _collect_stream(
        prompt=user_prompt,
        system_prompt=_BRAINSTORM_SYSTEM_PROMPT,
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return {"topic": topic, "answer": answer, "model": model}


async def reason(
    *,
    query: str,
    context: str = "",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Perform deep reasoning via one stateless LLM call."""
    api_key, base_url, model, max_tokens, temperature = _resolve_llm_args(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        default_max_tokens=4096,
        default_temperature=0.0,
    )

    parts: list[str] = []
    if context and context.strip():
        parts.append(f"## Context\n{context.strip()}")
    parts.append(f"## Reasoning Focus\n{query.strip()}")
    user_prompt = "\n\n".join(parts)

    logger.debug("reason tool: model=%s, query=%s...", model, query[:80])
    answer = await _collect_stream(
        prompt=user_prompt,
        system_prompt=_REASON_SYSTEM_PROMPT,
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return {"query": query, "answer": answer, "model": model}


__all__ = ["brainstorm", "reason"]

