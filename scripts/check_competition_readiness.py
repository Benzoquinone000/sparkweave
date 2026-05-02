#!/usr/bin/env python
"""Run a lightweight SparkWeave competition readiness check."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOCS = [
    "README.md",
    "docs/architecture.md",
    "docs/capabilities.md",
    "docs/competition-demo-runbook.md",
    "docs/competition-roadmap.md",
    "docs/demo-quickstart.md",
    "docs/guided-learning.md",
    "docs/learner-profile-design.md",
    "docs/iflytek-integration.md",
    "docs/ai-coding-statement.md",
]

REQUIRED_RUNTIME_FILES = [
    ".env.example",
    "requirements.txt",
    "requirements/server.txt",
    "requirements/math-animator.txt",
    "scripts/start_web.py",
    "scripts/check_install.py",
    "scripts/check_release_safety.py",
    "scripts/check_competition_readiness.py",
    "scripts/export_demo_materials.py",
    "scripts/export_competition_package.py",
]

REQUIRED_ASSETS = [
    "assets/logo-ver2.png",
    "assets/architecture.svg",
    "docs/assets/guided-learning-loop.svg",
    "docs/assets/agent-collaboration-blueprint.svg",
]

REQUIRED_SCREENSHOTS = [
    "web/screenshots-refined-chat.png",
    "web/screenshots-simplified-guide.png",
    "web/screenshots-simplified-final-knowledge.png",
    "web/screenshots-simplified-final-question.png",
    "web/screenshots-simplified-final-vision.png",
    "web/screenshots-simplified-notebook.png",
    "web/screenshots-finalcheck-agents.png",
    "web/screenshots-simplified-final-settings.png",
]

REQUIRED_COURSE_TEMPLATES = [
    "data/course_templates/ai_learning_agents_systems.json",
    "data/course_templates/higher_math_limits_derivatives.json",
    "data/course_templates/robotics_ros_foundations.json",
]

GENERATED_DEMO_FILES = [
    "README.md",
    "sparkweave-demo-deck-outline.md",
    "sparkweave-demo-deck.html",
    "sparkweave-7min-recording-script.md",
    "sparkweave-agent-collaboration-blueprint.md",
    "sparkweave-demo-fallback-assets.md",
    "sparkweave-defense-qa.md",
    "sparkweave-competition-scorecard.md",
    "sparkweave-final-pitch-checklist.md",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Defaults to text.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the machine-readable JSON report.",
    )
    args = parser.parse_args()

    report = build_report()
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 0 if report["success"] else 1


def build_report() -> dict[str, object]:
    checks: list[Check] = []
    checks.extend(check_paths("Docs", REQUIRED_DOCS))
    checks.extend(check_paths("Runtime", REQUIRED_RUNTIME_FILES))
    checks.extend(check_paths("Assets", REQUIRED_ASSETS))
    checks.extend(check_paths("Screenshots", REQUIRED_SCREENSHOTS))
    checks.extend(check_paths("Course templates", REQUIRED_COURSE_TEMPLATES))
    checks.append(run_project_script("Release safety", "check_release_safety.py"))
    checks.append(run_project_script("Course template schema", "check_course_templates.py"))
    checks.extend(check_generated_exports())

    failed = [item for item in checks if not item.ok]
    return {
        "success": not failed,
        "total_count": len(checks),
        "ready_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "summary": (
            "All required competition materials are ready."
            if not failed
            else f"{len(failed)} check(s) need attention before submission."
        ),
        "checks": [item.to_dict() for item in checks],
    }


def print_text_report(report: dict[str, object]) -> None:
    checks = [item for item in report.get("checks", []) if isinstance(item, dict)]
    print("\nSparkWeave competition readiness")
    print("=" * 40)
    for item in checks:
        ok = bool(item.get("ok"))
        mark = "ok" if ok else "fail"
        detail = str(item.get("detail") or "")
        suffix = f" - {detail}" if detail else ""
        print(f"[{mark}] {item.get('name')}{suffix}")
    print("=" * 40)
    print(str(report.get("summary") or ""))


def check_paths(group: str, paths: list[str]) -> list[Check]:
    checks: list[Check] = []
    for relative in paths:
        path = ROOT / relative
        checks.append(Check(f"{group}: {relative}", path.exists(), "missing" if not path.exists() else ""))
    return checks


def run_project_script(name: str, script_name: str, *args: str) -> Check:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode == 0:
        return Check(name, True, compact_output(result.stdout))
    return Check(name, False, compact_output(result.stderr or result.stdout))


def check_generated_exports() -> list[Check]:
    checks: list[Check] = []
    with tempfile.TemporaryDirectory(prefix="sparkweave-ready-") as tmp:
        tmpdir = Path(tmp)
        demo_dir = tmpdir / "demo_materials"
        package_dir = tmpdir / "competition_package"

        checks.append(
            run_project_script(
                "Offline demo material export",
                "export_demo_materials.py",
                "--output",
                str(demo_dir),
            )
        )
        checks.extend(check_generated_files("Generated demo", demo_dir, GENERATED_DEMO_FILES))
        checks.extend(
            check_generated_content(
                "Generated demo content",
                demo_dir,
                [
                    ("sparkweave-demo-deck.html", "SparkWeave 演示页"),
                    ("sparkweave-demo-deck-outline.md", "SparkWeave 演示 PPT 骨架"),
                    ("sparkweave-7min-recording-script.md", "SparkWeave 7 分钟录屏讲稿"),
                    ("sparkweave-agent-collaboration-blueprint.md", "SparkWeave 多智能体协作蓝图"),
                    ("sparkweave-demo-fallback-assets.md", "SparkWeave 稳定演示兜底素材"),
                    ("sparkweave-defense-qa.md", "SparkWeave 答辩问答预案"),
                    ("sparkweave-competition-scorecard.md", "SparkWeave 赛题评分点证据表"),
                    ("sparkweave-final-pitch-checklist.md", "SparkWeave 最终答辩材料清单"),
                ],
            )
        )

        checks.append(
            run_project_script(
                "Competition package export",
                "export_competition_package.py",
                "--output",
                str(package_dir),
            )
        )
        checks.extend(
            check_generated_files(
                "Generated package",
                package_dir,
                [
                    "README.md",
                    "submission_manifest.md",
                    "demo_materials/sparkweave-demo-deck.html",
                    "demo_materials/sparkweave-agent-collaboration-blueprint.md",
                    "demo_materials/sparkweave-demo-fallback-assets.md",
                    "demo_materials/sparkweave-competition-scorecard.md",
                    "demo_materials/sparkweave-final-pitch-checklist.md",
                    "assets/agent-collaboration-blueprint.svg",
                    "course_templates/ai_learning_agents_systems.json",
                    "runtime/scripts/check_competition_readiness.py",
                    "runtime/scripts/check_release_safety.py",
                    "runtime/scripts/start_web.py",
                    "screenshots/screenshots-simplified-guide.png",
                ],
            )
        )
        checks.extend(
            check_generated_content(
                "Generated package content",
                package_dir,
                [
                    ("submission_manifest.md", "SparkWeave 比赛提交包索引"),
                    ("docs/iflytek-integration.md", "科大讯飞能力接入说明"),
                    ("demo_materials/sparkweave-demo-deck.html", "SparkWeave 演示页"),
                    ("demo_materials/sparkweave-agent-collaboration-blueprint.md", "SparkWeave 多智能体协作蓝图"),
                    ("demo_materials/sparkweave-demo-fallback-assets.md", "SparkWeave 稳定演示兜底素材"),
                    ("demo_materials/sparkweave-competition-scorecard.md", "SparkWeave 赛题评分点证据表"),
                    ("demo_materials/sparkweave-final-pitch-checklist.md", "SparkWeave 最终答辩材料清单"),
                    ("docs/demo-quickstart.md", "演示者 5 分钟入口"),
                ],
            )
        )
    return checks


def check_generated_files(group: str, root: Path, relative_paths: list[str]) -> list[Check]:
    return [
        Check(f"{group}: {relative}", (root / relative).exists(), "missing after export" if not (root / relative).exists() else "")
        for relative in relative_paths
    ]


def check_generated_content(group: str, root: Path, expectations: list[tuple[str, str]]) -> list[Check]:
    checks: list[Check] = []
    for relative, needle in expectations:
        path = root / relative
        if not path.exists():
            checks.append(Check(f"{group}: {relative}", False, "missing after export"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(f"{group}: {relative}", False, f"not utf-8 text: {exc}"))
            continue
        checks.append(
            Check(
                f"{group}: {relative}",
                needle in content,
                "" if needle in content else f"missing marker {needle!r}",
            )
        )
    return checks


def compact_output(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:180]


if __name__ == "__main__":
    raise SystemExit(main())
