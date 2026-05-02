from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def run_script(script: str, output: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / script),
            "--output",
            str(output),
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_export_demo_materials(tmp_path: Path) -> None:
    output = tmp_path / "demo_materials"

    result = run_script("export_demo_materials.py", output)

    assert result.returncode == 0, result.stderr or result.stdout
    assert (output / "sparkweave-demo-deck-outline.md").exists()
    assert (output / "sparkweave-demo-deck.html").exists()
    assert (output / "sparkweave-7min-recording-script.md").exists()
    assert (output / "sparkweave-defense-qa.md").exists()
    assert (output / "sparkweave-competition-scorecard.md").exists()

    deck = (output / "sparkweave-demo-deck-outline.md").read_text(encoding="utf-8")
    deck_html = (output / "sparkweave-demo-deck.html").read_text(encoding="utf-8")
    script = (output / "sparkweave-7min-recording-script.md").read_text(encoding="utf-8")
    qa = (output / "sparkweave-defense-qa.md").read_text(encoding="utf-8")
    scorecard = (output / "sparkweave-competition-scorecard.md").read_text(encoding="utf-8")
    assert "SparkWeave 演示 PPT 骨架" in deck
    assert "<!doctype html>" in deck_html
    assert "SparkWeave 演示页" in deck_html
    assert "大模型教育智能体系统开发" in deck
    assert "SparkWeave 7 分钟录屏讲稿" in script
    assert "为什么不是普通聊天机器人" in qa
    assert "SparkWeave 赛题评分点证据表" in scorecard
    assert "多智能体协同的资源生成" in scorecard


def test_export_competition_package(tmp_path: Path) -> None:
    output = tmp_path / "competition_package"

    result = run_script("export_competition_package.py", output)

    assert result.returncode == 0, result.stderr or result.stdout
    assert (output / "submission_manifest.md").exists()
    assert (output / "docs" / "competition-demo-runbook.md").exists()
    assert (output / "course_templates" / "ai_learning_agents_systems.json").exists()
    assert (output / "assets" / "architecture.svg").exists()
    assert (output / "screenshots" / "screenshots-simplified-guide.png").exists()
    assert (output / "runtime" / ".env.example").exists()
    assert (output / "runtime" / "scripts" / "check_competition_readiness.py").exists()
    assert (output / "runtime" / "scripts" / "check_release_safety.py").exists()
    assert (output / "runtime" / "scripts" / "export_demo_materials.py").exists()
    assert (output / "demo_materials" / "sparkweave-demo-deck-outline.md").exists()
    assert (output / "demo_materials" / "sparkweave-demo-deck.html").exists()
    assert (output / "demo_materials" / "sparkweave-7min-recording-script.md").exists()
    assert (output / "demo_materials" / "sparkweave-defense-qa.md").exists()
    assert (output / "demo_materials" / "sparkweave-competition-scorecard.md").exists()

    manifest = (output / "submission_manifest.md").read_text(encoding="utf-8")
    assert "SparkWeave 比赛提交包索引" in manifest
    assert "大模型教育智能体系统开发" in manifest
    assert "demo_materials/sparkweave-demo-deck-outline.md" in manifest
    assert "demo_materials/sparkweave-demo-deck.html" in manifest
    assert "demo_materials/sparkweave-competition-scorecard.md" in manifest
    assert "missing 0 file(s)" not in manifest


def test_export_competition_package_accepts_course_template(tmp_path: Path) -> None:
    output = tmp_path / "math_package"

    result = run_script("export_competition_package.py", output, "--template", "higher_math_limits_derivatives")

    assert result.returncode == 0, result.stderr or result.stdout
    manifest = (output / "submission_manifest.md").read_text(encoding="utf-8")
    scorecard = (output / "demo_materials" / "sparkweave-competition-scorecard.md").read_text(encoding="utf-8")

    assert "高等数学" in manifest
    assert "高等数学" in scorecard
    assert "SparkWeave 赛题评分点证据表" in scorecard
