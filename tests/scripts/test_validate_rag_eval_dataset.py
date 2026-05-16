from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_rag_eval_dataset.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_rag_eval_dataset", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def test_sample_ml_course_dataset_passes_validation() -> None:
    report = validator.validate_dataset(
        ROOT / "docs" / "examples" / "rag_eval_dataset.ml_course.sample.jsonl",
        min_cases=30,
        min_query_types=5,
        require_kb=True,
    )

    assert report["status"] == "passed"
    assert report["case_count"] == 30
    assert set(report["query_types"]) == {"code", "concept", "exact", "formula", "guide"}
    assert report["knowledge_bases"] == {"ml-course": 30}
    assert report["keyword_label_coverage"] == 1.0
    assert report["source_label_coverage"] == 1.0
    assert report["full_label_coverage"] == 1.0
    assert report["fully_labelled_cases"] == 30
    assert report["recommendation"] == "Dataset is ready for comparative RAG evaluation."


def test_validation_rejects_duplicates_and_missing_metrics(tmp_path: Path) -> None:
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text(
        "\n".join(
            [
                json.dumps({"id": "dup", "question": "What is RAG?", "query_type": "concept"}),
                json.dumps({"id": "dup", "question": "What is reranking?", "query_type": "concept"}),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(validator.DatasetValidationError) as exc:
        validator.validate_dataset(dataset, min_cases=2, min_query_types=2, require_kb=True)

    payload = json.loads(str(exc.value))
    assert payload["status"] == "failed"
    assert any("Duplicate case id" in item for item in payload["errors"])
    assert any("missing kb_name" in item for item in payload["errors"])
    assert any("missing expected_keywords" in item for item in payload["errors"])
    assert any("query type" in item for item in payload["errors"])
    assert payload["recommendation"] == "Fix blocking dataset errors before running RAG evaluation."


def test_cli_writes_json_report(tmp_path: Path) -> None:
    dataset = tmp_path / "ok.jsonl"
    output = tmp_path / "report.json"
    dataset.write_text(
        json.dumps(
            {
                "id": "case-1",
                "kb_name": "course",
                "query_type": "concept",
                "question": "What is gradient descent?",
                "expected_keywords": ["gradient"],
                "expected_sources": ["gradient.md"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    code = validator.main([str(dataset), "--require-kb", "--json-output", str(output)])

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["case_count"] == 1
    assert payload["recommendation"].startswith("Dataset is usable for smoke checks")
