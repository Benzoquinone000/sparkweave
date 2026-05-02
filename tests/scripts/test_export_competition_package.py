from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_export_competition_package(tmp_path: Path) -> None:
    output = tmp_path / "competition_package"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "export_competition_package.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert (output / "submission_manifest.md").exists()
    assert (output / "docs" / "competition-demo-runbook.md").exists()
    assert (output / "course_templates" / "ai_learning_agents_systems.json").exists()
    assert (output / "assets" / "architecture.svg").exists()
    assert (output / "screenshots" / "screenshots-simplified-guide.png").exists()
    assert (output / "runtime" / ".env.example").exists()

    manifest = (output / "submission_manifest.md").read_text(encoding="utf-8")
    assert "SparkWeave 比赛提交包索引" in manifest
    assert "大模型教育智能体系统开发" in manifest
    assert "missing 0 file(s)" not in manifest
