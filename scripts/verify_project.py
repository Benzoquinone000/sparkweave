#!/usr/bin/env python
"""Run SparkWeave's release-oriented engineering quality gates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Step:
    label: str
    command: tuple[str, ...]
    cwd: Path = ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("quick", "frontend", "release"),
        default="quick",
        help="quick=repo/backend gates, frontend=web gates, release=both.",
    )
    parser.add_argument("--list", action="store_true", help="List selected checks without running them.")
    args = parser.parse_args()

    steps = build_plan(args.profile)
    print(f"SparkWeave verification profile: {args.profile}")
    print("=" * 42)
    if args.list:
        for step in steps:
            print(f"- {step.label}: {format_command(step)}")
        return 0

    started_at = time.perf_counter()
    for step in steps:
        code = run_step(step)
        if code:
            print("=" * 42)
            print(f"[fail] {step.label} failed with exit code {code}")
            return code

    duration = time.perf_counter() - started_at
    print("=" * 42)
    print(f"[ok] SparkWeave verification passed in {duration:.1f}s.")
    return 0


def build_plan(profile: str) -> list[Step]:
    quick_steps = [
        python_step("Project standards", "scripts/check_project_standards.py"),
        python_step("Release safety", "scripts/check_release_safety.py"),
        python_step("Course templates", "scripts/check_course_templates.py"),
        python_step("Web API contract", "scripts/check_web_api_contract.py"),
        python_step("NG replacement guard", "scripts/check_ng_replacement.py"),
        python_step("Compile Python sources", "-m", "compileall", "-q", "sparkweave", "sparkweave_cli", "scripts"),
    ]
    frontend_steps = [
        npm_step("Frontend lint", "lint"),
        npm_step("Frontend design contract", "check:design"),
        npm_step("Frontend API contract", "check:api-contract"),
        npm_step("Frontend replacement guard", "check:replacement"),
        npm_step("Frontend build", "build"),
    ]
    if profile == "quick":
        return quick_steps
    if profile == "frontend":
        return frontend_steps
    if profile == "release":
        return [*quick_steps, *frontend_steps]
    raise ValueError(f"Unknown profile: {profile}")


def python_step(label: str, *args: str) -> Step:
    return Step(label=label, command=(sys.executable, *args), cwd=ROOT)


def npm_step(label: str, script: str) -> Step:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return Step(label=label, command=(npm, "run", script), cwd=ROOT / "web")


def run_step(step: Step) -> int:
    print(f"\n[verify] {step.label}")
    print(f"[verify] cwd={step.cwd}")
    print(f"[verify] command={format_command(step)}")
    started_at = time.perf_counter()
    result = subprocess.run(step.command, cwd=step.cwd, check=False)
    duration = time.perf_counter() - started_at
    if result.returncode == 0:
        print(f"[verify] {step.label} passed in {duration:.1f}s")
    return result.returncode


def format_command(step: Step) -> str:
    return " ".join(quote_part(part) for part in step.command)


def quote_part(part: str) -> str:
    if not part or any(char.isspace() for char in part):
        return f'"{part}"'
    return part


if __name__ == "__main__":
    raise SystemExit(main())
