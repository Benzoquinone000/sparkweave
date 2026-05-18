"""Reusable RAG retrieval evaluation helpers.

The module intentionally keeps the evaluation loop lightweight: it measures
retrieval grounding signals that can run in local development without an LLM
judge, then emits stable JSON/Markdown reports for demos and regression checks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any


@dataclass(frozen=True)
class Strategy:
    """One retrieval configuration used in an evaluation run."""

    name: str
    params: dict[str, Any]


@dataclass
class EvalRecord:
    """Per-case result for one strategy."""

    case_id: str
    strategy: str
    success: bool
    latency_ms: float
    keyword_recall: float | None
    source_hit: bool | None
    avg_source_score: float | None
    source_count: int
    context_chars: int
    query_type: str = "untyped"
    topic: str = ""
    difficulty: str = ""
    chapter: str = ""
    source_mrr: float | None = None
    source_ndcg: float | None = None
    first_source_rank: int | None = None
    matched_keyword_count: int = 0
    evidence_reason_count: int = 0
    skipped_duplicate: int = 0
    skipped_threshold: int = 0
    skipped_budget: int = 0
    error: str = ""


QUICK_CHECK_STRATEGIES = [
    Strategy("baseline", {"top_k": 5, "max_context_chars": 6000}),
    Strategy(
        "adaptive_policy",
        {
            "retrieval_profile": "auto",
            "max_context_chars": 6000,
        },
    ),
]

DEFAULT_STRATEGIES = [
    Strategy("baseline", {"top_k": 5, "max_context_chars": 8000}),
    Strategy("dense_wide", {"top_k": 20, "max_context_chars": 12000}),
    Strategy("dense_strict", {"top_k": 12, "score_threshold": 0.35, "max_context_chars": 6000}),
]

RAG_UPGRADE_STRATEGIES = [
    Strategy("baseline", {"top_k": 5, "max_context_chars": 8000}),
    Strategy(
        "adaptive_policy",
        {
            "retrieval_profile": "auto",
            "max_context_chars": 8000,
        },
    ),
    Strategy("wide_context", {"top_k": 20, "candidate_top_k": 20, "max_context_chars": 12000}),
    Strategy(
        "hybrid_keyword_rerank",
        {
            "mode": "hybrid",
            "top_k": 5,
            "candidate_top_k": 20,
            "reranker": "keyword",
            "rerank_top_n": 5,
            "max_context_chars": 8000,
        },
    ),
    Strategy(
        "hyde_hybrid_rerank",
        {
            "mode": "hybrid",
            "query_transform": "hyde",
            "top_k": 5,
            "candidate_top_k": 20,
            "reranker": "keyword",
            "rerank_top_n": 5,
            "max_context_chars": 8000,
        },
    ),
    Strategy(
        "agentic_hyde",
        {
            "agentic_rag": "auto",
            "query_transform": "hyde",
            "agentic_max_subqueries": 3,
            "top_k": 5,
            "candidate_top_k": 12,
            "max_context_chars": 8000,
        },
    ),
]

STRATEGY_PRESETS = {
    "quick_check": QUICK_CHECK_STRATEGIES,
    "default": DEFAULT_STRATEGIES,
    "rag_upgrade": RAG_UPGRADE_STRATEGIES,
}


def strategies_for_preset(name: str | None) -> list[Strategy]:
    """Return a named strategy preset for repeatable experiments."""
    key = str(name or "default").strip().lower().replace("-", "_")
    if key not in STRATEGY_PRESETS:
        known = ", ".join(sorted(STRATEGY_PRESETS))
        raise ValueError(f"Unknown RAG eval strategy preset: {name}. Known presets: {known}")
    return list(STRATEGY_PRESETS[key])


def parse_strategy(raw: str) -> Strategy:
    """Parse ``name:key=value,key=value`` strategy syntax."""
    if ":" not in raw:
        return Strategy(raw.strip(), {})

    name, rest = raw.split(":", 1)
    params: dict[str, Any] = {}
    for item in rest.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid strategy parameter: {item}")
        key, value = item.split("=", 1)
        params[key.strip()] = _coerce_value(value.strip())
    return Strategy(name.strip(), params)


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load JSONL evaluation cases.

    Each row should include at least ``question``. ``kb_name`` can be omitted
    when the caller supplies a default knowledge base.
    """
    cases: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
        if not item.get("question"):
            raise ValueError(f"Missing question on line {line_no}")
        cases.append(item)
    return cases


def normalize_cases(cases: list[dict[str, Any]], *, default_kb: str | None = None) -> list[dict[str, Any]]:
    """Return validated, normalized case dictionaries for API callers."""
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(cases, start=1):
        if not item.get("question"):
            raise ValueError(f"Missing question in case #{index}")
        case = dict(item)
        case["id"] = str(case.get("id") or f"case-{index}")
        if default_kb and not case.get("kb_name"):
            case["kb_name"] = default_kb
        case["expected_keywords"] = _string_list(case.get("expected_keywords"))
        case["expected_sources"] = _string_list(case.get("expected_sources"))
        case["query_type"] = str(case.get("query_type") or "untyped")
        case["topic"] = str(case.get("topic") or "")
        case["difficulty"] = str(case.get("difficulty") or "")
        case["chapter"] = str(case.get("chapter") or "")
        normalized.append(case)
    return normalized


