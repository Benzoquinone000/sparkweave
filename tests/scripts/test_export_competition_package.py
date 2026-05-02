from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import zipfile


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
    assert (output / "sparkweave-agent-collaboration-blueprint.md").exists()
    assert (output / "sparkweave-demo-fallback-assets.md").exists()
    assert (output / "sparkweave-defense-qa.md").exists()
    assert (output / "sparkweave-competition-scorecard.md").exists()
    assert (output / "sparkweave-evaluator-one-pager.md").exists()
    assert (output / "sparkweave-final-pitch-checklist.md").exists()
    assert (output.parent / "assets" / "agent-collaboration-blueprint.svg").exists()

    deck = (output / "sparkweave-demo-deck-outline.md").read_text(encoding="utf-8")
    deck_html = (output / "sparkweave-demo-deck.html").read_text(encoding="utf-8")
    script = (output / "sparkweave-7min-recording-script.md").read_text(encoding="utf-8")
    agent_blueprint = (output / "sparkweave-agent-collaboration-blueprint.md").read_text(encoding="utf-8")
    fallback_assets = (output / "sparkweave-demo-fallback-assets.md").read_text(encoding="utf-8")
    qa = (output / "sparkweave-defense-qa.md").read_text(encoding="utf-8")
    scorecard = (output / "sparkweave-competition-scorecard.md").read_text(encoding="utf-8")
    one_pager = (output / "sparkweave-evaluator-one-pager.md").read_text(encoding="utf-8")
    checklist = (output / "sparkweave-final-pitch-checklist.md").read_text(encoding="utf-8")
    assert "SparkWeave 演示 PPT 骨架" in deck
    assert "<!doctype html>" in deck_html
    assert "SparkWeave 演示页" in deck_html
    assert "../assets/agent-collaboration-blueprint.svg" in deck
    assert "../assets/agent-collaboration-blueprint.svg" in deck_html
    assert "大模型教育智能体系统开发" in deck
    assert "SparkWeave 7 分钟录屏讲稿" in script
    assert "SparkWeave 多智能体协作蓝图" in agent_blueprint
    assert "graph LR" in agent_blueprint
    assert "../assets/agent-collaboration-blueprint.svg" in agent_blueprint
    assert "SparkWeave 稳定演示兜底素材" in fallback_assets
    assert "预置练习" in fallback_assets
    assert "录屏兜底讲法" in fallback_assets
    assert "为什么不是普通聊天机器人" in qa
    assert "SparkWeave 赛题评分点证据表" in scorecard
    assert "多智能体协同的资源生成" in scorecard
    assert "SparkWeave 评委一页说明" in one_pager
    assert "五项赛题对齐" in one_pager
    assert "赛前命令" in one_pager
    assert "SparkWeave 最终答辩材料清单" in checklist
    assert "科大讯飞" in checklist


def test_export_competition_package(tmp_path: Path) -> None:
    output = tmp_path / "competition_package"

    result = run_script("export_competition_package.py", output)

    assert result.returncode == 0, result.stderr or result.stdout
    assert (output / "index.html").exists()
    assert (output / "checksums.sha256").exists()
    assert (output / "submission_manifest.md").exists()
    assert (output / "docs" / "competition-demo-runbook.md").exists()
    assert (output / "docs" / "iflytek-integration.md").exists()
    assert (output / "course_templates" / "ai_learning_agents_systems.json").exists()
    assert (output / "assets" / "architecture.svg").exists()
    assert (output / "assets" / "agent-collaboration-blueprint.svg").exists()
    assert (output / "screenshots" / "screenshots-simplified-guide.png").exists()
    assert (output / "runtime" / ".env.example").exists()
    assert (output / "runtime" / "scripts" / "check_competition_readiness.py").exists()
    assert (output / "runtime" / "scripts" / "check_release_safety.py").exists()
    assert (output / "runtime" / "scripts" / "render_competition_summary.py").exists()
    assert (output / "runtime" / "scripts" / "export_demo_materials.py").exists()
    assert (output / "demo_materials" / "sparkweave-demo-deck-outline.md").exists()
    assert (output / "demo_materials" / "sparkweave-demo-deck.html").exists()
    assert (output / "demo_materials" / "sparkweave-7min-recording-script.md").exists()
    assert (output / "demo_materials" / "sparkweave-agent-collaboration-blueprint.md").exists()
    assert (output / "demo_materials" / "sparkweave-demo-fallback-assets.md").exists()
    assert (output / "demo_materials" / "sparkweave-defense-qa.md").exists()
    assert (output / "demo_materials" / "sparkweave-competition-scorecard.md").exists()
    assert (output / "demo_materials" / "sparkweave-evaluator-one-pager.md").exists()
    assert (output / "demo_materials" / "sparkweave-final-pitch-checklist.md").exists()

    manifest = (output / "submission_manifest.md").read_text(encoding="utf-8")
    index = (output / "index.html").read_text(encoding="utf-8")
    assert "SparkWeave 星火织学提交包" in index
    assert "demo_materials/sparkweave-demo-deck.html" in index
    assert "screenshots/screenshots-simplified-guide.png" in index
    assert "checksums.sha256" in index
    assert "五项要求证据" in index
    checksums = (output / "checksums.sha256").read_text(encoding="utf-8")
    assert "index.html" in checksums
    assert "submission_manifest.md" in checksums
    assert "demo_materials/sparkweave-competition-scorecard.md" in checksums
    assert "SparkWeave 比赛提交包索引" in manifest
    assert "大模型教育智能体系统开发" in manifest
    assert "demo_materials/sparkweave-demo-deck-outline.md" in manifest
    assert "demo_materials/sparkweave-demo-deck.html" in manifest
    assert "demo_materials/sparkweave-agent-collaboration-blueprint.md" in manifest
    assert "demo_materials/sparkweave-demo-fallback-assets.md" in manifest
    assert "demo_materials/sparkweave-competition-scorecard.md" in manifest
    assert "demo_materials/sparkweave-evaluator-one-pager.md" in manifest
    assert "demo_materials/sparkweave-final-pitch-checklist.md" in manifest
    assert "docs/iflytek-integration.md" in manifest
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


def test_export_competition_package_can_write_archive(tmp_path: Path) -> None:
    output = tmp_path / "competition_package"
    archive = tmp_path / "sparkweave_package.zip"

    result = run_script("export_competition_package.py", output, "--archive", str(archive))

    assert result.returncode == 0, result.stderr or result.stdout
    assert archive.exists()
    assert f"[competition-package] archived to {archive}" in result.stdout
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
    assert "competition_package/index.html" in names
    assert "competition_package/checksums.sha256" in names
    assert "competition_package/submission_manifest.md" in names
    assert "competition_package/demo_materials/sparkweave-competition-scorecard.md" in names
    assert "competition_package/runtime/scripts/start_web.py" in names
