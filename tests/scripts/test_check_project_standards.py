from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_project_standards.py"


def test_check_project_standards_current_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Structure, documentation links" in result.stdout


def test_check_project_standards_detects_missing_document_and_private_artifact(tmp_path: Path) -> None:
    build_minimal_project(tmp_path)
    (tmp_path / "docs" / "configuration-guide.md").unlink()
    private_path = tmp_path / "data" / "user" / "profile.json"
    private_path.parent.mkdir(parents=True)
    private_path.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "configuration-guide.md" in result.stdout
    assert "data/user/profile.json" in result.stdout


def build_minimal_project(root: Path) -> None:
    required_files = [
        ".editorconfig",
        ".gitattributes",
        ".env.example",
        ".gitignore",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
        ".github/workflows/ci.yml",
        "scripts/check_release_safety.py",
        "scripts/check_web_api_contract.py",
        "sparkweave/api/main.py",
    ]
    for relative in required_files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    (root / "tests").mkdir()
    (root / "web" / "src").mkdir(parents=True)

    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n[tool.ruff]\nline-length = 100\n[tool.ruff.lint]\nselect = ['E']\n",
        encoding="utf-8",
    )
    (root / "web" / "package.json").write_text(
        json.dumps({"scripts": {script: "true" for script in ("build", "check:api-contract", "check:design", "check:replacement", "lint", "verify")}}),
        encoding="utf-8",
    )
    indexed_docs = (
        "agent-orchestration-design.md",
        "api-development-guide.md",
        "configuration-guide.md",
        "data-storage-guide.md",
        "development-guide.md",
        "engineering-standards.md",
        "frontend-design-guide.md",
        "learner-profile-memory-design.md",
        "rag-system-design.md",
        "software-cup-delivery-checklist.md",
        "testing-guide.md",
    )
    docs_root = root / "docs"
    docs_root.mkdir()
    (docs_root / "README.md").write_text(
        "\n".join(f"[{name}](./{name})" for name in indexed_docs),
        encoding="utf-8",
    )
    for name in indexed_docs:
        (docs_root / name).write_text("", encoding="utf-8")
