#!/usr/bin/env python
"""Validate a RAG evaluation JSONL dataset before running experiments."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sparkweave.services.rag_support.evaluation import load_cases  # noqa: E402


class DatasetValidationError(RuntimeError):
    """Raised when the evaluation dataset is not usable."""


def _as_non_empty_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_dataset(
    path: Path,
    *,
    min_cases: int = 1,
    min_query_types: int = 1,
    require_kb: bool = False,
    require_expected_sources: bool = True,
    require_expected_keywords: bool = True,
) -> dict[str, Any]:
    cases = load_cases(path)
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    query_types: Counter[str] = Counter()
    difficulties: Counter[str] = Counter()
    kb_names: Counter[str] = Counter()
    keyword_labelled_cases = 0
    source_labelled_cases = 0
    fully_labelled_cases = 0

    if len(cases) < min_cases:
        errors.append(f"Dataset has {len(cases)} case(s), expected at least {min_cases}.")

    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("id") or f"row-{index}").strip()
        if case_id in seen_ids:
            duplicate_ids.add(case_id)
        seen_ids.add(case_id)

        question = str(case.get("question") or "").strip()
        if not question:
            errors.append(f"{case_id}: missing question.")

        kb_name = str(case.get("kb_name") or "").strip()
        if require_kb and not kb_name:
            errors.append(f"{case_id}: missing kb_name.")
        if kb_name:
            kb_names[kb_name] += 1

        query_type = str(case.get("query_type") or "untyped").strip() or "untyped"
        query_types[query_type] += 1
        difficulty = str(case.get("difficulty") or "unlabeled").strip() or "unlabeled"
        difficulties[difficulty] += 1

        expected_keywords = _as_non_empty_list(case.get("expected_keywords"))
        if expected_keywords:
            keyword_labelled_cases += 1
        if require_expected_keywords and not expected_keywords:
            errors.append(f"{case_id}: missing expected_keywords.")
        elif not expected_keywords:
            warnings.append(f"{case_id}: keyword recall cannot be computed.")

        expected_sources = _as_non_empty_list(case.get("expected_sources"))
        if expected_sources:
            source_labelled_cases += 1
        if require_expected_sources and not expected_sources:
            errors.append(f"{case_id}: missing expected_sources.")
        elif not expected_sources:
            warnings.append(f"{case_id}: source hit metrics cannot be computed.")
        if expected_keywords and expected_sources:
            fully_labelled_cases += 1

    if duplicate_ids:
        errors.append(f"Duplicate case id(s): {', '.join(sorted(duplicate_ids))}.")
    if len(query_types) < min_query_types:
        errors.append(
            f"Dataset covers {len(query_types)} query type(s), expected at least {min_query_types}."
        )

    summary = {
        "status": "failed" if errors else "passed",
        "path": str(path),
        "case_count": len(cases),
        "query_type_count": len(query_types),
        "query_types": dict(sorted(query_types.items())),
        "difficulties": dict(sorted(difficulties.items())),
        "knowledge_bases": dict(sorted(kb_names.items())),
        "keyword_labelled_cases": keyword_labelled_cases,
        "source_labelled_cases": source_labelled_cases,
        "fully_labelled_cases": fully_labelled_cases,
        "keyword_label_coverage": _ratio(keyword_labelled_cases, len(cases)),
        "source_label_coverage": _ratio(source_labelled_cases, len(cases)),
        "full_label_coverage": _ratio(fully_labelled_cases, len(cases)),
        "recommendation": _dataset_recommendation(
            errors=errors,
            warnings=warnings,
            case_count=len(cases),
            min_cases=min_cases,
            query_type_count=len(query_types),
            min_query_types=min_query_types,
            fully_labelled_cases=fully_labelled_cases,
        ),
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        raise DatasetValidationError(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _dataset_recommendation(
    *,
    errors: list[str],
    warnings: list[str],
    case_count: int,
    min_cases: int,
    query_type_count: int,
    min_query_types: int,
    fully_labelled_cases: int,
) -> str:
    if errors:
        return "Fix blocking dataset errors before running RAG evaluation."
    if case_count < max(30, min_cases) or query_type_count < max(5, min_query_types):
        return "Dataset is usable for smoke checks; add more cases and query types before treating it as a release gate."
    if fully_labelled_cases < case_count:
        return "Dataset can run, but release metrics need every case to include expected_keywords and expected_sources."
    if warnings:
        return "Dataset passed; review warnings before comparing strategies."
    return "Dataset is ready for comparative RAG evaluation."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--min-query-types", type=int, default=1)
    parser.add_argument("--require-kb", action="store_true")
    parser.add_argument("--allow-missing-sources", dest="require_expected_sources", action="store_false")
    parser.add_argument("--allow-missing-keywords", dest="require_expected_keywords", action="store_false")
    parser.add_argument("--json-output", type=Path)
    parser.set_defaults(require_expected_sources=True, require_expected_keywords=True)
    return parser


def _write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_dataset(
            args.dataset,
            min_cases=args.min_cases,
            min_query_types=args.min_query_types,
            require_kb=args.require_kb,
            require_expected_sources=args.require_expected_sources,
            require_expected_keywords=args.require_expected_keywords,
        )
    except DatasetValidationError as exc:
        try:
            report = json.loads(str(exc))
        except ValueError:
            report = {"status": "failed", "errors": [str(exc)]}
        _write_report(args.json_output, report)
        print(f"RAG eval dataset failed validation: {args.dataset}", file=sys.stderr)
        for error in report.get("errors", []):
            print(f"- {error}", file=sys.stderr)
        return 1

    _write_report(args.json_output, report)
    print(
        f"RAG eval dataset passed: {report['case_count']} cases, "
        f"{report['query_type_count']} query types, "
        f"{report['fully_labelled_cases']} fully labelled."
    )
    print(report["recommendation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
