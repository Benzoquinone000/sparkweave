#!/usr/bin/env python
"""Run a lightweight SparkWeave competition readiness check."""

from __future__ import annotations

from dataclasses import dataclass
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
    "docs/guided-learning.md",
    "docs/learner-profile-design.md",
    "docs/ai-coding-statement.md",
]

REQUIRED_RUNTIME_FILES = [
    ".env.example",
    "requirements.txt",
    "requirements/server.txt",
    "requirements/math-animator.txt",
    "scripts/start_web.py",
    "scripts/check_install.py",
    "scripts/export_demo_materials.py",
    "scripts/export_competition_package.py",
]

REQUIRED_ASSETS = [
    "assets/logo-ver2.png",
    "assets/architecture.svg",
    "docs/assets/guided-learning-loop.svg",
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
    "sparkweave-defense-qa.md",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def main() -> int:
    checks: list[Check] = []
    checks.extend(check_paths("Docs", REQUIRED_DOCS))
    checks.extend(check_paths("Runtime", REQUIRED_RUNTIME_FILES))
    checks.extend(check_paths("Assets", REQUIRED_ASSETS))
    checks.extend(check_paths("Screenshots", REQUIRED_SCREENSHOTS))
    checks.extend(check_paths("Course templates", REQUIRED_COURSE_TEMPLATES))
    checks.append(run_project_script("Course template schema", "check_course_templates.py"))
    checks.extend(check_generated_exports())

    failed = [item for item in checks if not item.ok]
    print("\nSparkWeave competition readiness")
    print("=" * 40)
    for item in checks:
        mark = "ok" if item.ok else "fail"
        suffix = f" - {item.detail}" if item.detail else ""
        print(f"[{mark}] {item.name}{suffix}")
    print("=" * 40)
    if failed:
        print(f"{len(failed)} check(s) need attention before submission.")
        return 1
    print("All required competition materials are ready.")
    return 0


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
                    "course_templates/ai_learning_agents_systems.json",
                    "runtime/scripts/start_web.py",
                    "screenshots/screenshots-simplified-guide.png",
                ],
            )
        )
    return checks


def check_generated_files(group: str, root: Path, relative_paths: list[str]) -> list[Check]:
    return [
        Check(f"{group}: {relative}", (root / relative).exists(), "missing after export" if not (root / relative).exists() else "")
        for relative in relative_paths
    ]


def compact_output(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:180]


if __name__ == "__main__":
    raise SystemExit(main())
