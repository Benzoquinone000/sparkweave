from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from scripts.verify_project import build_plan, format_command

ROOT = Path(__file__).resolve().parents[2]


def test_build_plan_quick_contains_core_release_gates() -> None:
    labels = [step.label for step in build_plan("quick")]

    assert labels == [
        "Project standards",
        "Release safety",
        "Course templates",
        "Web API contract",
        "NG replacement guard",
        "Compile Python sources",
    ]


def test_build_plan_release_appends_frontend_gates() -> None:
    labels = [step.label for step in build_plan("release")]

    assert labels[:2] == ["Project standards", "Release safety"]
    assert labels[-2:] == ["Frontend replacement guard", "Frontend build"]


def test_format_command_quotes_spaces() -> None:
    step = build_plan("quick")[0]
    assert format_command(step).startswith(sys.executable if " " not in sys.executable else f'"{sys.executable}"')


def test_verify_project_list_mode() -> None:
    command = [sys.executable, "scripts/verify_project.py", "--profile", "frontend", "--list"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)

    assert result.returncode == 0
    assert "Frontend build" in result.stdout
    assert ("npm.cmd run build" in result.stdout) if os.name == "nt" else ("npm run build" in result.stdout)
