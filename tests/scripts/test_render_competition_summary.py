from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run_summary(report: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "render_competition_summary.py"),
            str(report),
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_render_competition_summary_success(tmp_path: Path) -> None:
    report = tmp_path / "readiness.json"
    report.write_text(
        json.dumps(
            {
                "success": True,
                "ready_count": 20,
                "total_count": 20,
                "failed_count": 0,
                "summary": "All required competition materials are ready.",
                "checks": [
                    {"name": "Runtime collaboration route: backend emitter", "ok": True},
                    {"name": "Runtime collaboration route: frontend viewer", "ok": True},
                    {"name": "Runtime collaboration route: test coverage", "ok": True},
                    {"name": "External video loop: search service", "ok": True},
                    {"name": "External video loop: chat handoff", "ok": True},
                    {"name": "External video loop: viewer evidence", "ok": True},
                    {"name": "External video loop: test coverage", "ok": True},
                    {"name": "Effect assessment chain: backend report", "ok": True},
                    {"name": "Effect assessment chain: frontend card", "ok": True},
                    {"name": "Effect assessment chain: test coverage", "ok": True},
                    {"name": "Learning effect closed loop: backend remediation status", "ok": True},
                    {"name": "Learning effect closed loop: profile card", "ok": True},
                    {"name": "Learning effect closed loop: test coverage", "ok": True},
                    {"name": "Learning effect closed loop: design doc", "ok": True},
                    {"name": "Competition proof chain: backend package", "ok": True},
                    {"name": "Competition proof chain: frontend card", "ok": True},
                    {"name": "Competition proof chain: test coverage", "ok": True},
                    {"name": "User-facing diagnostics: settings status strip", "ok": True},
                    {"name": "User-facing knowledge progress: milestone view", "ok": True},
                    {"name": "User-facing chat trace: collaboration viewer", "ok": True},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_summary(report)

    assert result.returncode == 0, result.stderr
    assert "SparkWeave 赛前就绪摘要" in result.stdout
    assert "状态：OK 通过" in result.stdout
    assert "20/20 通过" in result.stdout
    assert "多智能体协作" in result.stdout
    assert "错因补救复测闭环" in result.stdout
    assert "CI artifact" in result.stdout
    assert "competition-preflight --with-build" in result.stdout


def test_render_competition_summary_writes_failure_output(tmp_path: Path) -> None:
    report = tmp_path / "readiness.json"
    output = tmp_path / "summary.md"
    report.write_text(
        json.dumps(
            {
                "success": False,
                "ready_count": 1,
                "total_count": 2,
                "failed_count": 1,
                "summary": "1 check(s) need attention before submission.",
                "checks": [
                    {"name": "Docs: README.md", "ok": True},
                    {"name": "Screenshots: web/screenshots-simplified-guide.png", "ok": False, "detail": "missing"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_summary(report, "--output", str(output))

    assert result.returncode == 0, result.stderr or result.stdout
    markdown = output.read_text(encoding="utf-8")
    assert "状态：FAIL 需要处理" in markdown
    assert "需要优先处理" in markdown
    assert "Screenshots: web/screenshots-simplified-guide.png：missing" in markdown
