#!/usr/bin/env python
"""Check SparkWeave competition visualization deliverables."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_MARKERS = [
    (
        "Demo route",
        "web/src/router.tsx",
        ["path: \"/demo\"", "DemoRoute"],
    ),
    (
        "Demo page",
        "web/src/pages/DemoPage.tsx",
        [
            "competition-demo-page",
            "competition-demo-dashboard",
            "demo-recording-script",
            "demo-runtime-iflytek",
            "demo-ppt-shot-list",
        ],
    ),
    (
        "Stable demo data",
        "web/src/pages/demo/demoCoursePackage.ts",
        [
            "competition_alignment",
            "agent_collaboration_blueprint",
            "recording_script",
            "presentation_outline",
            "ai_coding_statement",
        ],
    ),
    (
        "Guide competition dashboard",
        "web/src/pages/guide/CompetitionDemoDashboard.tsx",
        ["competition-demo-dashboard", "competition-loop-rail", "competition-iflytek-strip"],
    ),
    (
        "Agent relay theater",
        "web/src/components/chat/AgentCollaborationPanel.tsx",
        ["agent-relay-theater", "多智能体接力剧场"],
    ),
    (
        "Multimodal resource studio",
        "web/src/pages/guide/GuideResourceArtifactPager.tsx",
        ["guide-multimodal-resource-studio", "多模态资源 Studio"],
    ),
    (
        "Knowledge transit map",
        "web/src/pages/guide/GuideKnowledgeMapPanel.tsx",
        ["guide-knowledge-transit-map", "知识掌握地铁图"],
    ),
    (
        "Path adjustment morph",
        "web/src/pages/guide/GuideLearningReportPanel.tsx",
        ["guide-path-adjustment-morph", "路线调整前后"],
    ),
    (
        "RAG evidence waterfall",
        "web/src/components/results/RagEvidenceChain.tsx",
        ["rag-evidence-waterfall", "证据瀑布"],
    ),
    (
        "Visual runbook",
        "docs/competition-demo-visual-runbook.md",
        ["/demo", "7 分钟录屏路线", "PPT 主截图位", "兜底策略"],
    ),
    (
        "Visualization plan completion",
        "docs/competition-visualization-wow-plan.md",
        ["实施完成记录", "已完成的非阻塞优化", "最终完成判定"],
    ),
    (
        "Visualization completion report",
        "docs/competition-visualization-completion-report.md",
        [
            "比赛可视化专项完成证据",
            "完成矩阵",
            "Competition visual plan is complete.",
            "All required competition materials are ready.",
        ],
    ),
    (
        "Screenshot capture targets",
        "web/scripts/capture-screenshots.mjs",
        ["screenshots-competition-demo.png", "screenshots-competition-demo-mobile.png"],
    ),
    (
        "E2E coverage",
        "web/tests/e2e/workbench-smoke.spec.ts",
        ["competition demo route exposes judge-facing visual proof points", "demo-ppt-shot-list"],
    ),
]

REQUIRED_SCREENSHOTS = [
    ("Desktop demo screenshot", "web/screenshots-competition-demo.png", 1000, 650),
    ("Mobile demo screenshot", "web/screenshots-competition-demo-mobile.png", 320, 640),
]

COMPLETION_WORDING_DOCS = [
    "docs/competition-visualization-wow-plan.md",
    "docs/competition-visualization-completion-report.md",
    "docs/sparkweave-execution-plan.md",
]

DISALLOWED_COMPLETION_PHRASES = [
    "待规划",
    "待落地",
    "待补齐",
    "仍有未完成",
    "剩余非阻塞优化",
    "后续的比赛可视化专项路线",
    "下一阶段可视化层",
    "下一轮可视化开发",
    "也可以后续独立成",
    "建议实施顺序",
    "后续打磨建议",
    "第一刀建议落点",
    "TODO",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", type=Path, help="Optional path for a JSON report.")
    args = parser.parse_args()

    checks = check_markers() + check_completion_wording() + check_screenshots()
    failed = [item for item in checks if not item.ok]
    report = {
        "success": not failed,
        "total_count": len(checks),
        "ready_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "summary": "Competition visual plan is complete." if not failed else f"{len(failed)} visual check(s) need attention.",
        "checks": [item.as_dict() for item in checks],
    }

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report["success"] else 1


def check_markers() -> list[Check]:
    checks: list[Check] = []
    for name, relative, markers in REQUIRED_MARKERS:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [marker for marker in markers if marker not in content]
        checks.append(Check(name, not missing, "" if not missing else "missing " + ", ".join(missing)))
    return checks


def check_completion_wording() -> list[Check]:
    checks: list[Check] = []
    for relative in COMPLETION_WORDING_DOCS:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(f"Completion wording: {relative}", False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(f"Completion wording: {relative}", False, f"not utf-8 text: {exc}"))
            continue
        found = [phrase for phrase in DISALLOWED_COMPLETION_PHRASES if phrase in content]
        checks.append(
            Check(
                f"Completion wording: {relative}",
                not found,
                "" if not found else "ambiguous completion wording: " + ", ".join(found),
            )
        )
    return checks


def check_screenshots() -> list[Check]:
    checks: list[Check] = []
    for name, relative, min_width, min_height in REQUIRED_SCREENSHOTS:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        size = path.stat().st_size
        dimensions = png_dimensions(path)
        if dimensions is None:
            checks.append(Check(name, False, "not a valid PNG"))
            continue
        width, height = dimensions
        ok = size > 10_000 and width >= min_width and height >= min_height
        detail = f"{width}x{height}, {size} bytes"
        checks.append(Check(name, ok, detail if ok else f"too small or empty: {detail}"))
    return checks


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def print_text(report: dict[str, object]) -> None:
    print("\nSparkWeave competition visual readiness")
    print("=" * 48)
    for item in report["checks"]:
        check = item if isinstance(item, dict) else {}
        mark = "ok" if check.get("ok") else "fail"
        detail = f" - {check.get('detail')}" if check.get("detail") else ""
        print(f"[{mark}] {check.get('name')}{detail}")
    print("=" * 48)
    print(str(report["summary"]))


if __name__ == "__main__":
    raise SystemExit(main())
