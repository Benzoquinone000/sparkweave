from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_check_competition_readiness() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_competition_readiness.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "SparkWeave competition readiness" in result.stdout
    assert "[ok] Course template schema" in result.stdout
    assert "[ok] Runtime collaboration route: backend emitter" in result.stdout
    assert "[ok] Runtime collaboration route: frontend viewer" in result.stdout
    assert "[ok] Runtime collaboration route: test coverage" in result.stdout
    assert "[ok] External video loop: search service" in result.stdout
    assert "[ok] External video loop: chat handoff" in result.stdout
    assert "[ok] External video loop: viewer evidence" in result.stdout
    assert "[ok] External video loop: test coverage" in result.stdout
    assert "[ok] Effect assessment chain: backend report" in result.stdout
    assert "[ok] Effect assessment chain: frontend card" in result.stdout
    assert "[ok] Effect assessment chain: test coverage" in result.stdout
    assert "[ok] Competition proof chain: backend package" in result.stdout
    assert "[ok] Competition proof chain: frontend card" in result.stdout
    assert "[ok] Competition proof chain: test coverage" in result.stdout
    assert "[ok] User-facing diagnostics: settings status strip" in result.stdout
    assert "[ok] User-facing diagnostics: test coverage" in result.stdout
    assert "[ok] Assets: docs/assets/agent-collaboration-blueprint.svg" in result.stdout
    assert "[ok] Offline demo material export" in result.stdout
    assert "[ok] Generated demo content: sparkweave-demo-deck.html" in result.stdout
    assert "[ok] Generated demo content: sparkweave-agent-collaboration-blueprint.md" in result.stdout
    assert "[ok] Generated demo content: sparkweave-demo-fallback-assets.md" in result.stdout
    assert "[ok] Generated demo content: sparkweave-competition-scorecard.md" in result.stdout
    assert "[ok] Generated demo content: sparkweave-evaluator-one-pager.md" in result.stdout
    assert "[ok] Generated demo content: sparkweave-final-pitch-checklist.md" in result.stdout
    assert "[ok] Competition package export" in result.stdout
    assert "[ok] Generated package content: docs/demo-quickstart.md" in result.stdout
    assert "[ok] Generated package content: docs/iflytek-integration.md" in result.stdout
    assert "All required competition materials are ready." in result.stdout


def test_check_competition_readiness_json_report(tmp_path: Path) -> None:
    output = tmp_path / "readiness.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_competition_readiness.py"),
            "--format",
            "json",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    written_report = json.loads(output.read_text(encoding="utf-8"))
    check_names = {item["name"] for item in report["checks"]}

    assert report == written_report
    assert report["success"] is True
    assert report["failed_count"] == 0
    assert report["ready_count"] == report["total_count"]
    assert "Generated demo content: sparkweave-demo-deck.html" in check_names
    assert "Generated demo content: sparkweave-agent-collaboration-blueprint.md" in check_names
    assert "Generated demo content: sparkweave-demo-fallback-assets.md" in check_names
    assert "Generated demo content: sparkweave-evaluator-one-pager.md" in check_names
    assert "Generated demo content: sparkweave-final-pitch-checklist.md" in check_names
    assert "Runtime collaboration route: backend emitter" in check_names
    assert "Runtime collaboration route: frontend viewer" in check_names
    assert "Runtime collaboration route: test coverage" in check_names
    assert "External video loop: search service" in check_names
    assert "External video loop: chat handoff" in check_names
    assert "External video loop: viewer evidence" in check_names
    assert "External video loop: test coverage" in check_names
    assert "Effect assessment chain: backend report" in check_names
    assert "Effect assessment chain: frontend card" in check_names
    assert "Effect assessment chain: test coverage" in check_names
    assert "Competition proof chain: backend package" in check_names
    assert "Competition proof chain: frontend card" in check_names
    assert "Competition proof chain: test coverage" in check_names
    assert "User-facing diagnostics: settings status strip" in check_names
    assert "User-facing diagnostics: test coverage" in check_names
    assert "Assets: docs/assets/agent-collaboration-blueprint.svg" in check_names
    assert "Generated package: assets/agent-collaboration-blueprint.svg" in check_names
    assert "Generated package content: docs/iflytek-integration.md" in check_names
    assert "Generated package content: demo_materials/sparkweave-demo-fallback-assets.md" in check_names
    assert "Generated package content: demo_materials/sparkweave-competition-scorecard.md" in check_names
    assert "Generated package content: demo_materials/sparkweave-evaluator-one-pager.md" in check_names
