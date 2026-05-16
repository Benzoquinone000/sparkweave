"""Gated query planning for Agentic RAG.

The planner is deliberately conservative: most questions should use the fast
single-query RAG path. Planning only activates for complex learning questions or
when callers explicitly force it in an evaluation strategy.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
import re
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
class RagSubQuery:
    """One focused retrieval query in an agentic RAG plan."""

    query: str
    purpose: str = ""

    def trace(self) -> dict[str, str]:
        return {"query": self.query, "purpose": self.purpose}


@dataclass(frozen=True)
class RagQueryPlan:
    """A gated query plan for RAG retrieval."""

    original_query: str
    mode: str
    enabled: bool
    reason: str
    subqueries: list[RagSubQuery]
    error: str = ""

    def trace(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "agentic_mode": self.mode,
            "agentic_enabled": self.enabled,
            "agentic_reason": self.reason,
            "agentic_error": self.error,
            "subqueries": [item.trace() for item in self.subqueries],
        }


def normalize_agentic_mode(value: Any, default: str = "off") -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"force", "forced", "always", "on", "true", "1", "agentic"}:
        return "force"
    if raw in {"auto", "gated", "gated_agentic"}:
        return "auto"
    if raw in {"off", "none", "false", "0", "disabled", ""}:
        return default
    return default


async def plan_rag_queries(
    query: str,
    *,
    mode: str | None = None,
    max_subqueries: int | None = None,
    timeout_seconds: float | None = None,
) -> RagQueryPlan:
    """Return a gated plan for RAG retrieval."""
    selected_mode = normalize_agentic_mode(mode or _env("RAG_AGENTIC_MODE", "off"), "off")
    max_items = max(1, min(max_subqueries or _env_int("RAG_AGENTIC_MAX_SUBQUERIES", 3), 5))
    timeout = timeout_seconds or _env_float("RAG_AGENTIC_TIMEOUT_SECONDS", 8.0)

    if selected_mode == "off":
        return _disabled_plan(query, selected_mode, "agentic_rag_disabled")

    should_plan, reason = should_use_agentic_rag(query, mode=selected_mode)
    if not should_plan:
        return _disabled_plan(query, selected_mode, reason)

    try:
        subqueries = await asyncio.wait_for(
            _llm_plan_subqueries(query, max_subqueries=max_items),
            timeout=timeout,
        )
        subqueries = _normalize_subqueries(query, subqueries, max_items)
        if subqueries:
            return RagQueryPlan(
                original_query=query,
                mode=selected_mode,
                enabled=True,
                reason=reason,
                subqueries=subqueries,
            )
    except Exception as exc:
        fallback = _fallback_subqueries(query, max_items)
        return RagQueryPlan(
            original_query=query,
            mode=selected_mode,
            enabled=bool(fallback),
            reason=f"{reason};fallback_rule_split",
            subqueries=fallback,
            error=str(exc),
        )

    fallback = _fallback_subqueries(query, max_items)
    return RagQueryPlan(
        original_query=query,
        mode=selected_mode,
        enabled=bool(fallback),
        reason=f"{reason};fallback_rule_split",
        subqueries=fallback,
        error="empty_llm_plan",
    )


def should_use_agentic_rag(query: str, *, mode: str = "auto") -> tuple[bool, str]:
    """Heuristic gate for query planning."""
    selected_mode = normalize_agentic_mode(mode, "auto")
    if selected_mode == "force":
        return True, "forced_by_caller"

    text = str(query or "").strip()
    if not text:
        return False, "empty_query"

    question_marks = text.count("?") + text.count("？")
    if question_marks >= 2:
        return True, "multiple_questions"

    if len(text) >= _env_int("RAG_AGENTIC_MIN_QUERY_CHARS", 80):
        return True, "long_query"

    multi_intent_terms = [
        "对比",
        "比较",
        "分别",
        "同时",
        "结合",
        "总结",
        "规划",
        "路线",
        "推荐",
        "优缺点",
        "区别",
        "联系",
        "先",
        "再",
        "为什么",
        "如何",
        "compare",
        "contrast",
        "summarize",
        "plan",
    ]
    lowered = text.lower()
    hits = [term for term in multi_intent_terms if term in text or term in lowered]
    if len(hits) >= 2:
        return True, f"multi_intent_terms:{','.join(hits[:3])}"

    if re.search(r"(^|\s|[，,。；;])([1-9][\.、)]|[一二三四五六七八九十]+[、.])", text):
        return True, "enumerated_question"

    if re.search(r"(从.+角度|包含.+和|既.+又|先.+再|一方面.+另一方面)", text):
        return True, "composed_question"

    return False, "simple_query_fast_path"


async def _llm_plan_subqueries(query: str, *, max_subqueries: int) -> list[RagSubQuery]:
    from sparkweave.services.llm import complete

    prompt = (
        "请把下面的学习检索问题拆成少量彼此互补的 focused subqueries。"
        "只返回 JSON，不要解释。格式："
        '{"subqueries":[{"query":"...","purpose":"..."}]}。'
        f"最多 {max_subqueries} 个子查询，每个子查询必须能独立检索课程资料。\n\n"
        f"问题：{query}"
    )
    raw = await complete(
        prompt,
        system_prompt="你是 RAG query planner，只输出合法 JSON。",
    )
    payload = _loads_json_object(raw)
    items = payload.get("subqueries") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    subqueries: list[RagSubQuery] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subqueries.append(
            RagSubQuery(
                query=str(item.get("query") or "").strip(),
                purpose=str(item.get("purpose") or "").strip(),
            )
        )
    return subqueries


def _loads_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    payload = json.loads(text)
    return payload if isinstance(payload, dict) else {}


def _normalize_subqueries(
    original_query: str,
    subqueries: list[RagSubQuery],
    max_subqueries: int,
) -> list[RagSubQuery]:
    normalized: list[RagSubQuery] = []
    seen: set[str] = set()
    for item in subqueries:
        query = " ".join(item.query.split())
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(RagSubQuery(query=query, purpose=item.purpose.strip()))
        if len(normalized) >= max_subqueries:
            break
    if not normalized:
        normalized = _fallback_subqueries(original_query, max_subqueries)
    return normalized[:max_subqueries]


def _fallback_subqueries(query: str, max_subqueries: int) -> list[RagSubQuery]:
    parts = _split_query_parts(query)
    if len(parts) <= 1:
        parts = [query]
    return [
        RagSubQuery(query=part, purpose="fallback_split" if part != query else "original_query")
        for part in parts[:max_subqueries]
        if part
    ]


def _split_query_parts(query: str) -> list[str]:
    text = str(query or "").strip()
    raw_parts = re.split(r"[？?；;。]\s*|(?:\s+以及\s+)|(?:\s+并且\s+)|(?:\s+同时\s+)", text)
    parts = [_clean_split_part(part) for part in raw_parts if part.strip(" ，,、")]
    parts = [part for part in parts if part]
    if len(parts) > 1:
        return parts
    comma_parts = re.split(r"[，,]\s*", text)
    return [_clean_split_part(part) for part in comma_parts if len(part.strip()) >= 6]


def _clean_split_part(value: str) -> str:
    text = " ".join(str(value or "").strip(" ，,、").split())
    text = re.sub(r"^(同时|并且|以及|然后|再|还要|另外)", "", text).strip()
    return text


def _disabled_plan(query: str, mode: str, reason: str) -> RagQueryPlan:
    return RagQueryPlan(
        original_query=query,
        mode=mode,
        enabled=False,
        reason=reason,
        subqueries=[],
    )
