from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_check_competition_visuals_text() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_competition_visuals.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Competition visual plan is complete." in result.stdout
    assert "[ok] Visualization plan completion" in result.stdout
    assert "[ok] Visualization completion report" in result.stdout
    assert "[ok] Completion wording: docs/competition-visualization-wow-plan.md" in result.stdout
    assert "[ok] Completion wording: docs/sparkweave-execution-plan.md" in result.stdout


def test_check_competition_visuals_json_report(tmp_path: Path) -> None:
    output = tmp_path / "visual-readiness.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_competition_visuals.py"),
            "--format",
            "json",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    written_report = json.loads(output.read_text(encoding="utf-8"))
    check_names = {item["name"] for item in report["checks"]}

    assert report == written_report
    assert report["success"] is True
    assert report["summary"] == "Competition visual plan is complete."
    assert "Completion wording: docs/competition-visualization-completion-report.md" in check_names
    assert "Completion wording: docs/sparkweave-execution-plan.md" in check_names
