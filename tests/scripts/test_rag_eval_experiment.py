from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rag_eval_experiment.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("rag_eval_experiment", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rag_eval = _load_module()


def test_parse_strategy_coerces_values() -> None:
    strategy = rag_eval.parse_strategy("dense_strict:top_k=12,score_threshold=0.35,enabled=true,mode=hybrid")

    assert strategy.name == "dense_strict"
    assert strategy.params == {
        "top_k": 12,
        "score_threshold": 0.35,
        "enabled": True,
        "mode": "hybrid",
    }


def test_strategy_presets_include_agentic_rag() -> None:
    strategies = rag_eval.strategies_for_preset("rag-upgrade")

    assert [item.name for item in strategies] == [
        "baseline",
        "adaptive_policy",
        "wide_context",
        "hybrid_keyword_rerank",
        "hyde_hybrid_rerank",
        "agentic_hyde",
    ]
    assert strategies[1].params["retrieval_profile"] == "auto"
    assert strategies[-1].params["agentic_rag"] == "auto"
    assert strategies[-1].params["query_transform"] == "hyde"


def test_quick_check_preset_is_lightweight() -> None:
    strategies = rag_eval.strategies_for_preset("quick-check")

    assert [item.name for item in strategies] == ["baseline", "adaptive_policy"]
    assert strategies[0].params["top_k"] == 5
    assert strategies[1].params["retrieval_profile"] == "auto"
    assert all(item.params["max_context_chars"] <= 6000 for item in strategies)


def test_strategy_presets_reject_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown RAG eval strategy preset"):
        rag_eval.strategies_for_preset("not-real")


def test_cli_accepts_documented_hyphenated_preset() -> None:
    parser = rag_eval.argparse.ArgumentParser()
    parser.add_argument(
        "--preset",
        choices=sorted({*rag_eval.STRATEGY_PRESETS, *(name.replace("_", "-") for name in rag_eval.STRATEGY_PRESETS)}),
    )

    args = parser.parse_args(["--preset", "quick-check"])

    assert args.preset == "quick-check"


def test_parse_strategy_rejects_invalid_parameter() -> None:
    with pytest.raises(ValueError, match="Invalid strategy parameter"):
        rag_eval.parse_strategy("bad:top_k")


def test_load_cases_reads_jsonl_and_ignores_comments(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join([
            "# comment",
            '{"id":"case-1","question":"什么是 RAG？"}',
            "",
        ]),
        encoding="utf-8",
    )

    assert rag_eval.load_cases(dataset) == [{"id": "case-1", "question": "什么是 RAG？"}]


def test_load_cases_requires_question(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text('{"id":"bad"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Missing question"):
        rag_eval.load_cases(dataset)


def test_dataset_profile_explains_label_coverage() -> None:
    smoke = rag_eval.summarize_dataset_profile([
        {"id": "a", "question": "What is RAG?"},
        {"id": "b", "question": "How should I learn this?"},
    ])

    assert smoke["label_status"] == "smoke_check"
    assert smoke["keyword_labelled_cases"] == 0
    assert smoke["source_labelled_cases"] == 0
    assert smoke["metrics_supported"]["release_quality_gate"] is False

    partial = rag_eval.summarize_dataset_profile([
        {"id": "a", "question": "What is RAG?", "expected_keywords": ["retrieval"]},
        {"id": "b", "question": "Where is it defined?", "expected_sources": ["chapter-1"]},
    ])

    assert partial["label_status"] == "partial"
    assert partial["keyword_label_coverage"] == 0.5
    assert partial["source_label_coverage"] == 0.5

    release_ready = rag_eval.summarize_dataset_profile([
        {
            "id": f"case-{index}",
            "question": f"Question {index}?",
            "expected_keywords": ["concept"],
            "expected_sources": ["source"],
        }
        for index in range(30)
    ])

    assert release_ready["label_status"] == "release_ready"
    assert release_ready["fully_labelled_cases"] == 30


def test_ml_course_sample_dataset_has_type_coverage() -> None:
    cases = rag_eval.load_cases(ROOT / "docs" / "examples" / "rag_eval_dataset.ml_course.sample.jsonl")

    assert len(cases) == 30
    assert {case["query_type"] for case in cases} == {"code", "concept", "exact", "formula", "guide"}
    assert all(case.get("expected_keywords") for case in cases)
    assert all(case.get("expected_sources") for case in cases)


def test_summarize_records() -> None:
    records = [
        rag_eval.EvalRecord(
            case_id="a",
            strategy="baseline",
            success=True,
            latency_ms=100,
            keyword_recall=0.5,
            source_hit=True,
            avg_source_score=0.8,
            source_count=2,
            context_chars=1000,
            query_type="concept",
            source_mrr=1.0,
            source_ndcg=1.0,
            first_source_rank=1,
            matched_keyword_count=3,
            evidence_reason_count=2,
            skipped_duplicate=1,
        ),
        rag_eval.EvalRecord(
            case_id="b",
            strategy="baseline",
            success=False,
            latency_ms=300,
            keyword_recall=1.0,
            source_hit=False,
            avg_source_score=None,
            source_count=0,
            context_chars=0,
            query_type="concept",
            source_mrr=0.0,
            source_ndcg=0.0,
        ),
    ]

    assert rag_eval.summarize(records) == [
        {
            "strategy": "baseline",
            "cases": 2,
            "success_rate": 0.5,
            "keyword_recall": 0.75,
            "source_hit_rate": 0.5,
            "avg_source_score": 0.8,
            "avg_source_mrr": 0.5,
            "avg_source_ndcg": 0.5,
            "avg_first_source_rank": 1.0,
            "avg_source_count": 1.0,
            "avg_context_chars": 500.0,
            "avg_matched_keywords": 1.5,
            "avg_evidence_reasons": 1.0,
            "avg_skipped_duplicate": 0.5,
            "avg_skipped_threshold": 0.0,
            "avg_skipped_budget": 0.0,
            "p50_latency_ms": 100.0,
            "p95_latency_ms": 300.0,
        }
    ]
    assert rag_eval.summarize(records, group_by="query_type")[0]["query_type"] == "concept"


def test_build_report_includes_strategy_outcome_summary() -> None:
    records = [
        rag_eval.EvalRecord(
            case_id="b1",
            strategy="baseline",
            success=True,
            latency_ms=100,
            keyword_recall=0.4,
            source_hit=True,
            avg_source_score=0.7,
            source_count=2,
            context_chars=1000,
            query_type="concept",
            difficulty="basic",
            chapter="optimization",
            evidence_reason_count=1,
        ),
        rag_eval.EvalRecord(
            case_id="b2",
            strategy="baseline",
            success=True,
            latency_ms=200,
            keyword_recall=0.6,
            source_hit=False,
            avg_source_score=0.6,
            source_count=1,
            context_chars=800,
            query_type="guide",
            difficulty="basic",
            chapter="optimization",
        ),
        rag_eval.EvalRecord(
            case_id="h1",
            strategy="hybrid_keyword_rerank",
            success=True,
            latency_ms=300,
            keyword_recall=0.8,
            source_hit=True,
            avg_source_score=0.8,
            source_count=3,
            context_chars=1200,
            query_type="concept",
            difficulty="advanced",
            chapter="optimization",
            evidence_reason_count=2,
        ),
        rag_eval.EvalRecord(
            case_id="h2",
            strategy="hybrid_keyword_rerank",
            success=True,
            latency_ms=400,
            keyword_recall=0.9,
            source_hit=True,
            avg_source_score=0.85,
            source_count=3,
            context_chars=1300,
            query_type="guide",
            difficulty="advanced",
            chapter="optimization",
            evidence_reason_count=2,
        ),
    ]

    report = rag_eval.build_report(records)
    outcome = report["experiment_summary"]

    assert outcome["quality_leader"] == "hybrid_keyword_rerank"
    assert outcome["fastest_strategy"] == "baseline"
    assert outcome["quality_delta"]["source_hit_delta"] == 0.5
    assert outcome["decision"] == "promote_default"
    assert outcome["quality_score"] > outcome["baseline_quality_score"]
    assert "currently leads" in outcome["headline"]
    assert "complex or high-stakes queries" in outcome["recommendation"]
    assert report["quality_gate"]["status"] == "fail"
    assert report["quality_gate"]["strategy"] == "hybrid_keyword_rerank"
    assert "Only 2 cases" in report["quality_gate"]["reasons"][0]
    assert {row["difficulty"] for row in report["summary_by_difficulty"]} == {"basic", "advanced"}
    assert {row["chapter"] for row in report["summary_by_chapter"]} == {"optimization"}


def test_quality_gate_classifies_release_readiness() -> None:
    summary = [
        {
            "strategy": "baseline",
            "cases": 30,
            "success_rate": 1.0,
            "source_hit_rate": 0.9,
            "avg_source_ndcg": 0.86,
            "keyword_recall": 0.72,
            "avg_evidence_reasons": 1.5,
        }
    ]
    outcome = rag_eval.summarize_strategy_outcome(summary, [], baseline_strategy="baseline")
    clean_diagnostics = rag_eval.summarize_case_diagnostics([], total_records=30)

    passed = rag_eval.build_quality_gate(summary, clean_diagnostics, outcome, baseline_strategy="baseline")

    assert passed["status"] == "pass"
    assert passed["status_label"] == "Ready"
    assert passed["metrics"]["quality_score"] > 0.8

    warning = rag_eval.build_quality_gate(
        [{**summary[0], "source_hit_rate": 0.8}],
        {
            **clean_diagnostics,
            "total_diagnostics": 2,
            "affected_cases": 2,
            "severity_counts": {"high": 1},
        },
        outcome,
        baseline_strategy="baseline",
    )

    assert warning["status"] == "warn"
    assert any("high-severity" in reason for reason in warning["reasons"])

    failed = rag_eval.build_quality_gate(
        [{**summary[0], "source_hit_rate": 0.6}],
        {
            **clean_diagnostics,
            "total_diagnostics": 1,
            "affected_cases": 1,
            "severity_counts": {"critical": 1},
        },
        outcome,
        baseline_strategy="baseline",
    )

    assert failed["status"] == "fail"
    assert any("critical" in reason for reason in failed["reasons"])


def test_case_diagnostics_explain_problem_records() -> None:
    records = [
        rag_eval.EvalRecord(
            case_id="ok",
            strategy="baseline",
            success=True,
            latency_ms=100,
            keyword_recall=1.0,
            source_hit=True,
            avg_source_score=0.9,
            source_count=3,
            context_chars=1800,
        ),
        rag_eval.EvalRecord(
            case_id="empty",
            strategy="baseline",
            success=True,
            latency_ms=110,
            keyword_recall=None,
            source_hit=None,
            avg_source_score=None,
            source_count=0,
            context_chars=0,
        ),
        rag_eval.EvalRecord(
            case_id="kw",
            strategy="hyde_hybrid_rerank",
            success=True,
            latency_ms=220,
            keyword_recall=0.25,
            source_hit=True,
            avg_source_score=0.7,
            source_count=2,
            context_chars=1200,
        ),
        rag_eval.EvalRecord(
            case_id="boom",
            strategy="agentic_hyde",
            success=False,
            latency_ms=300,
            keyword_recall=None,
            source_hit=None,
            avg_source_score=None,
            source_count=0,
            context_chars=0,
            error="planner timeout",
        ),
    ]

    diagnostics = rag_eval.diagnose_case_records(records, baseline_strategy="baseline")

    assert [item["case_id"] for item in diagnostics] == ["boom", "empty", "kw"]
    assert diagnostics[0]["severity"] == "critical"
    assert diagnostics[0]["issue_code"] == "retrieval_error"
    assert diagnostics[1]["issue_code"] == "no_sources"
    assert diagnostics[2]["issue_code"] == "low_keyword_recall"
    report = rag_eval.build_report(records)
    assert report["case_diagnostics"] == diagnostics
    assert report["diagnostic_summary"]["affected_cases"] == 3
    assert report["diagnostic_summary"]["primary_issue_code"] == "retrieval_error"
    assert "main pattern" in report["diagnostic_summary"]["headline"]


def test_write_reports(tmp_path: Path) -> None:
    summary = [
        {
            "strategy": "baseline",
            "cases": 1,
            "success_rate": 1.0,
            "keyword_recall": 0.6667,
            "source_hit_rate": None,
            "avg_source_score": 0.9,
            "avg_source_count": 2.0,
            "avg_context_chars": 1200.0,
            "p50_latency_ms": 42.0,
            "p95_latency_ms": 42.0,
        }
    ]
    records = [
        rag_eval.EvalRecord(
            case_id="case-1",
            strategy="baseline",
            success=True,
            latency_ms=42,
            keyword_recall=0.6667,
            source_hit=None,
            avg_source_score=0.9,
            source_count=2,
            context_chars=1200,
            query_type="concept",
            difficulty="basic",
            chapter="gradient",
            matched_keyword_count=2,
            evidence_reason_count=1,
        )
    ]

    md_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"
    rag_eval.write_markdown(md_path, summary)
    rag_eval.write_json(json_path, records, summary)

    assert "baseline" in md_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"] == summary
    assert payload["summary_by_query_type"]
    assert payload["summary_by_difficulty"][0]["difficulty"] == "basic"
    assert payload["summary_by_chapter"][0]["chapter"] == "gradient"
    assert payload["experiment_summary"]["quality_leader"] == "baseline"
    assert payload["quality_gate"]["status"] == "fail"
    assert payload["case_diagnostics"] == []
    assert payload["diagnostic_summary"]["total_diagnostics"] == 0


def test_write_markdown_includes_case_diagnostics(tmp_path: Path) -> None:
    summary = [{"strategy": "baseline", "cases": 1, "success_rate": 0.0}]
    records = [
        rag_eval.EvalRecord(
            case_id="empty",
            strategy="baseline",
            success=True,
            latency_ms=120,
            keyword_recall=None,
            source_hit=None,
            avg_source_score=None,
            source_count=0,
            context_chars=0,
            difficulty="basic",
            chapter="retrieval",
        )
    ]
    md_path = tmp_path / "report.md"

    rag_eval.write_markdown(md_path, summary, records)

    content = md_path.read_text(encoding="utf-8")
    assert "Executive Summary" in content
    assert "Decision:" in content
    assert "Quality Gate" in content
    assert "Diagnostic Summary" in content
    assert "Case Diagnostics" in content
    assert "By Difficulty" in content
    assert "By Chapter" in content
    assert "No supporting evidence was retrieved" in content


def test_run_case_uses_runtime_rag_search(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("sparkweave.services.rag")

    async def fake_rag_search(query: str, kb_name: str, **params):
        assert query == "为什么梯度下降沿负梯度方向？"
        assert kb_name == "ml-course"
        assert params == {"top_k": 2}
        return {
            "success": True,
            "content": "负梯度方向对应局部最陡下降，可以降低损失函数。",
            "sources": [
                {
                    "title": "unrelated notes",
                    "source": "overview.md",
                    "content": "课程目标和学习建议",
                },
                {
                    "title": "gradient notes",
                    "source": "gradient.md",
                    "content": "最陡下降",
                    "score": 0.91,
                    "matched_keywords": ["负梯度", "最陡下降"],
                    "evidence_reason": "命中问题关键词：负梯度、最陡下降。",
                }
            ],
            "context_pack": {"skipped_duplicate": 1, "skipped_threshold": 0, "skipped_budget": 0},
        }

    fake_module.rag_search = fake_rag_search
    monkeypatch.setitem(sys.modules, "sparkweave.services.rag", fake_module)

    record = asyncio.run(
        rag_eval.run_case(
            {
                "id": "gd-01",
                "kb_name": "ml-course",
                "question": "为什么梯度下降沿负梯度方向？",
                "expected_keywords": ["负梯度", "最陡下降", "损失函数"],
                "expected_sources": ["gradient"],
            },
            rag_eval.Strategy("tiny", {"top_k": 2}),
            default_kb=None,
        )
    )

    assert record.success is True
    assert record.keyword_recall == 1
    assert record.source_hit is True
    assert record.avg_source_score == 0.91
    assert record.source_count == 2
    assert record.first_source_rank == 2
    assert record.source_mrr == 0.5
    assert record.source_ndcg == 0.6309
    assert record.query_type == "untyped"
    assert record.matched_keyword_count == 2
    assert record.evidence_reason_count == 1
    assert record.skipped_duplicate == 1


def test_run_case_applies_default_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("sparkweave.services.rag")

    async def fake_rag_search(query: str, kb_name: str, **params):
        assert query == "什么是 RAG？"
        assert kb_name == "course"
        assert params["provider"] == "milvus"
        return {"success": True, "content": "RAG", "sources": []}

    fake_module.rag_search = fake_rag_search
    monkeypatch.setitem(sys.modules, "sparkweave.services.rag", fake_module)

    record = asyncio.run(
        rag_eval.run_case(
            {"id": "rag-01", "kb_name": "course", "question": "什么是 RAG？"},
            rag_eval.Strategy("milvus", {}),
            default_kb=None,
            default_provider="milvus",
        )
    )

    assert record.success is True
