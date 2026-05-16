"""RAG search-test and evaluation operations for knowledge-base routes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any


def build_rag_search_kwargs(request: Any) -> dict[str, Any]:
    search_kwargs: dict[str, Any] = {
        "top_k": request.top_k,
        "max_context_chars": request.max_context_chars,
    }
    if request.candidate_top_k is not None:
        search_kwargs["candidate_top_k"] = max(request.candidate_top_k, request.top_k)
    if request.retrieval_profile:
        search_kwargs["retrieval_profile"] = request.retrieval_profile
    if request.retrieval_mode:
        search_kwargs["retrieval_mode"] = request.retrieval_mode
    if request.reranker:
        search_kwargs["reranker"] = request.reranker
    if request.query_transform:
        search_kwargs["query_transform"] = request.query_transform
    if request.agentic_rag is not None:
        search_kwargs["agentic_rag"] = request.agentic_rag
    if request.agentic_max_context_chars is not None:
        search_kwargs["agentic_max_context_chars"] = request.agentic_max_context_chars
    if request.agentic_max_sources is not None:
        search_kwargs["agentic_max_sources"] = request.agentic_max_sources
    if request.agentic_min_sources is not None:
        search_kwargs["agentic_min_sources"] = request.agentic_min_sources
    if request.agentic_min_coverage_ratio is not None:
        search_kwargs["agentic_min_coverage_ratio"] = request.agentic_min_coverage_ratio
    if request.agentic_min_relevant_coverage_ratio is not None:
        search_kwargs["agentic_min_relevant_coverage_ratio"] = (
            request.agentic_min_relevant_coverage_ratio
        )
    if request.agentic_min_context_chars is not None:
        search_kwargs["agentic_min_context_chars"] = request.agentic_min_context_chars
    if request.agentic_min_score is not None:
        search_kwargs["agentic_min_score"] = request.agentic_min_score
    return search_kwargs


def format_rag_search_result(
    *,
    kb_name: str,
    query: str,
    provider: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    content = str(result.get("content") or result.get("answer") or "")
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    return {
        "kb_name": kb_name,
        "query": query,
        "provider": result.get("provider") or provider,
        "success": bool(result.get("success", True)),
        "content": content,
        "answer": result.get("answer") or content,
        "sources": sources,
        "source_count": result.get("source_count", len(sources)),
        "retrieval_profile": result.get("retrieval_profile"),
        "retrieval_mode": result.get("retrieval_mode"),
        "requested_retrieval_mode": result.get("requested_retrieval_mode"),
        "indexed_retrieval_mode": result.get("indexed_retrieval_mode"),
        "query_transform": result.get("query_transform"),
        "query_transform_applied": result.get("query_transform_applied"),
        "agentic_rag": result.get("agentic_rag"),
        "agentic_fallback": result.get("agentic_fallback"),
        "agentic_fallback_reason": result.get("agentic_fallback_reason"),
        "agentic_quality": result.get("agentic_quality"),
        "agentic_repair": result.get("agentic_repair"),
        "agentic_explanation": result.get("agentic_explanation"),
        "agentic_activity_plan": result.get("agentic_activity_plan"),
        "agentic_evidence_groups": result.get("agentic_evidence_groups"),
        "agentic_context_pack": result.get("agentic_context_pack"),
        "subquery_results": result.get("subquery_results"),
        "query_plan": result.get("query_plan"),
        "failed_query_plan": result.get("failed_query_plan"),
        "context_pack": result.get("context_pack"),
        "error": result.get("error"),
        "error_code": result.get("error_code"),
        "error_detail": result.get("error_detail"),
        "readiness": result.get("readiness"),
        "diagnostic": result.get("diagnostic"),
    }


async def run_rag_search_test(
    *,
    kb_name: str,
    request: Any,
    manager: Any,
    kb_entry: dict[str, Any],
    default_provider: str,
    validate_provider: Callable[[str | None], str],
    rag_service_cls: Callable[..., Any],
) -> dict[str, Any]:
    query = request.query.strip()
    if not query:
        raise ValueError("Query cannot be empty")

    provider = validate_provider(request.provider or kb_entry.get("rag_provider") or default_provider)
    result = await rag_service_cls(
        kb_base_dir=str(manager.base_dir),
        provider=provider,
    ).search(
        query=query,
        kb_name=kb_name,
        **build_rag_search_kwargs(request),
    )
    return format_rag_search_result(
        kb_name=kb_name,
        query=query,
        provider=provider,
        result=result,
    )


async def run_rag_evaluation_report(
    *,
    kb_name: str,
    request: Any,
    manager: Any,
    kb_entry: dict[str, Any],
    default_provider: str,
    validate_provider: Callable[[str | None], str],
    evaluation_strategies_or_default: Callable[[Any, str | None], Any],
    model_dump: Callable[[Any], dict[str, Any]],
    run_evaluation: Callable[..., Any],
    summarize_dataset_profile: Callable[[list[dict[str, Any]]], dict[str, Any]],
    save_latest_report: Callable[[Any, str, dict[str, Any]], None],
) -> dict[str, Any]:
    if not request.cases:
        raise ValueError("At least one evaluation case is required")
    if len(request.cases) > 80:
        raise ValueError("RAG evaluation accepts at most 80 cases per request")

    provider = validate_provider(request.provider or kb_entry.get("rag_provider") or default_provider)
    strategies = evaluation_strategies_or_default(request.strategies, request.preset)
    cases = [model_dump(case) for case in request.cases]
    report = await run_evaluation(
        cases=cases,
        strategies=strategies,
        default_kb=kb_name,
        default_provider=provider,
        baseline_strategy=request.baseline_strategy or "baseline",
    )
    report.setdefault("dataset_profile", summarize_dataset_profile(cases))
    payload = {
        "kb_name": kb_name,
        "provider": provider,
        "created_at": datetime.now().isoformat(),
        "strategy_count": len(strategies),
        "case_count": len(cases),
        "preset": "custom" if request.strategies else (request.preset or "default"),
        **report,
    }
    save_latest_report(manager, kb_name, payload)
    return payload
