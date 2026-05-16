"""Query transformation utilities for retrieval.

HyDE is useful for vague learning questions, but it should stay gated because it
adds latency and depends on an LLM call. This module keeps the feature explicit
and easy to compare in RAG evaluation experiments.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from typing import Any


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class QueryTransformResult:
    """Result of a retrieval query transform."""

    original_query: str
    retrieval_query: str
    strategy: str
    applied: bool = False
    hypothetical_answer: str = ""
    error: str = ""

    def trace(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "retrieval_query": self.retrieval_query,
            "query_transform": self.strategy,
            "query_transform_applied": self.applied,
            "query_transform_error": self.error,
            "hypothetical_answer": self.hypothetical_answer,
        }


def normalize_query_transform(value: Any, default: str = "none") -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"hyde", "hypothetical", "hypothetical_document", "hypothetical_answer"}:
        return "hyde"
    if raw in {"none", "off", "false", "0", "disabled", ""}:
        return default
    return default


async def transform_rag_query(
    query: str,
    *,
    strategy: str | None = None,
    max_chars: int | None = None,
    timeout_seconds: float | None = None,
) -> QueryTransformResult:
    """Transform a user query before vector retrieval.

    ``none`` returns the original query. ``hyde`` generates a short hypothetical
    answer and appends it to the retrieval query so embedding search has richer
    semantic anchors.
    """
    selected = normalize_query_transform(strategy or _env("RAG_QUERY_TRANSFORM", "none"), "none")
    if selected == "none":
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    if selected == "hyde":
        return await _hyde_transform(
            query=query,
            max_chars=max_chars or _env_int("RAG_HYDE_MAX_CHARS", 700),
            timeout_seconds=timeout_seconds or _env_float("RAG_HYDE_TIMEOUT_SECONDS", 8.0),
        )

    return QueryTransformResult(original_query=query, retrieval_query=query, strategy=selected)


async def _hyde_transform(query: str, *, max_chars: int, timeout_seconds: float) -> QueryTransformResult:
    try:
        hypothetical_answer = await asyncio.wait_for(
            _complete_hypothetical_answer(query=query, max_chars=max_chars),
            timeout=timeout_seconds,
        )
        hypothetical_answer = _clean_hyde_text(hypothetical_answer, max_chars=max_chars)
        if not hypothetical_answer:
            return QueryTransformResult(
                original_query=query,
                retrieval_query=query,
                strategy="hyde",
                error="empty_hypothetical_answer",
            )
        retrieval_query = f"{query}\n\n检索假设答案：\n{hypothetical_answer}"
        return QueryTransformResult(
            original_query=query,
            retrieval_query=retrieval_query,
            strategy="hyde",
            applied=True,
            hypothetical_answer=hypothetical_answer,
        )
    except Exception as exc:
        return QueryTransformResult(
            original_query=query,
            retrieval_query=query,
            strategy="hyde",
            error=str(exc),
        )


async def _complete_hypothetical_answer(query: str, *, max_chars: int) -> str:
    from sparkweave.services.llm import complete

    prompt = (
        "请为下面的学习检索问题写一段简短、事实中立的假设答案，用于帮助向量检索命中相关资料。"
        "不要编造具体页码、作者或不存在的文件名；只写可能出现在教材/讲义中的概念、公式、术语和步骤。"
        f"控制在 {max_chars} 个中文字符以内。\n\n"
        f"问题：{query}"
    )
    return await complete(
        prompt,
        system_prompt="你是一个 RAG 查询改写器，只输出用于检索的假设答案。",
    )


def _clean_hyde_text(value: str, *, max_chars: int) -> str:
    text = " ".join(str(value or "").strip().split())
    for prefix in ("假设答案：", "检索假设答案：", "答案："):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    return text[:max_chars]
