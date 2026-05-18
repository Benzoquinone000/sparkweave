"""User-facing explanations for Agentic RAG retrieval decisions."""

from __future__ import annotations

from typing import Any


def build_agentic_explanation(
    *,
    result: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    """Build the structured explanation attached to an Agentic RAG result."""
    plan = result.get("query_plan") if isinstance(result.get("query_plan"), dict) else {}
    if not plan and isinstance(result.get("failed_query_plan"), dict):
        plan = result["failed_query_plan"]
    activity = result.get("agentic_activity_plan") if isinstance(result.get("agentic_activity_plan"), dict) else {}
    repair = result.get("agentic_repair") if isinstance(result.get("agentic_repair"), dict) else {}
    thresholds = quality.get("thresholds") if isinstance(quality.get("thresholds"), dict) else {}
    reasons = [str(item) for item in quality.get("reasons") or []]
    decision = _agentic_decision_label(result, quality, repair)
    return {
        "schema_version": 1,
        "decision": decision,
        "summary": _agentic_explanation_summary(
            decision=decision,
            reasons=reasons,
            quality_status=str(quality.get("status") or ""),
        ),
        "plan": {
            "mode": plan.get("agentic_mode") or plan.get("mode") or activity.get("mode"),
            "enabled": bool(plan.get("agentic_enabled", result.get("agentic_rag"))),
            "reason": plan.get("agentic_reason") or plan.get("reason") or activity.get("reason") or "",
            "subquery_count": len(plan.get("subqueries") or []),
        },
        "evidence": {
            "source_count": quality.get("source_count", result.get("source_count")),
            "context_chars": quality.get("content_chars"),
            "coverage_ratio": quality.get("coverage_ratio"),
            "relevant_coverage_ratio": quality.get("relevant_coverage_ratio"),
            "quality_score": quality.get("quality_score"),
            "quality_status": quality.get("status"),
            "reasons": reasons,
        },
        "quality_checks": _agentic_quality_checks(quality, thresholds),
        "steps": _agentic_explanation_steps(result, activity),
        "repair": {
            "strategy": repair.get("strategy") or "",
            "triggered_by": repair.get("triggered_by") or [],
            "attempted_branches": repair.get("attempted_branches"),
            "accepted_branches": repair.get("accepted_branches"),
            "fallback_source_count": repair.get("fallback_source_count"),
        },
        "next_action": quality.get("recommendation") or activity.get("recommendation") or "",
        "user_facing": _agentic_user_facing_explanation(
            result=result,
            quality=quality,
            decision=decision,
            reasons=reasons,
            plan=plan,
            activity=activity,
            repair=repair,
        ),
    }


def attach_agentic_explanation(result: dict[str, Any], quality: dict[str, Any]) -> None:
    """Attach the structured explanation to a mutable RAG result."""
    result["agentic_explanation"] = build_agentic_explanation(
        result=result,
        quality=quality,
    )


def _agentic_user_facing_explanation(
    *,
    result: dict[str, Any],
    quality: dict[str, Any],
    decision: str,
    reasons: list[str],
    plan: dict[str, Any],
    activity: dict[str, Any],
    repair: dict[str, Any],
) -> dict[str, Any]:
    reason_code = str(
        plan.get("agentic_reason")
        or plan.get("reason")
        or activity.get("reason")
        or ""
    )
    source_count = quality.get("source_count", result.get("source_count", 0))
    covered = quality.get("covered_subqueries")
    total = quality.get("total_subqueries")
    relevant = quality.get("relevant_subqueries")
    context_chars = quality.get("content_chars")
    fallback_used = decision == "single_search_fallback" or bool(result.get("agentic_fallback"))
    return {
        "title": _agentic_decision_title(decision),
        "badge": _agentic_decision_badge(decision),
        "tone": _agentic_decision_tone(decision, str(quality.get("status") or "")),
        "summary": _agentic_user_summary(decision),
        "trigger_reason": _agentic_plan_reason_label(reason_code),
        "fallback_used": fallback_used,
        "fallback_reason": _agentic_fallback_reason_label(reasons) if fallback_used else "",
        "evidence_summary": _agentic_evidence_summary(
            source_count=source_count,
            covered_subqueries=covered,
            total_subqueries=total,
            relevant_subqueries=relevant,
            context_chars=context_chars,
        ),
        "next_action": _agentic_user_next_action(
            decision=decision,
            reasons=reasons,
            quality=quality,
            repair=repair,
        ),
    }


def _agentic_decision_title(decision: str) -> str:
    labels = {
        "single_search_fallback": "Used the safer single-search path",
        "subquery_repair": "Repaired weak retrieval branches",
        "weak_multi_query": "Found evidence that needs review",
        "multi_query": "Used multi-step retrieval",
    }
    return labels.get(decision, "Reviewed retrieval evidence")


def _agentic_decision_badge(decision: str) -> str:
    labels = {
        "single_search_fallback": "Fallback used",
        "subquery_repair": "Repaired",
        "weak_multi_query": "Needs review",
        "multi_query": "Evidence ready",
    }
    return labels.get(decision, "Checked")


def _agentic_decision_tone(decision: str, quality_status: str) -> str:
    if decision == "single_search_fallback" or decision == "weak_multi_query" or quality_status == "weak":
        return "warning"
    if decision == "subquery_repair":
        return "success"
    return "success"


def _agentic_user_summary(decision: str) -> str:
    labels = {
        "single_search_fallback": "Multi-step retrieval was weak, so the answer used safer single-search evidence.",
        "subquery_repair": "Weak retrieval branches were repaired before answering.",
        "weak_multi_query": "Evidence was found, but some quality checks need review.",
        "multi_query": "Multi-step retrieval found enough evidence.",
    }
    return labels.get(decision, "Retrieval evidence was checked before answering.")


def _agentic_plan_reason_label(reason: str) -> str:
    reason = str(reason or "")
    primary = reason.split(";", 1)[0]
    if primary.startswith("multi_intent_terms"):
        return "The question has multiple learning intents."
    labels = {
        "forced_by_caller": "This request explicitly asked for deeper retrieval.",
        "multiple_questions": "The question contains multiple questions.",
        "long_query": "The question is long enough to benefit from focused retrieval.",
        "enumerated_question": "The question is structured as a list of sub-tasks.",
        "composed_question": "The question combines several requirements.",
        "fallback_rule_split": "The planner used a rule-based split.",
        "test": "Multi-step retrieval was selected for this request.",
    }
    return labels.get(primary, "Multi-step retrieval was selected for this request.")


def _agentic_fallback_reason_label(reasons: list[str]) -> str:
    priority = [
        ("no_sources", "No usable sources were found in the planned branches."),
        ("low_subquery_coverage", "Some planned branches did not return usable evidence."),
        ("low_relevance_coverage", "Some planned branches returned weakly related evidence."),
        ("low_context_chars", "The retrieved context was too thin for a grounded answer."),
        ("low_score", "The strongest evidence score was below the configured threshold."),
        ("low_source_count", "Too few sources were retained for the answer."),
    ]
    reason_set = set(reasons)
    for code, label in priority:
        if code in reason_set:
            return label
    return "The planned evidence did not pass the quality gate."


def _agentic_evidence_summary(
    *,
    source_count: Any,
    covered_subqueries: Any,
    total_subqueries: Any,
    relevant_subqueries: Any,
    context_chars: Any,
) -> str:
    parts = [f"{source_count or 0} source(s) retained"]
    if total_subqueries:
        parts.append(f"{covered_subqueries or 0}/{total_subqueries} branches covered")
        parts.append(f"{relevant_subqueries or 0}/{total_subqueries} branches relevant")
    if context_chars is not None:
        parts.append(f"{context_chars} context chars")
    return "; ".join(parts) + "."


def _agentic_user_next_action(
    *,
    decision: str,
    reasons: list[str],
    quality: dict[str, Any],
    repair: dict[str, Any],
) -> str:
    del repair
    if decision == "single_search_fallback":
        return "Review the fallback sources before relying on the answer."
    if decision == "subquery_repair":
        return "Review the repaired branches and source snippets."
    if "no_sources" in reasons:
        return "Open the knowledge base preflight and check whether the documents were indexed."
    if "low_subquery_coverage" in reasons or "low_relevance_coverage" in reasons:
        return "Run a stronger evidence preset or rephrase the missing branch."
    if quality.get("status") == "weak":
        return "Treat the answer as tentative and inspect the evidence list."
    return "Open the cited sources to verify the important claims."


def _agentic_decision_label(
    result: dict[str, Any],
    quality: dict[str, Any],
    repair: dict[str, Any],
) -> str:
    if result.get("agentic_fallback"):
        return "single_search_fallback"
    if result.get("agentic_repaired") or repair.get("strategy") == "subquery_repair":
        return "subquery_repair"
    if quality.get("status") == "weak":
        return "weak_multi_query"
    return "multi_query"


def _agentic_explanation_summary(
    *,
    decision: str,
    reasons: list[str],
    quality_status: str,
) -> str:
    if decision == "single_search_fallback":
        suffix = f" ({', '.join(reasons)})" if reasons else ""
        return f"Agentic RAG used a single-search fallback because multi-query evidence was weak{suffix}."
    if decision == "subquery_repair":
        return "Agentic RAG repaired weak retrieval branches and kept the multi-query evidence."
    if decision == "weak_multi_query" or quality_status == "weak":
        suffix = f": {', '.join(reasons)}" if reasons else "."
        return f"Agentic RAG found evidence, but quality checks are weak{suffix}"
    return "Agentic RAG split the question and found sufficient evidence for grounded synthesis."


def _agentic_quality_checks(
    quality: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    reasons = set(quality.get("reasons") or [])
    return [
        {
            "code": "source_count",
            "status": "failed" if {"no_sources", "low_source_count"} & reasons else "passed",
            "observed": quality.get("source_count"),
            "threshold": thresholds.get("min_sources"),
            "message": "Checks whether enough evidence sources were retained.",
        },
        {
            "code": "subquery_coverage",
            "status": "failed" if "low_subquery_coverage" in reasons else "passed",
            "observed": quality.get("coverage_ratio"),
            "threshold": thresholds.get("min_coverage_ratio"),
            "message": "Checks whether planned subqueries produced usable evidence.",
        },
        {
            "code": "relevance_coverage",
            "status": "failed" if "low_relevance_coverage" in reasons else "passed",
            "observed": quality.get("relevant_coverage_ratio"),
            "threshold": thresholds.get("min_relevant_coverage_ratio"),
            "message": "Checks whether evidence overlaps with each subquery.",
        },
        {
            "code": "context_chars",
            "status": "failed" if "low_context_chars" in reasons else "passed",
            "observed": quality.get("content_chars"),
            "threshold": thresholds.get("min_context_chars"),
            "message": "Checks whether the merged context is large enough to answer from.",
        },
        {
            "code": "score",
            "status": "failed" if "low_score" in reasons else "passed",
            "observed": quality.get("max_score"),
            "threshold": thresholds.get("min_score"),
            "message": "Checks the strongest similarity score when a score floor is configured.",
        },
    ]


def _agentic_explanation_steps(
    result: dict[str, Any],
    activity: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_steps = activity.get("steps") if isinstance(activity.get("steps"), list) else []
    subquery_results = result.get("subquery_results") if isinstance(result.get("subquery_results"), list) else []
    steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, dict):
            continue
        subquery_result = subquery_results[index] if index < len(subquery_results) and isinstance(subquery_results[index], dict) else {}
        status = str(raw_step.get("status") or "")
        repaired = bool(subquery_result.get("repaired"))
        repair_attempted = bool(subquery_result.get("repair_attempted"))
        if repaired:
            action = "accepted_repair"
        elif repair_attempted:
            action = "repair_rejected"
        elif status == "failed":
            action = "retry_or_fallback"
        elif status == "weak":
            action = "needs_more_evidence"
        else:
            action = "use_evidence"
        steps.append(
            {
                "index": raw_step.get("index", index + 1),
                "query": raw_step.get("query") or subquery_result.get("query") or "",
                "purpose": raw_step.get("purpose") or subquery_result.get("purpose") or "",
                "status": status,
                "source_count": raw_step.get("source_count", subquery_result.get("source_count")),
                "content_chars": raw_step.get("content_chars", subquery_result.get("content_chars")),
                "relevance_score": raw_step.get("relevance_score", subquery_result.get("relevance_score")),
                "matched_terms": raw_step.get("matched_terms") or subquery_result.get("matched_terms") or [],
                "repair_attempted": repair_attempted,
                "repaired": repaired,
                "action": action,
                "error": raw_step.get("error") or subquery_result.get("error") or "",
            }
        )
    return steps