def summarize_dataset_profile(
    cases: list[dict[str, Any]],
    *,
    min_release_cases: int = 30,
) -> dict[str, Any]:
    """Summarize whether an evaluation dataset can support quality claims.

    Unlabelled smoke checks are useful after uploads and reindexing, but they
    should not be presented as release-quality regression evidence. This
    profile lets API and UI callers explain that distinction to users.
    """
    normalized = normalize_cases(cases)
    case_count = len(normalized)
    keyword_labelled_cases = sum(1 for case in normalized if _string_list(case.get("expected_keywords")))
    source_labelled_cases = sum(1 for case in normalized if _string_list(case.get("expected_sources")))
    fully_labelled_cases = sum(
        1
        for case in normalized
        if _string_list(case.get("expected_keywords")) and _string_list(case.get("expected_sources"))
    )

    keyword_coverage = _ratio(keyword_labelled_cases, case_count)
    source_coverage = _ratio(source_labelled_cases, case_count)
    full_coverage = _ratio(fully_labelled_cases, case_count)
    if case_count <= 0:
        label_status = "empty"
        label_status_label = "No cases"
        headline = "No evaluation cases were provided."
        recommendation = "Add at least one question before running retrieval evaluation."
    elif keyword_labelled_cases == 0 and source_labelled_cases == 0:
        label_status = "smoke_check"
        label_status_label = "Smoke check"
        headline = "This run checks whether retrieval works, but it has no labelled expected evidence."
        recommendation = "Use it after uploads or reindexing; add expected keywords and sources before treating results as a quality gate."
    elif fully_labelled_cases >= min_release_cases and keyword_coverage >= 0.8 and source_coverage >= 0.8:
        label_status = "release_ready"
        label_status_label = "Release dataset"
        headline = "This dataset is labelled enough for release-quality retrieval regression checks."
        recommendation = "Keep the same dataset for future RAG changes so quality deltas stay comparable."
    else:
        label_status = "partial"
        label_status_label = "Partially labelled"
        headline = "Some cases include expected evidence, so quality metrics are directional rather than final."
        recommendation = "Add expected sources and keywords to more cases before changing default retrieval strategy."

    return {
        "case_count": case_count,
        "keyword_labelled_cases": keyword_labelled_cases,
        "source_labelled_cases": source_labelled_cases,
        "fully_labelled_cases": fully_labelled_cases,
        "keyword_label_coverage": keyword_coverage,
        "source_label_coverage": source_coverage,
        "full_label_coverage": full_coverage,
        "label_status": label_status,
        "label_status_label": label_status_label,
        "headline": headline,
        "recommendation": recommendation,
        "min_release_cases": min_release_cases,
        "metrics_supported": {
            "keyword_recall": keyword_labelled_cases > 0,
            "source_hit_rate": source_labelled_cases > 0,
            "release_quality_gate": label_status == "release_ready",
        },
    }


