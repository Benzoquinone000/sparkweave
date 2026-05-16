"""Merge and fallback helpers for Agentic RAG results."""

from __future__ import annotations

import os
from typing import Any

from .agentic_activity import build_agentic_activity_plan
from .query_planner import RagQueryPlan


def merge_agentic_results(
    *,
    query: str,
    provider: str,
    plan: RagQueryPlan,
    results: list[dict[str, Any]],
    search_kwargs: dict[str, Any] | None = None,
    merge_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge branch results into a single grounded context with trace metadata."""
    sources: list[dict[str, Any]] = []
    evidence_groups: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for result in results:
        content = str(result.get("content") or result.get("answer") or "").strip()
        group_sources: list[dict[str, Any]] = []
        for source in result.get("sources") or []:
            if not isinstance(source, dict):
                continue
            enriched = dict(source)
            enriched["subquery"] = result.get("query") or ""
            enriched["subquery_index"] = result.get("subquery_index")
            enriched["subquery_purpose"] = result.get("subquery_purpose") or ""
            group_sources.append(enriched)
            key = _source_key(enriched)
            if key in seen_sources:
                continue
            seen_sources.add(key)
            sources.append(enriched)
        evidence_groups.append(
            {
                "subquery_index": result.get("subquery_index"),
                "query": result.get("query"),
                "purpose": result.get("subquery_purpose") or "",
                "success": bool(result.get("success", True)),
                "source_count": len(group_sources),
                "content_chars": len(content),
            }
        )

    source_limit = _agentic_source_limit(merge_options or {})
    if source_limit is not None:
        sources = sources[:source_limit]

    content, context_trace = _build_agentic_context_pack(
        results=results,
        search_kwargs=search_kwargs or {},
        merge_options=merge_options or {},
    )
    success_values = [bool(item.get("success", True)) for item in results]
    activity_plan = build_agentic_activity_plan(plan=plan, results=results, source_count=len(sources))
    return {
        "query": query,
        "answer": content,
        "content": content,
        "sources": sources,
        "provider": provider,
        "success": any(success_values) if success_values else False,
        "agentic_rag": True,
        "query_plan": plan.trace(),
        "agentic_activity_plan": activity_plan,
        "agentic_evidence_groups": evidence_groups,
        "agentic_context_pack": context_trace,
        "subquery_results": [
            {
                "query": item.get("query"),
                "purpose": item.get("subquery_purpose") or "",
                "success": item.get("success"),
                "source_count": len(item.get("sources") or []),
                "content_chars": len(str(item.get("content") or item.get("answer") or "")),
                "error": item.get("error") or "",
                "repair_attempted": bool(item.get("agentic_repair_attempted")),
                "repaired": bool(item.get("agentic_repair_accepted")),
            }
            for item in results
        ],
        "source_count": len(sources),
    }


def fallback_search_kwargs(search_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Return safer broad-retrieval kwargs for Agentic RAG fallback and repair."""
    kwargs = dict(search_kwargs)
    kwargs.setdefault("retrieval_mode", "hybrid")
    kwargs.setdefault("top_k", 6)
    kwargs.setdefault("candidate_top_k", 18)
    kwargs.setdefault("reranker", "keyword")
    kwargs.setdefault("rerank_top_n", 6)
    return kwargs


def _build_agentic_context_pack(
    *,
    results: list[dict[str, Any]],
    search_kwargs: dict[str, Any],
    merge_options: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    max_chars = _agentic_context_limit(search_kwargs, merge_options)
    branches = [
        {
            "query": str(result.get("query") or "subquery"),
            "content": str(result.get("content") or result.get("answer") or "").strip(),
            "subquery_index": result.get("subquery_index"),
        }
        for result in results
        if str(result.get("content") or result.get("answer") or "").strip()
    ]
    if not branches:
        return "", {
            "context_chars": 0,
            "max_context_chars": max_chars,
            "subquery_count": len(results),
            "included_subqueries": 0,
            "truncated": False,
            "branches": [],
        }

    if max_chars <= 0:
        content = "\n\n".join(f"### {item['query']}\n{item['content']}" for item in branches).strip()
        return content, {
            "context_chars": len(content),
            "max_context_chars": 0,
            "subquery_count": len(results),
            "included_subqueries": len(branches),
            "truncated": False,
            "branches": [
                {
                    "subquery_index": item["subquery_index"],
                    "query": item["query"],
                    "content_chars": len(item["content"]),
                    "included_chars": len(item["content"]),
                    "truncated": False,
                }
                for item in branches
            ],
        }

    target_per_branch = max(1, max_chars // len(branches))
    passages: list[str] = []
    branch_traces: list[dict[str, Any]] = []
    used = 0
    for offset, item in enumerate(branches):
        separator = "\n\n" if passages else ""
        header = f"### {item['query']}\n"
        remaining = max_chars - used - len(separator) - len(header)
        if remaining <= 0:
            branch_traces.append(
                {
                    "subquery_index": item["subquery_index"],
                    "query": item["query"],
                    "content_chars": len(item["content"]),
                    "included_chars": 0,
                    "truncated": True,
                }
            )
            continue
        planned = remaining if offset == len(branches) - 1 else min(target_per_branch, remaining)
        include_chars = max(0, min(len(item["content"]), planned))
        if include_chars <= 0:
            continue
        passage = f"{separator}{header}{item['content'][:include_chars]}"
        passages.append(passage)
        used += len(passage)
        branch_traces.append(
            {
                "subquery_index": item["subquery_index"],
                "query": item["query"],
                "content_chars": len(item["content"]),
                "included_chars": include_chars,
                "truncated": include_chars < len(item["content"]),
            }
        )
        if used >= max_chars:
            break

    content = "".join(passages).strip()
    return content, {
        "context_chars": len(content),
        "max_context_chars": max_chars,
        "subquery_count": len(results),
        "included_subqueries": sum(1 for item in branch_traces if int(item.get("included_chars") or 0) > 0),
        "truncated": any(bool(item.get("truncated")) for item in branch_traces),
        "branches": branch_traces,
    }


def _agentic_context_limit(search_kwargs: dict[str, Any], merge_options: dict[str, Any]) -> int:
    explicit = merge_options.get("max_context_chars")
    if explicit not in (None, ""):
        return _coerce_non_negative_int(explicit, 0)
    if search_kwargs.get("max_context_chars") not in (None, ""):
        return _coerce_non_negative_int(search_kwargs.get("max_context_chars"), 0)
    env_default = _coerce_non_negative_int(_env_value("RAG_AGENTIC_MAX_CONTEXT_CHARS"), 0)
    if env_default > 0:
        return env_default
    return _coerce_non_negative_int(_env_value("RAG_MAX_CONTEXT_CHARS"), 8000)


def _agentic_source_limit(merge_options: dict[str, Any]) -> int | None:
    explicit = merge_options.get("max_sources")
    env_value = _env_value("RAG_AGENTIC_MAX_SOURCES")
    raw = explicit if explicit not in (None, "") else env_value
    if raw in (None, ""):
        return None
    parsed = _coerce_non_negative_int(raw, 0)
    return parsed if parsed > 0 else None


def _source_key(source: dict[str, Any]) -> str:
    parts = [
        str(source.get("source") or ""),
        str(source.get("title") or ""),
        str(source.get("content") or "")[:240],
    ]
    return "\n".join(parts).lower()


def _env_value(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _coerce_non_negative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default
