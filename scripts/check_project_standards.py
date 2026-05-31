#!/usr/bin/env python
"""Validate repository layout, documentation links, and quality gate entry points."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PATHS = (
    ".editorconfig",
    ".gitattributes",
    ".env.example",
    ".gitignore",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    ".github/pull_request_template.md",
    "docs/README.md",
    "docs/development-guide.md",
    "docs/engineering-standards.md",
    "docs/testing-guide.md",
    "scripts/check_release_safety.py",
    "scripts/verify_project.py",
    "scripts/check_web_api_contract.py",
    "sparkweave/api/main.py",
    "tests",
    "web/package.json",
    "web/src",
)

INDEXED_DOCUMENTS = (
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

REQUIRED_WEB_SCRIPTS = (
    "build",
    "check:api-contract",
    "check:design",
    "check:replacement",
    "lint",
    "verify",
)

REQUIRED_PYPROJECT_TABLES = (
    ("tool", "pytest", "ini_options"),
    ("tool", "ruff"),
    ("tool", "ruff", "lint"),
)

FORBIDDEN_TRACKED_FILES = {".env", "web/.env.local"}
FORBIDDEN_TRACKED_PREFIXES = (
    ".pytest_cache/",
    ".pytest_tmp/",
    ".ruff_cache/",
    ".venv/",
    "data/knowledge_bases/",
    "data/memory/",
    "data/milvus/",
    "data/user/",
    "logs/",
    "web/dist/",
    "web/playwright-report/",
    "web/test-results/",
)

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_LINK_PREFIXES = ("#", "http://", "https://", "mailto:", "data:")


@dataclass(frozen=True)
class Finding:
    check: str
    message: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root to check.")
    args = parser.parse_args()
    root = args.root.resolve()

    findings = [
        *check_required_paths(root),
        *check_document_index(root),
        *check_markdown_links(root),
        *check_web_scripts(root),
        *check_python_config(root),
        *check_tracked_artifacts(root),
    ]

    print("SparkWeave project standards check")
    print("=" * 36)
    if findings:
        for finding in findings:
            print(f"[fail] {finding.check}: {finding.message}")
        print("=" * 36)
        print("Align the repository structure or documentation before publishing.")
        return 1

    print("[ok] Structure, documentation links, scripts, and tracked-artifact boundaries are valid.")
    return 0


def check_required_paths(root: Path) -> list[Finding]:
    return [
        Finding("required-path", f"missing {relative}")
        for relative in REQUIRED_PATHS
        if not (root / relative).exists()
    ]


def check_document_index(root: Path) -> list[Finding]:
    index_path = root / "docs" / "README.md"
    if not index_path.exists():
        return []
    index = index_path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    for document in INDEXED_DOCUMENTS:
        path = root / "docs" / document
        if not path.exists():
            findings.append(Finding("docs-index", f"indexed core document is missing: docs/{document}"))
        if f"./{document}" not in index:
            findings.append(Finding("docs-index", f"docs/README.md does not link to {document}"))
    return findings


def check_markdown_links(root: Path) -> list[Finding]:
    candidates = [
        root / "README.md",
        root / "CONTRIBUTING.md",
        root / "SECURITY.md",
        root / "sparkweave_cli" / "README.md",
        root / "web" / "README.md",
        *(root / "docs").glob("*.md"),
    ]
    findings: list[Finding] = []
    for source in candidates:
        if not source.exists():
            continue
        text = source.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK_RE.findall(text):
            local_target = normalize_link_target(target)
            if not local_target or local_target.startswith(SKIP_LINK_PREFIXES):
                continue
            resolved = (source.parent / local_target).resolve()
            if not resolved.exists():
                relative_source = source.relative_to(root).as_posix()
                findings.append(Finding("markdown-link", f"{relative_source} -> {local_target} does not exist"))
    return findings


def normalize_link_target(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    return target.split("#", 1)[0].strip()


def check_web_scripts(root: Path) -> list[Finding]:
    package_path = root / "web" / "package.json"
    if not package_path.exists():
        return []
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [Finding("web-scripts", f"web/package.json is invalid JSON: {error}")]
    scripts = package.get("scripts", {})
    return [
        Finding("web-scripts", f"web/package.json is missing script {script}")
        for script in REQUIRED_WEB_SCRIPTS
        if script not in scripts
    ]


def check_python_config(root: Path) -> list[Finding]:
    config_path = root / "pyproject.toml"
    if not config_path.exists():
        return []
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return [Finding("python-config", f"pyproject.toml is invalid TOML: {error}")]
    findings: list[Finding] = []
    for table in REQUIRED_PYPROJECT_TABLES:
        value: object = config
        for key in table:
            if not isinstance(value, dict) or key not in value:
                findings.append(Finding("python-config", f"pyproject.toml is missing [{' / '.join(table)}]"))
                break
            value = value[key]
    return findings


def check_tracked_artifacts(root: Path) -> list[Finding]:
    tracked_files = list_tracked_files(root)
    findings: list[Finding] = []
    for relative in tracked_files:
        normalized = relative.replace("\\", "/")
        if normalized in FORBIDDEN_TRACKED_FILES or any(
            normalized.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES
        ):
            findings.append(Finding("tracked-artifact", f"runtime or private artifact is tracked: {normalized}"))
    return findings


def list_tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and Path(result.stdout.strip()).resolve() == root:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            text=True,
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            return [line.strip() for line in tracked.stdout.splitlines() if line.strip()]
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    ]


if __name__ == "__main__":
    raise SystemExit(main())