async def run_case(
    case: dict[str, Any],
    strategy: Strategy,
    default_kb: str | None,
    default_provider: str | None = None,
) -> EvalRecord:
    """Run one case through ``rag_search`` and collect explainable metrics."""
    from sparkweave.services.rag import rag_search

    kb_name = str(case.get("kb_name") or default_kb or "").strip()
    if not kb_name:
        raise ValueError(f"Case {case.get('id') or case.get('question')} has no kb_name")

    started = time.perf_counter()
    params = dict(strategy.params)
    if default_provider and "provider" not in params:
        params["provider"] = default_provider

    try:
        result = await rag_search(query=str(case["question"]), kb_name=kb_name, **params)
        latency_ms = (time.perf_counter() - started) * 1000
        sources = result.get("sources") if isinstance(result.get("sources"), list) else []
        content = str(result.get("content") or result.get("answer") or "")
        context_pack = result.get("context_pack") if isinstance(result.get("context_pack"), dict) else {}
        expected_sources = _string_list(case.get("expected_sources"))
        source_ranks = _source_match_ranks(expected_sources, result)
        return EvalRecord(
            case_id=str(case.get("id") or case["question"]),
            strategy=strategy.name,
            success=bool(result.get("success", True)),
            latency_ms=latency_ms,
            keyword_recall=_keyword_recall(_string_list(case.get("expected_keywords")), result),
            source_hit=_source_hit_from_ranks(source_ranks),
            avg_source_score=_avg_source_score(result),
            source_count=len(sources),
            context_chars=len(content),
            query_type=str(case.get("query_type") or "untyped"),
            topic=str(case.get("topic") or ""),
            difficulty=str(case.get("difficulty") or ""),
            chapter=str(case.get("chapter") or ""),
            source_mrr=_source_mrr(source_ranks),
            source_ndcg=_source_ndcg(source_ranks, expected_count=len(expected_sources), source_count=len(sources)),
            first_source_rank=_first_source_rank(source_ranks),
            matched_keyword_count=_matched_keyword_count(sources),
            evidence_reason_count=_evidence_reason_count(sources),
            skipped_duplicate=_safe_int(context_pack.get("skipped_duplicate")),
            skipped_threshold=_safe_int(context_pack.get("skipped_threshold")),
            skipped_budget=_safe_int(context_pack.get("skipped_budget")),
            error=str(result.get("error") or ""),
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return EvalRecord(
            case_id=str(case.get("id") or case.get("question") or "unknown"),
            strategy=strategy.name,
            success=False,
            latency_ms=latency_ms,
            keyword_recall=None,
            source_hit=None,
            avg_source_score=None,
            source_count=0,
            context_chars=0,
            query_type=str(case.get("query_type") or "untyped"),
            topic=str(case.get("topic") or ""),
            difficulty=str(case.get("difficulty") or ""),
            chapter=str(case.get("chapter") or ""),
            error=str(exc),
        )


async def run_experiment(
    cases: list[dict[str, Any]],
    strategies: list[Strategy],
    default_kb: str | None,
    default_provider: str | None = None,
) -> list[EvalRecord]:
    """Run all strategies over all cases sequentially for stable comparisons."""
    records: list[EvalRecord] = []
    normalized_cases = normalize_cases(cases, default_kb=default_kb)
    for strategy in strategies:
        for case in normalized_cases:
            records.append(await run_case(case, strategy, default_kb, default_provider))
    return records


def summarize(records: list[EvalRecord], *, group_by: str | None = None) -> list[dict[str, Any]]:
    """Aggregate evaluation records by strategy, optionally by another field."""
    rows: list[dict[str, Any]] = []
    keys = _summary_keys(records, group_by)
    for key in keys:
        strategy = key[0]
        group_value = key[1] if len(key) > 1 else None
        subset = [
            item
            for item in records
            if item.strategy == strategy and (group_by is None or _group_value(item, group_by) == group_value)
        ]
        keyword_values = [item.keyword_recall for item in subset if item.keyword_recall is not None]
        source_values = [item.source_hit for item in subset if item.source_hit is not None]
        score_values = [item.avg_source_score for item in subset if item.avg_source_score is not None]
        source_mrr_values = [item.source_mrr for item in subset if item.source_mrr is not None]
        source_ndcg_values = [item.source_ndcg for item in subset if item.source_ndcg is not None]
        first_source_ranks = [item.first_source_rank for item in subset if item.first_source_rank is not None]
        latencies = [item.latency_ms for item in subset]
        row = {
            "strategy": strategy,
            "cases": len(subset),
            "success_rate": _mean([1.0 if item.success else 0.0 for item in subset]),
            "keyword_recall": _mean(keyword_values),
            "source_hit_rate": _mean([1.0 if item else 0.0 for item in source_values]),
            "avg_source_score": _mean(score_values),
            "avg_source_mrr": _mean(source_mrr_values),
            "avg_source_ndcg": _mean(source_ndcg_values),
            "avg_first_source_rank": _mean(first_source_ranks),
            "avg_source_count": _mean([item.source_count for item in subset]),
            "avg_context_chars": _mean([item.context_chars for item in subset]),
            "avg_matched_keywords": _mean([item.matched_keyword_count for item in subset]),
            "avg_evidence_reasons": _mean([item.evidence_reason_count for item in subset]),
            "avg_skipped_duplicate": _mean([item.skipped_duplicate for item in subset]),
            "avg_skipped_threshold": _mean([item.skipped_threshold for item in subset]),
            "avg_skipped_budget": _mean([item.skipped_budget for item in subset]),
            "p50_latency_ms": _percentile(latencies, 50),
            "p95_latency_ms": _percentile(latencies, 95),
        }
        if group_by is not None:
            row[group_by] = group_value
        rows.append(row)
    return rows


def calculate_deltas(summary: list[dict[str, Any]], baseline_strategy: str) -> list[dict[str, Any]]:
    """Calculate headline deltas against a baseline strategy row."""
    baseline = next((item for item in summary if item.get("strategy") == baseline_strategy), None)
    if not baseline:
        return []

    rows: list[dict[str, Any]] = []
    for row in summary:
        if row.get("strategy") == baseline_strategy:
            continue
        rows.append({
            "strategy": row.get("strategy"),
            "success_delta": _delta(row.get("success_rate"), baseline.get("success_rate")),
            "keyword_recall_delta": _delta(row.get("keyword_recall"), baseline.get("keyword_recall")),
            "source_hit_delta": _delta(row.get("source_hit_rate"), baseline.get("source_hit_rate")),
            "source_mrr_delta": _delta(row.get("avg_source_mrr"), baseline.get("avg_source_mrr")),
            "source_ndcg_delta": _delta(row.get("avg_source_ndcg"), baseline.get("avg_source_ndcg")),
            "first_source_rank_delta": _delta(row.get("avg_first_source_rank"), baseline.get("avg_first_source_rank")),
            "evidence_reason_delta": _delta(row.get("avg_evidence_reasons"), baseline.get("avg_evidence_reasons")),
            "p95_latency_delta_ms": _delta(row.get("p95_latency_ms"), baseline.get("p95_latency_ms")),
        })
    return rows


def diagnose_case_records(
    records: list[EvalRecord],
    *,
    baseline_strategy: str = "baseline",
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Build compact per-case diagnostics for explainable RAG evaluation."""
    diagnostics = [_diagnose_record(record) for record in records]
    rows = [item for item in diagnostics if item]
    rows.sort(
        key=lambda item: (
            _severity_rank(str(item.get("severity") or "")),
            str(item.get("strategy") or "") != baseline_strategy,
            str(item.get("case_id") or ""),
            str(item.get("strategy") or ""),
        )
    )
    return rows[: max(0, limit)]


def summarize_case_diagnostics(
    diagnostics: list[dict[str, Any]],
    *,
    total_records: int,
) -> dict[str, Any]:
    """Summarize diagnostic rows into one user-facing next action."""
    severity_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    affected_cases: set[str] = set()
    for item in diagnostics:
        severity = str(item.get("severity") or "low")
        issue_code = str(item.get("issue_code") or "unknown")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        issue_counts[issue_code] = issue_counts.get(issue_code, 0) + 1
        if item.get("case_id"):
            affected_cases.add(str(item["case_id"]))

    primary_issue = _primary_issue(issue_counts)
    primary_severity = _primary_severity(severity_counts)
    return {
        "total_records": total_records,
        "total_diagnostics": len(diagnostics),
        "affected_cases": len(affected_cases),
        "severity_counts": severity_counts,
        "issue_counts": issue_counts,
        "primary_issue_code": primary_issue,
        "primary_severity": primary_severity,
        "headline": _diagnostic_headline(primary_issue, len(diagnostics), len(affected_cases)),
        "recommendation": _diagnostic_recommendation(primary_issue),
    }


def summarize_strategy_outcome(
    summary: list[dict[str, Any]],
    deltas: list[dict[str, Any]],
    *,
    baseline_strategy: str = "baseline",
) -> dict[str, Any]:
    """Summarize multi-strategy evaluation into one presentation-ready conclusion."""
    if not summary:
        return {
            "baseline_strategy": baseline_strategy,
            "quality_leader": "",
            "fastest_strategy": "",
            "headline": "No RAG strategy result is available yet.",
            "recommendation": "Run an evaluation dataset before making retrieval strategy decisions.",
        }

    baseline = next((item for item in summary if item.get("strategy") == baseline_strategy), summary[0])
    quality_leader = max(summary, key=_strategy_quality_key)
    fastest = min(
        (item for item in summary if item.get("p95_latency_ms") is not None),
        key=lambda item: _numeric(item.get("p95_latency_ms"), default=float("inf")),
        default=None,
    )
    leader_name = str(quality_leader.get("strategy") or "")
    leader_delta = next((item for item in deltas if item.get("strategy") == leader_name), {})
    decision = _strategy_outcome_decision(leader_name, baseline_strategy, quality_leader, leader_delta)
    return {
        "baseline_strategy": baseline_strategy,
        "quality_leader": leader_name,
        "fastest_strategy": str(fastest.get("strategy") if fastest else ""),
        "quality_leader_metrics": _strategy_metrics(quality_leader),
        "baseline_metrics": _strategy_metrics(baseline),
        "quality_delta": dict(leader_delta),
        "quality_score": _strategy_quality_score(quality_leader),
        "baseline_quality_score": _strategy_quality_score(baseline),
        "decision": decision["decision"],
        "decision_label": decision["label"],
        "decision_reason": decision["reason"],
        "latency_tradeoff_ms": leader_delta.get("p95_latency_delta_ms"),
        "headline": _strategy_outcome_headline(quality_leader, leader_delta),
        "recommendation": _strategy_outcome_recommendation(leader_name, baseline_strategy, leader_delta),
    }


def build_quality_gate(
    summary: list[dict[str, Any]],
    diagnostic_summary: dict[str, Any],
    experiment_summary: dict[str, Any],
    *,
    baseline_strategy: str = "baseline",
    min_cases: int = 30,
) -> dict[str, Any]:
    """Convert retrieval metrics into one stable release-quality signal."""
    if not summary:
        return {
            "status": "fail",
            "status_label": "No evaluation",
            "headline": "Run a labelled RAG evaluation before trusting this knowledge base.",
            "recommendation": "Create at least one labelled dataset, then rerun the RAG quality experiment.",
            "strategy": "",
            "reasons": ["No strategy summary rows were produced."],
            "metrics": {},
            "thresholds": _quality_gate_thresholds(min_cases=min_cases),
        }

    leader_name = str(experiment_summary.get("quality_leader") or baseline_strategy or "").strip()
    leader = next((item for item in summary if str(item.get("strategy") or "") == leader_name), None)
    if leader is None:
        leader = next((item for item in summary if str(item.get("strategy") or "") == baseline_strategy), None) or summary[0]
        leader_name = str(leader.get("strategy") or leader_name or baseline_strategy)

    metrics = _quality_gate_metrics(leader)
    severity_counts = diagnostic_summary.get("severity_counts") if isinstance(diagnostic_summary.get("severity_counts"), dict) else {}
    critical_count = int(_numeric(severity_counts.get("critical"), default=0))
    high_count = int(_numeric(severity_counts.get("high"), default=0))
    total_diagnostics = int(_numeric(diagnostic_summary.get("total_diagnostics"), default=0))
    affected_cases = int(_numeric(diagnostic_summary.get("affected_cases"), default=0))
    cases = int(_numeric(metrics.get("cases"), default=0))
    decision = str(experiment_summary.get("decision") or "")

    fail_reasons: list[str] = []
    warn_reasons: list[str] = []
    if cases < max(1, min_cases // 2):
        fail_reasons.append(f"Only {cases} cases were evaluated; at least {min_cases // 2} are required for a basic gate.")
    elif cases < min_cases:
        warn_reasons.append(f"Only {cases} cases were evaluated; target baseline is {min_cases}.")

    if critical_count:
        fail_reasons.append(f"{critical_count} critical retrieval diagnostics were found.")
    if _metric_below(metrics, "success_rate", 0.95):
        fail_reasons.append("Retrieval success rate is below 95%.")
    if _metric_below(metrics, "source_hit_rate", 0.75):
        fail_reasons.append("Expected-source hit rate is below 75%.")
    if _metric_below(metrics, "avg_source_ndcg", 0.70):
        fail_reasons.append("Evidence ranking nDCG is below 70%.")
    if _metric_below(metrics, "keyword_recall", 0.55):
        fail_reasons.append("Keyword recall is below 55%.")

    if high_count:
        warn_reasons.append(f"{high_count} high-severity diagnostics need review.")
    if total_diagnostics and affected_cases:
        warn_reasons.append(f"{affected_cases} cases produced diagnostics.")
    if _metric_below(metrics, "source_hit_rate", 0.85):
        warn_reasons.append("Expected-source hit rate is below the 85% release target.")
    if _metric_below(metrics, "avg_source_ndcg", 0.80):
        warn_reasons.append("Evidence ranking nDCG is below the 80% release target.")
    if _metric_below(metrics, "keyword_recall", 0.65):
        warn_reasons.append("Keyword recall is below the 65% release target.")
    if _metric_below(metrics, "avg_evidence_reasons", 1.0):
        warn_reasons.append("Evidence reasons are sparse; explanations may feel thin.")
    if decision == "needs_more_data":
        warn_reasons.append("The strategy comparison still needs more evidence before changing defaults.")

    if fail_reasons:
        status = "fail"
    elif warn_reasons:
        status = "warn"
    else:
        status = "pass"

    return {
        "status": status,
        "status_label": {
            "pass": "Ready",
            "warn": "Needs review",
            "fail": "Blocked",
        }[status],
        "headline": _quality_gate_headline(status, leader_name, metrics),
        "recommendation": _quality_gate_recommendation(status, fail_reasons or warn_reasons),
        "strategy": leader_name,
        "reasons": (fail_reasons or warn_reasons or ["All tracked retrieval quality gates passed."])[:6],
        "metrics": metrics,
        "thresholds": _quality_gate_thresholds(min_cases=min_cases),
    }


def _diagnose_record(record: EvalRecord) -> dict[str, Any] | None:
    severity = "low"
    issue_code = ""
    issue = ""
    recommendation = ""

    if record.error:
        severity = "critical"
        issue_code = "retrieval_error"
        issue = "Retrieval execution failed."
        recommendation = "Check provider connectivity, strategy parameters, and timeout settings."
    elif not record.success:
        severity = "critical"
        issue_code = "search_failed"
        issue = "The RAG tool returned an unsuccessful result."
        recommendation = "Inspect backend logs and retry with the baseline strategy to isolate provider issues."
    elif record.source_count <= 0:
        severity = "high"
        issue_code = "no_sources"
        issue = "No supporting evidence was retrieved."
        recommendation = "Confirm the document was indexed, then widen top_k or lower the score threshold."
    elif record.source_hit is False:
        severity = "high"
        issue_code = "expected_source_missed"
        issue = "Expected source was not retrieved."
        recommendation = "Check file metadata, chunk boundaries, and whether hybrid retrieval should be enabled."
    elif record.first_source_rank is not None and record.first_source_rank > 3:
        severity = "medium"
        issue_code = "late_expected_source"
        issue = "Expected source was retrieved too late in the evidence list."
        recommendation = "Use reranking or hybrid retrieval so the strongest source appears earlier."
    elif record.keyword_recall is not None and record.keyword_recall < 0.5:
        severity = "medium"
        issue_code = "low_keyword_recall"
        issue = "Expected keywords are weakly covered."
        recommendation = "Try hybrid retrieval, HyDE query transform, or add domain synonyms to the source material."
    elif record.context_chars < 500 and record.source_count > 0:
        severity = "medium"
        issue_code = "short_context"
        issue = "Retrieved evidence is too short for a stable answer."
        recommendation = "Increase max_context_chars or use a wider candidate set before reranking."
    elif record.skipped_budget > 0:
        severity = "low"
        issue_code = "context_budget_trimmed"
        issue = "Some evidence was dropped by the context budget."
        recommendation = "Raise the context budget or use reranking to keep only the strongest chunks."
    elif record.skipped_threshold > 0 and record.source_count <= 2:
        severity = "low"
        issue_code = "threshold_trimmed"
        issue = "Score threshold may be filtering useful evidence."
        recommendation = "Lower score_threshold or compare with a dense_wide strategy."
    else:
        return None

    row: dict[str, Any] = {
        "case_id": record.case_id,
        "strategy": record.strategy,
        "query_type": record.query_type,
        "topic": record.topic,
        "difficulty": record.difficulty,
        "chapter": record.chapter,
        "severity": severity,
        "issue_code": issue_code,
        "issue": issue,
        "recommendation": recommendation,
        "keyword_recall": record.keyword_recall,
        "source_hit": record.source_hit,
        "source_mrr": record.source_mrr,
        "source_ndcg": record.source_ndcg,
        "first_source_rank": record.first_source_rank,
        "source_count": record.source_count,
        "context_chars": record.context_chars,
        "latency_ms": round(record.latency_ms, 2),
    }
    if record.error:
        row["error"] = record.error.strip().splitlines()[0][:240]
    return row


def build_report(
    records: list[EvalRecord],
    *,
    baseline_strategy: str = "baseline",
    dataset_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical JSON payload used by API, CLI and scripts."""
    summary = summarize(records)
    deltas = calculate_deltas(summary, baseline_strategy=baseline_strategy)
    case_diagnostics = diagnose_case_records(records, baseline_strategy=baseline_strategy)
    experiment_summary = summarize_strategy_outcome(summary, deltas, baseline_strategy=baseline_strategy)
    diagnostic_summary = summarize_case_diagnostics(case_diagnostics, total_records=len(records))
    return {
        "summary": summary,
        "summary_by_query_type": summarize(records, group_by="query_type"),
        "summary_by_difficulty": summarize(records, group_by="difficulty"),
        "summary_by_chapter": summarize(records, group_by="chapter"),
        "baseline_strategy": baseline_strategy,
        "deltas": deltas,
        "experiment_summary": experiment_summary,
        "dataset_profile": dataset_profile,
        "quality_gate": build_quality_gate(
            summary,
            diagnostic_summary,
            experiment_summary,
            baseline_strategy=baseline_strategy,
        ),
        "case_diagnostics": case_diagnostics,
        "diagnostic_summary": diagnostic_summary,
        "records": [record.__dict__ for record in records],
    }


async def run_evaluation(
    cases: list[dict[str, Any]],
    strategies: list[Strategy] | None = None,
    *,
    default_kb: str | None = None,
    default_provider: str | None = None,
    baseline_strategy: str = "baseline",
) -> dict[str, Any]:
    """Run a complete evaluation and return the canonical report payload."""
    normalized_cases = normalize_cases(cases, default_kb=default_kb)
    records = await run_experiment(
        cases=normalized_cases,
        strategies=strategies or DEFAULT_STRATEGIES,
        default_kb=default_kb,
        default_provider=default_provider,
    )
    return build_report(
        records,
        baseline_strategy=baseline_strategy,
        dataset_profile=summarize_dataset_profile(normalized_cases),
    )


def run_evaluation_sync(
    cases: list[dict[str, Any]],
    strategies: list[Strategy] | None = None,
    *,
    default_kb: str | None = None,
    default_provider: str | None = None,
    baseline_strategy: str = "baseline",
) -> dict[str, Any]:
    """Synchronous wrapper for CLI entry points."""
    return asyncio.run(
        run_evaluation(
            cases=cases,
            strategies=strategies,
            default_kb=default_kb,
            default_provider=default_provider,
            baseline_strategy=baseline_strategy,
        )
    )


def write_json(path: Path, records: list[EvalRecord], summary: list[dict[str, Any]], *, baseline_strategy: str | None = None) -> None:
    """Write a JSON report from precomputed records and summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    baseline = baseline_strategy or (summary[0]["strategy"] if summary else "")
    payload = build_report(records, baseline_strategy=baseline)
    payload["summary"] = summary
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_report_json(path: Path, report: dict[str, Any]) -> None:
    """Write a canonical report payload as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(
    path: Path,
    summary: list[dict[str, Any]],
    records: list[EvalRecord] | None = None,
    *,
    baseline_strategy: str | None = None,
    dataset_profile: dict[str, Any] | None = None,
) -> None:
    """Write a Markdown report from precomputed records and summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = records or []
    baseline = baseline_strategy or (summary[0]["strategy"] if summary else "")
    deltas = calculate_deltas(summary, baseline_strategy=baseline)
    outcome = summarize_strategy_outcome(summary, deltas, baseline_strategy=baseline)
    diagnostics = diagnose_case_records(records, baseline_strategy=baseline)
    diagnostic_summary = summarize_case_diagnostics(diagnostics, total_records=len(records))
    gate = build_quality_gate(summary, diagnostic_summary, outcome, baseline_strategy=baseline)
    lines = [
        "# RAG Evaluation Report",
        "",
        f"Baseline: `{baseline or '-'}`",
        "",
        "## Executive Summary",
        "",
        f"- {outcome['headline']}",
        f"- Decision: {outcome['decision_label']} ({outcome['decision_reason']})",
        f"- Quality gate: {gate['status_label']} - {gate['headline']}",
        f"- Recommendation: {outcome['recommendation']}",
    ]
    if dataset_profile:
        lines.append(
            f"- Dataset profile: {dataset_profile.get('label_status_label') or '-'} - "
            f"{dataset_profile.get('headline') or '-'}"
        )
    lines.extend([
        "",
        "## Quality Gate",
        "",
        f"- Status: `{gate['status']}` ({gate['status_label']})",
        f"- Strategy: `{gate.get('strategy') or '-'}`",
        f"- Recommendation: {gate['recommendation']}",
    ])
    for reason in gate.get("reasons") or []:
        lines.append(f"- {reason}")
    if dataset_profile:
        lines.extend(["", "## Dataset Profile", ""])
        _append_dataset_profile(lines, dataset_profile)
    lines.extend([
        "",
        "## Overall",
        "",
    ])
    _append_summary_table(lines, summary)

    by_type = summarize(records, group_by="query_type") if records else []
    if by_type:
        lines.extend(["", "## By Query Type", ""])
        _append_summary_table(lines, by_type, group_by="query_type")

    by_difficulty = _non_empty_group_summary(records, "difficulty")
    if by_difficulty:
        lines.extend(["", "## By Difficulty", ""])
        _append_summary_table(lines, by_difficulty, group_by="difficulty")

    by_chapter = _non_empty_group_summary(records, "chapter")
    if by_chapter:
        lines.extend(["", "## By Chapter", ""])
        _append_summary_table(lines, by_chapter, group_by="chapter")

    if deltas:
        lines.extend(["", "## Baseline Deltas", ""])
        _append_delta_table(lines, deltas)

    if diagnostics:
        lines.extend(["", "## Diagnostic Summary", ""])
        lines.append(f"- {diagnostic_summary['headline']}")
        lines.append(f"- Next action: {diagnostic_summary['recommendation']}")
        lines.extend(["", "## Case Diagnostics", ""])
        _append_case_diagnostics_table(lines, diagnostics)

    failures = [record for record in records if not record.success]
    if failures:
        lines.extend(["", "## Failures", ""])
        for record in failures:
            message = record.error.strip().splitlines()[0] if record.error.strip() else "Unknown error"
            lines.append(f"- `{record.strategy}` / `{record.case_id}`: {message}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report_markdown(path: Path, report: dict[str, Any]) -> None:
    """Write a Markdown report from the canonical JSON payload."""
    records = [EvalRecord(**item) for item in report.get("records", [])]
    write_markdown(
        path,
        list(report.get("summary") or []),
        records,
        baseline_strategy=str(report.get("baseline_strategy") or "baseline"),
        dataset_profile=report.get("dataset_profile") if isinstance(report.get("dataset_profile"), dict) else None,
    )


def _append_dataset_profile(lines: list[str], profile: dict[str, Any]) -> None:
    lines.extend([
        f"- Status: `{profile.get('label_status') or '-'}` ({profile.get('label_status_label') or '-'})",
        f"- Cases: {profile.get('case_count') or 0}",
        f"- Keyword-labelled cases: {profile.get('keyword_labelled_cases') or 0}",
        f"- Source-labelled cases: {profile.get('source_labelled_cases') or 0}",
        f"- Fully-labelled cases: {profile.get('fully_labelled_cases') or 0}",
        f"- Recommendation: {profile.get('recommendation') or '-'}",
    ])


def _append_summary_table(lines: list[str], rows: list[dict[str, Any]], *, group_by: str | None = None) -> None:
    headers = ["Strategy"]
    aligns = ["---"]
    if group_by:
        headers.append(group_by.replace("_", " ").title())
        aligns.append("---")
    headers.extend([
        "Cases",
        "Success",
        "Keyword Recall",
        "Source Hit",
        "MRR",
        "nDCG",
        "Avg KW",
        "Evidence",
        "Dup Skip",
        "Avg Sources",
        "Avg Context",
        "P95 Latency",
    ])
    aligns.extend(["---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"])
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(aligns) + " |")
    for row in rows:
        values = [_format_cell(row.get("strategy"))]
        if group_by:
            values.append(_format_cell(row.get(group_by)))
        values.extend([
            _format_cell(row.get("cases")),
            _format_cell(row.get("success_rate")),
            _format_cell(row.get("keyword_recall")),
            _format_cell(row.get("source_hit_rate")),
            _format_cell(row.get("avg_source_mrr")),
            _format_cell(row.get("avg_source_ndcg")),
            _format_cell(row.get("avg_matched_keywords")),
            _format_cell(row.get("avg_evidence_reasons")),
            _format_cell(row.get("avg_skipped_duplicate")),
            _format_cell(row.get("avg_source_count")),
            _format_cell(row.get("avg_context_chars")),
            _format_cell(row.get("p95_latency_ms")),
        ])
        lines.append("| " + " | ".join(values) + " |")


def _append_delta_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    lines.extend([
        "| Strategy | Success Delta | Keyword Recall Delta | Source Hit Delta | MRR Delta | nDCG Delta | Evidence Delta | P95 Latency Delta(ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in rows:
        lines.append(
            "| {strategy} | {success_delta} | {keyword_recall_delta} | {source_hit_delta} | "
            "{source_mrr_delta} | {source_ndcg_delta} | {evidence_reason_delta} | {p95_latency_delta_ms} |".format(
                **{key: _format_cell(value) for key, value in row.items()}
            )
        )


def _append_case_diagnostics_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    lines.extend([
        "| Severity | Strategy | Case | Issue | Recommendation |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in rows:
        lines.append(
            "| {severity} | {strategy} | {case_id} | {issue} | {recommendation} |".format(
                severity=_format_cell(row.get("severity")),
                strategy=_format_cell(row.get("strategy")),
                case_id=_format_cell(row.get("case_id")),
                issue=_format_cell(row.get("issue")),
                recommendation=_format_cell(row.get("recommendation")),
            )
        )


def _summary_keys(records: list[EvalRecord], group_by: str | None) -> list[tuple[str, ...]]:
    seen: set[tuple[str, ...]] = set()
    keys: list[tuple[str, ...]] = []
    for item in records:
        key = (item.strategy,) if group_by is None else (item.strategy, _group_value(item, group_by))
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _group_value(record: EvalRecord, group_by: str) -> str:
    return str(getattr(record, group_by) or "untyped")


def _non_empty_group_summary(records: list[EvalRecord], group_by: str) -> list[dict[str, Any]]:
    if not any(str(getattr(record, group_by, "") or "").strip() for record in records):
        return []
    return summarize(records, group_by=group_by)


def _coerce_value(value: str) -> Any:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _text_blob(result: dict[str, Any]) -> str:
    parts = [str(result.get("answer") or ""), str(result.get("content") or "")]
    for source in result.get("sources") or []:
        if isinstance(source, dict):
            parts.extend(str(source.get(key) or "") for key in ("title", "source", "content"))
    return "\n".join(parts).lower()


def _keyword_recall(expected_keywords: list[str], result: dict[str, Any]) -> float | None:
    keywords = [item.strip().lower() for item in expected_keywords if str(item).strip()]
    if not keywords:
        return None
    blob = _text_blob(result)
    hits = sum(1 for keyword in keywords if keyword in blob)
    return hits / len(keywords)


def _source_hit(expected_sources: list[str], result: dict[str, Any]) -> bool | None:
    return _source_hit_from_ranks(_source_match_ranks(expected_sources, result))


def _source_hit_from_ranks(source_ranks: list[int] | None) -> bool | None:
    if source_ranks is None:
        return None
    return bool(source_ranks)


def _source_match_ranks(expected_sources: list[str], result: dict[str, Any]) -> list[int] | None:
    expected = [item.strip().lower() for item in expected_sources if str(item).strip()]
    if not expected:
        return None

    remaining = list(dict.fromkeys(expected))
    ranks: list[int] = []
    for rank, source in enumerate(result.get("sources") or [], start=1):
        if not isinstance(source, dict):
            continue
        blob = "\n".join(str(source.get(key) or "") for key in ("title", "source", "content")).lower()
        matched = [item for item in remaining if item in blob]
        if not matched:
            continue
        ranks.append(rank)
        remaining = [item for item in remaining if item not in matched]
        if not remaining:
            break
    return ranks


def _first_source_rank(source_ranks: list[int] | None) -> int | None:
    if source_ranks is None or not source_ranks:
        return None
    return min(source_ranks)


def _source_mrr(source_ranks: list[int] | None) -> float | None:
    first_rank = _first_source_rank(source_ranks)
    if source_ranks is None:
        return None
    if first_rank is None:
        return 0.0
    return round(1 / first_rank, 4)


def _source_ndcg(source_ranks: list[int] | None, *, expected_count: int, source_count: int) -> float | None:
    if source_ranks is None:
        return None
    if expected_count <= 0:
        return None
    if source_count <= 0:
        return 0.0

    ideal_count = min(expected_count, source_count)
    if ideal_count <= 0:
        return 0.0

    dcg = sum(1 / math.log2(rank + 1) for rank in sorted(set(source_ranks)))
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return round(dcg / idcg, 4) if idcg else 0.0


def _avg_source_score(result: dict[str, Any]) -> float | None:
    scores = []
    for source in result.get("sources") or []:
        if not isinstance(source, dict):
            continue
        score = source.get("score")
        try:
            scores.append(float(score))
        except (TypeError, ValueError):
            pass
    return statistics.fmean(scores) if scores else None


def _matched_keyword_count(sources: list[Any]) -> int:
    total = 0
    for source in sources:
        if isinstance(source, dict) and isinstance(source.get("matched_keywords"), list):
            total += len(source["matched_keywords"])
    return total


def _evidence_reason_count(sources: list[Any]) -> int:
    return sum(1 for source in sources if isinstance(source, dict) and bool(source.get("evidence_reason")))


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _mean(values: list[float | int]) -> float | None:
    return round(float(statistics.fmean(values)), 4) if values else None


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile / 100)
    return round(float(ordered[index]), 2)


def _delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    try:
        return round(float(value) - float(baseline), 4)
    except (TypeError, ValueError):
        return None


def _severity_rank(value: str) -> int:
    order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return order.get(value, 9)


def _primary_issue(issue_counts: dict[str, int]) -> str:
    if not issue_counts:
        return ""
    return sorted(issue_counts.items(), key=lambda item: (-item[1], _issue_rank(item[0]), item[0]))[0][0]


def _primary_severity(severity_counts: dict[str, int]) -> str:
    if not severity_counts:
        return ""
    return sorted(severity_counts, key=lambda item: (_severity_rank(item), item))[0]


def _diagnostic_headline(issue_code: str, total_diagnostics: int, affected_cases: int) -> str:
    if total_diagnostics <= 0:
        return "No obvious retrieval risk was detected in this evaluation run."
    issue_labels = {
        "context_budget_trimmed": "context budget trimming",
        "expected_source_missed": "missed expected sources",
        "low_keyword_recall": "weak keyword coverage",
        "late_expected_source": "late expected sources",
        "no_sources": "missing retrieved evidence",
        "retrieval_error": "retrieval execution errors",
        "search_failed": "unsuccessful RAG calls",
        "short_context": "short retrieved context",
        "threshold_trimmed": "over-strict score threshold filtering",
    }
    label = issue_labels.get(issue_code, "retrieval quality issues")
    return f"{affected_cases} case(s) need attention; the main pattern is {label}."


def _diagnostic_recommendation(issue_code: str) -> str:
    recommendations = {
        "context_budget_trimmed": "Compare reranking and a larger max_context_chars budget, then keep the smaller setting that preserves source hit rate.",
        "expected_source_missed": "Check source metadata and chunk boundaries, then compare dense, hybrid, and Agentic plans for the affected cases.",
        "low_keyword_recall": "Try hybrid retrieval, HyDE, or domain synonym enrichment for the affected question types.",
        "late_expected_source": "Enable reranking or adjust hybrid weights so expected sources move into the first few evidence slots.",
        "no_sources": "Verify indexing first; then widen top_k or reduce score_threshold before changing the answer model.",
        "retrieval_error": "Check provider connectivity, timeout settings, and strategy parameters before tuning ranking quality.",
        "search_failed": "Re-run baseline and the failing strategy side by side to separate service issues from strategy regressions.",
        "short_context": "Increase max_context_chars or candidate_top_k, then use reranking to keep the strongest evidence.",
        "threshold_trimmed": "Lower score_threshold and compare against dense_wide to confirm whether useful evidence was filtered.",
    }
    return recommendations.get(issue_code, "Inspect the affected records, sources, and backend logs before changing strategy defaults.")


def _issue_rank(issue_code: str) -> int:
    order = {
        "retrieval_error": 0,
        "search_failed": 1,
        "no_sources": 2,
        "expected_source_missed": 3,
        "low_keyword_recall": 4,
        "late_expected_source": 5,
        "short_context": 6,
        "context_budget_trimmed": 7,
        "threshold_trimmed": 8,
    }
    return order.get(issue_code, 99)


def _strategy_quality_key(row: dict[str, Any]) -> tuple[float, float, float, float, float, float, float]:
    return (
        _numeric(row.get("success_rate"), default=-1.0),
        _numeric(row.get("source_hit_rate"), default=-1.0),
        _numeric(row.get("avg_source_ndcg"), default=-1.0),
        _numeric(row.get("avg_source_mrr"), default=-1.0),
        _numeric(row.get("keyword_recall"), default=-1.0),
        _numeric(row.get("avg_evidence_reasons"), default=0.0),
        -_numeric(row.get("p95_latency_ms"), default=1_000_000.0),
    )


def _strategy_quality_score(row: dict[str, Any]) -> float:
    success = _numeric(row.get("success_rate"), default=0.0)
    source_hit = _numeric(row.get("source_hit_rate"), default=success)
    source_ndcg = _numeric(row.get("avg_source_ndcg"), default=source_hit)
    keyword = _numeric(row.get("keyword_recall"), default=0.0)
    evidence = min(_numeric(row.get("avg_evidence_reasons"), default=0.0), 3.0) / 3.0
    score = success * 0.25 + source_hit * 0.25 + source_ndcg * 0.2 + keyword * 0.2 + evidence * 0.1
    return round(max(0.0, min(score, 1.0)), 4)


def _strategy_metrics(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "success_rate": row.get("success_rate"),
        "source_hit_rate": row.get("source_hit_rate"),
        "avg_source_mrr": row.get("avg_source_mrr"),
        "avg_source_ndcg": row.get("avg_source_ndcg"),
        "avg_first_source_rank": row.get("avg_first_source_rank"),
        "keyword_recall": row.get("keyword_recall"),
        "avg_evidence_reasons": row.get("avg_evidence_reasons"),
        "avg_source_count": row.get("avg_source_count"),
        "avg_context_chars": row.get("avg_context_chars"),
        "p95_latency_ms": row.get("p95_latency_ms"),
    }


def _quality_gate_metrics(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "cases": row.get("cases"),
        "success_rate": row.get("success_rate"),
        "source_hit_rate": row.get("source_hit_rate"),
        "avg_source_mrr": row.get("avg_source_mrr"),
        "avg_source_ndcg": row.get("avg_source_ndcg"),
        "keyword_recall": row.get("keyword_recall"),
        "avg_evidence_reasons": row.get("avg_evidence_reasons"),
        "avg_source_count": row.get("avg_source_count"),
        "avg_context_chars": row.get("avg_context_chars"),
        "p95_latency_ms": row.get("p95_latency_ms"),
        "quality_score": _strategy_quality_score(row),
    }


def _quality_gate_thresholds(*, min_cases: int) -> dict[str, Any]:
    return {
        "min_cases": min_cases,
        "hard_min_cases": max(1, min_cases // 2),
        "success_rate_fail_below": 0.95,
        "source_hit_rate_fail_below": 0.75,
        "source_hit_rate_warn_below": 0.85,
        "avg_source_ndcg_fail_below": 0.70,
        "avg_source_ndcg_warn_below": 0.80,
        "keyword_recall_fail_below": 0.55,
        "keyword_recall_warn_below": 0.65,
        "avg_evidence_reasons_warn_below": 1.0,
    }


def _metric_below(metrics: dict[str, Any], key: str, threshold: float) -> bool:
    value = metrics.get(key)
    if value is None:
        return False
    return _numeric(value, default=0.0) < threshold


def _quality_gate_headline(status: str, strategy: str, metrics: dict[str, Any]) -> str:
    source = _format_percent(metrics.get("source_hit_rate"))
    ndcg = _format_percent(metrics.get("avg_source_ndcg"))
    keyword = _format_percent(metrics.get("keyword_recall"))
    if status == "pass":
        return f"{strategy or 'Selected strategy'} is ready: source hit {source}, nDCG {ndcg}, keyword recall {keyword}."
    if status == "warn":
        return f"{strategy or 'Selected strategy'} is usable but needs review: source hit {source}, nDCG {ndcg}, keyword recall {keyword}."
    return f"{strategy or 'Selected strategy'} is blocked by quality issues: source hit {source}, nDCG {ndcg}, keyword recall {keyword}."


def _quality_gate_recommendation(status: str, reasons: list[str]) -> str:
    if status == "pass":
        return "Keep this retrieval setup as the current release baseline and monitor future regressions."
    if status == "warn":
        return "Keep the strategy gated for normal use, review the highlighted cases, then rerun the same dataset."
    if reasons and "critical" in reasons[0].lower():
        return "Fix retrieval execution errors before tuning ranking or prompt behavior."
    return "Do not promote this retrieval setup until the failed quality checks are addressed and re-evaluated."


def _strategy_outcome_decision(
    leader_name: str,
    baseline_strategy: str,
    leader: dict[str, Any],
    delta: dict[str, Any],
) -> dict[str, str]:
    if not leader_name:
        return {
            "decision": "needs_evaluation",
            "label": "Needs evaluation",
            "reason": "no strategy results are available",
        }
    if leader_name == baseline_strategy:
        return {
            "decision": "keep_baseline",
            "label": "Keep baseline",
            "reason": "baseline is still the best overall strategy",
        }

    score = _strategy_quality_score(leader)
    source_delta = _numeric(delta.get("source_hit_delta"), default=0.0)
    ndcg_delta = _numeric(delta.get("source_ndcg_delta"), default=0.0)
    keyword_delta = _numeric(delta.get("keyword_recall_delta"), default=0.0)
    latency_delta = _numeric(delta.get("p95_latency_delta_ms"), default=0.0)
    quality_gain = max(source_delta, ndcg_delta, keyword_delta)

    if score < 0.65:
        return {
            "decision": "needs_more_data",
            "label": "Needs more data",
            "reason": "the leading strategy is not reliable enough yet",
        }
    if quality_gain >= 0.08 and latency_delta <= 1200:
        return {
            "decision": "promote_default",
            "label": "Promote as default candidate",
            "reason": "quality gain is material and latency cost is acceptable",
        }
    if quality_gain >= 0.05:
        return {
            "decision": "use_for_complex_queries",
            "label": "Use for complex queries",
            "reason": "quality improves, but tradeoffs should stay gated",
        }
    return {
        "decision": "needs_more_data",
        "label": "Needs more data",
        "reason": "observed gain is too small to change defaults",
    }


def _numeric(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _strategy_outcome_headline(row: dict[str, Any], delta: dict[str, Any]) -> str:
    name = str(row.get("strategy") or "-")
    source = _format_percent(row.get("source_hit_rate"))
    ndcg = _format_percent(row.get("avg_source_ndcg"))
    keyword = _format_percent(row.get("keyword_recall"))
    latency = _format_latency(row.get("p95_latency_ms"))
    source_delta = _format_delta_percent(delta.get("source_hit_delta"))
    keyword_delta = _format_delta_percent(delta.get("keyword_recall_delta"))
    if delta:
        return (
            f"{name} currently leads: source hit {source} ({source_delta} vs baseline), "
            f"source nDCG {ndcg}, keyword recall {keyword} ({keyword_delta}), p95 latency {latency}."
        )
    return f"{name} currently leads: source hit {source}, source nDCG {ndcg}, keyword recall {keyword}, p95 latency {latency}."


def _strategy_outcome_recommendation(leader_name: str, baseline_strategy: str, delta: dict[str, Any]) -> str:
    if not leader_name:
        return "Run an evaluation dataset before changing retrieval defaults."
    if leader_name == baseline_strategy:
        return "Baseline is still the best overall; improve corpus coverage, chunking and metadata before adding complexity."

    source_delta = _numeric(delta.get("source_hit_delta"), default=0.0)
    ndcg_delta = _numeric(delta.get("source_ndcg_delta"), default=0.0)
    keyword_delta = _numeric(delta.get("keyword_recall_delta"), default=0.0)
    latency_delta = _numeric(delta.get("p95_latency_delta_ms"), default=0.0)
    best_quality_gain = max(source_delta, ndcg_delta, keyword_delta)

    if latency_delta > 1000 and best_quality_gain < 0.05:
        return f"{leader_name} has limited quality gain with higher latency; keep it as an opt-in strategy."
    if best_quality_gain >= 0.05:
        return f"Use {leader_name} for complex or high-stakes queries, and keep baseline for quick chat paths."
    return f"{leader_name} is slightly ahead; validate on a larger labelled dataset before making it the default."


def _format_percent(value: Any) -> str:
    number = _numeric(value, default=float("nan"))
    if number != number:
        return "-"
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def _format_delta_percent(value: Any) -> str:
    number = _numeric(value, default=float("nan"))
    if number != number:
        return "-"
    if abs(number) <= 1:
        number *= 100
    sign = "+" if number >= 0 else ""
    return f"{sign}{number:.1f}pp"


def _format_latency(value: Any) -> str:
    number = _numeric(value, default=float("nan"))
    if number != number:
        return "-"
    if number >= 1000:
        return f"{number / 1000:.1f}s"
    return f"{number:.0f}ms"


def _format_cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []
