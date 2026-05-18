#!/usr/bin/env python
"""Run lightweight comparative RAG retrieval experiments.

Dataset JSONL format:
{"id":"case-1","kb_name":"course","question":"...","expected_keywords":["..."],"expected_sources":["..."]}
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sparkweave.services.rag_support.evaluation import (  # noqa: E402
    DEFAULT_STRATEGIES,
    QUICK_CHECK_STRATEGIES,
    RAG_UPGRADE_STRATEGIES,
    STRATEGY_PRESETS,
    EvalRecord,
    Strategy,
    build_quality_gate,
    build_report,
    diagnose_case_records,
    load_cases,
    parse_strategy,
    run_case,
    run_evaluation,
    run_experiment,
    strategies_for_preset,
    summarize,
    summarize_case_diagnostics,
    summarize_dataset_profile,
    summarize_strategy_outcome,
    write_json,
    write_markdown,
    write_report_json,
    write_report_markdown,
)

__all__ = [
    "DEFAULT_STRATEGIES",
    "EvalRecord",
    "QUICK_CHECK_STRATEGIES",
    "RAG_UPGRADE_STRATEGIES",
    "Strategy",
    "STRATEGY_PRESETS",
    "build_quality_gate",
    "build_report",
    "diagnose_case_records",
    "load_cases",
    "parse_strategy",
    "run_case",
    "run_evaluation",
    "run_experiment",
    "strategies_for_preset",
    "summarize",
    "summarize_case_diagnostics",
    "summarize_dataset_profile",
    "summarize_strategy_outcome",
    "write_json",
    "write_markdown",
    "write_report_json",
    "write_report_markdown",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    preset_choices = sorted({*STRATEGY_PRESETS, *(name.replace("_", "-") for name in STRATEGY_PRESETS)})
    parser.add_argument("dataset", type=Path, help="JSONL eval dataset.")
    parser.add_argument("--kb", help="Default knowledge base name when cases omit kb_name.")
    parser.add_argument("--provider", help="Default RAG provider, e.g. milvus or llamaindex.")
    parser.add_argument(
        "--strategy",
        action="append",
        default=[],
        help="Strategy definition, e.g. baseline:top_k=5,max_context_chars=8000",
    )
    parser.add_argument(
        "--preset",
        default="default",
        choices=preset_choices,
        help="Named strategy preset used when --strategy is omitted.",
    )
    parser.add_argument("--output", type=Path, default=Path("dist/rag-eval-report.md"))
    parser.add_argument("--json-output", type=Path, default=Path("dist/rag-eval-report.json"))
    parser.add_argument("--baseline-strategy", default="baseline", help="Strategy name used for delta comparison.")
    args = parser.parse_args()

    strategies = [parse_strategy(item) for item in args.strategy] if args.strategy else strategies_for_preset(args.preset)
    cases = load_cases(args.dataset)
    report = asyncio.run(
        run_evaluation(
            cases,
            strategies,
            default_kb=args.kb,
            default_provider=args.provider,
            baseline_strategy=args.baseline_strategy,
        )
    )
    write_report_markdown(args.output, report)
    write_report_json(args.json_output, report)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
