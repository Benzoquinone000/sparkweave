"""Quality gates for Agentic RAG retrieval results."""

from __future__ import annotations

import os
from typing import Any

from .agentic_explanation import attach_agentic_explanation
from .query_planner import RagQueryPlan
from .rerank import tokenize_text


def build_agentic_quality_report(
    *,
    plan: RagQueryPlan,
    results: list[dict[str, Any]],
    merged: dict[str, Any],
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assess whether merged multi-query evidence is strong enough to answer from."""
    thresholds = _agentic_quality_thresholds(options or {})
    source_count = _coerce_non_negative_int(
        merged.get("source_count"),
        len(merged.get("sources") or []),
    )
    content_chars = len(str(merged.get("content") or merged.get("answer") or ""))
    total_subqueries = len(plan.subqueries)
    successful_subqueries = sum(1 for item in results if bool(item.get("success", True)))
    covered_subqueries = sum(1 for item in results if result_has_evidence(item))
    coverage_ratio = covered_subqueries / total_subqueries if total_subqueries else 0.0
    relevance_reports = [agentic_relevance_report(item) for item in results]
    relevant_subqueries = sum(1 for item in relevance_reports if item.get("relevant"))
    relevant_coverage_ratio = relevant_subqueries / total_subqueries if total_subqueries else 0.0
    scores = [
        score
        for source in merged.get("sources") or []
        if isinstance(source, dict)
        for score in [source_score(source)]
        if score is not None
    ]
    max_score = max(scores) if scores else None
    avg_score = sum(scores) / len(scores) if scores else None

    reasons: list[str] = []
    if source_count <= 0:
        reasons.append("no_sources")
    elif source_count < thresholds["min_sources"]:
        reasons.append("low_source_count")
    if total_subqueries and coverage_ratio < thresholds["min_coverage_ratio"]:
        reasons.append("low_subquery_coverage")
    if total_subqueries and relevant_coverage_ratio < thresholds["min_relevant_coverage_ratio"]:
        reasons.append("low_relevance_coverage")
    if content_chars < thresholds["min_context_chars"]:
        reasons.append("low_context_chars")
    min_score = thresholds.get("min_score")
    if min_score is not None and max_score is not None and max_score < min_score:
        reasons.append("low_score")
    if total_subqueries and successful_subqueries <= 0:
        reasons.append("all_subqueries_failed")

    quality_score = _agentic_quality_score(
        source_count=source_count,
        coverage_ratio=coverage_ratio,
        relevant_coverage_ratio=relevant_coverage_ratio,
        content_chars=content_chars,
        max_score=max_score,
        thresholds=thresholds,
    )
    return {
        "status": "weak" if reasons else "sufficient",
        "needs_fallback": bool(reasons),
        "reasons": reasons,
        "quality_score": quality_score,
        "source_count": source_count,
        "content_chars": content_chars,
        "total_subqueries": total_subqueries,
        "successful_subqueries": successful_subqueries,
        "covered_subqueries": covered_subqueries,
        "relevant_subqueries": relevant_subqueries,
        "coverage_ratio": round(coverage_ratio, 3),
        "relevant_coverage_ratio": round(relevant_coverage_ratio, 3),
        "max_score": round(max_score, 4) if max_score is not None else None,
        "avg_score": round(avg_score, 4) if avg_score is not None else None,
        "subquery_relevance": relevance_reports,
        "thresholds": thresholds,
        "recommendation": _agentic_quality_recommendation(reasons),
    }


def attach_agentic_quality(result: dict[str, Any], quality: dict[str, Any]) -> None:
    """Attach quality metadata and keep activity/subquery traces in sync."""
    result["agentic_quality"] = quality
    activity = result.get("agentic_activity_plan")
    if not isinstance(activity, dict):
        attach_agentic_explanation(result, quality)
        return
    activity["quality_status"] = quality.get("status")
    activity["quality_score"] = quality.get("quality_score")
    activity["covered_steps"] = quality.get("covered_subqueries")
    activity["relevant_steps"] = quality.get("relevant_subqueries")
    activity["coverage_ratio"] = quality.get("coverage_ratio")
    activity["relevant_coverage_ratio"] = quality.get("relevant_coverage_ratio")
    activity["quality_reasons"] = quality.get("reasons") or []
    activity["recommendation"] = quality.get("recommendation") or activity.get("recommendation", "")
    relevance = quality.get("subquery_relevance")
    if not isinstance(relevance, list):
        attach_agentic_explanation(result, quality)
        return
    steps = activity.get("steps")
    if isinstance(steps, list):
        for step, report in zip(steps, relevance):
            if not isinstance(step, dict) or not isinstance(report, dict):
                continue
            step["relevance_score"] = report.get("score")
            step["matched_terms"] = report.get("matched_terms") or []
            if step.get("status") == "ok" and not report.get("relevant"):
                step["status"] = "weak"
        activity["failed_steps"] = sum(
            1 for item in steps if isinstance(item, dict) and item.get("status") == "failed"
        )
        activity["weak_steps"] = sum(
            1 for item in steps if isinstance(item, dict) and item.get("status") == "weak"
        )
    subquery_results = result.get("subquery_results")
    if isinstance(subquery_results, list):
        for item, report in zip(subquery_results, relevance):
            if not isinstance(item, dict) or not isinstance(report, dict):
                continue
            item["relevance_score"] = report.get("score")
            item["matched_terms"] = report.get("matched_terms") or []
            item["relevant"] = bool(report.get("relevant"))
    attach_agentic_explanation(result, quality)


def result_has_evidence(result: dict[str, Any]) -> bool:
    return bool(result.get("sources")) and bool(str(result.get("content") or result.get("answer") or "").strip())


def agentic_relevance_report(result: dict[str, Any]) -> dict[str, Any]:
    query = str(result.get("query") or "")
    query_tokens = tokenize_text(query)
    evidence_parts = [str(result.get("content") or result.get("answer") or "")]
    for source in result.get("sources") or []:
        if not isinstance(source, dict):
            continue
        evidence_parts.extend(
            str(source.get(key) or "")
            for key in ("title", "content", "source", "evidence_reason")
        )
    evidence_tokens = tokenize_text("\n".join(evidence_parts))
    matched = sorted(query_tokens & evidence_tokens, key=lambda item: (len(item), item))
    required = {token for token in query_tokens if any(char.isascii() and char.isalnum() for char in token)}
    required_matched = sorted(required & evidence_tokens, key=lambda item: (len(item), item))
    score = len(matched) / len(query_tokens) if query_tokens else (1.0 if evidence_tokens else 0.0)
    required_ok = not required or bool(required_matched)
    relevant = bool(evidence_tokens) and required_ok and (not query_tokens or score >= 0.15)
    return {
        "query": query,
        "relevant": relevant,
        "score": round(score, 3),
        "matched_terms": matched[:8],
        "required_terms": sorted(required)[:8],
        "required_matched": required_matched[:8],
    }


def source_score(source: dict[str, Any]) -> float | None:
    raw = source.get("score")
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _agentic_quality_thresholds(options: dict[str, Any]) -> dict[str, Any]:
    min_sources_default = _coerce_non_negative_int(_env_value("RAG_AGENTIC_MIN_SOURCES"), 1)
    min_coverage_default = _coerce_ratio(_env_value("RAG_AGENTIC_MIN_COVERAGE_RATIO"), 0.5)
    min_relevant_coverage_default = _coerce_ratio(_env_value("RAG_AGENTIC_MIN_RELEVANT_COVERAGE_RATIO"), 0.67)
    min_chars_default = _coerce_non_negative_int(_env_value("RAG_AGENTIC_MIN_CONTEXT_CHARS"), 120)
    min_score_default = _coerce_non_negative_float(_env_value("RAG_AGENTIC_MIN_SCORE"), None)
    return {
        "min_sources": _coerce_non_negative_int(options.get("min_sources"), min_sources_default),
        "min_coverage_ratio": _coerce_ratio(options.get("min_coverage_ratio"), min_coverage_default),
        "min_relevant_coverage_ratio": _coerce_ratio(options.get("min_relevant_coverage_ratio"), min_relevant_coverage_default),
        "min_context_chars": _coerce_non_negative_int(options.get("min_context_chars"), min_chars_default),
        "min_score": _coerce_non_negative_float(options.get("min_score"), min_score_default),
    }


def _agentic_quality_score(
    *,
    source_count: int,
    coverage_ratio: float,
    relevant_coverage_ratio: float,
    content_chars: int,
    max_score: float | None,
    thresholds: dict[str, Any],
) -> float:
    min_sources = max(1, int(thresholds.get("min_sources") or 1))
    min_coverage = float(thresholds.get("min_coverage_ratio") or 0)
    min_relevant_coverage = float(thresholds.get("min_relevant_coverage_ratio") or 0)
    min_chars = max(1, int(thresholds.get("min_context_chars") or 1))
    components = [
        min(1.0, source_count / min_sources),
        min(1.0, coverage_ratio / min_coverage) if min_coverage > 0 else 1.0,
        min(1.0, relevant_coverage_ratio / min_relevant_coverage) if min_relevant_coverage > 0 else 1.0,
        min(1.0, content_chars / min_chars),
    ]
    min_score = thresholds.get("min_score")
    if min_score is not None and float(min_score) > 0 and max_score is not None:
        components.append(min(1.0, max_score / float(min_score)))
    return round(sum(components) / len(components), 3)


def _agentic_quality_recommendation(reasons: list[str]) -> str:
    if not reasons:
        return "Agentic evidence is sufficient for grounded synthesis."
    if "no_sources" in reasons:
        return "No usable sources were found; retry the original query with broader retrieval."
    if "low_subquery_coverage" in reasons:
        return "Some planned retrieval branches are uncovered; run baseline repair before answering."
    if "low_relevance_coverage" in reasons:
        return "Some branches returned weakly related chunks; retry the original query with broader retrieval."
    if "low_context_chars" in reasons:
        return "Retrieved context is too thin; widen candidates or lower overly strict filters."
    if "low_score" in reasons:
        return "Similarity scores are below the configured threshold; verify indexing and reranking."
    return "Evidence is weak; use a fallback retrieval path before answering."


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


def _coerce_ratio(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return min(parsed, 1.0)


def _coerce_non_negative_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default
