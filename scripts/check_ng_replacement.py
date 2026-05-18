#!/usr/bin/env python
"""Check that active code paths point at sparkweave and web."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

ACTIVE_DIRS = {
    "sparkweave_cli",
    "sparkweave",
    "scripts",
    "tests",
    "web",
}

ACTIVE_FILES = {
    ".dockerignore",
    ".env.example",
    ".env.example_CN",
    "Dockerfile",
    "README.md",
    "docker-compose.dev.yml",
    "docker-compose.yml",
    "pyproject.toml",
    "requirements.txt",
}

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}

TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".dockerignore",
    ".env",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    message: str


LEGACY_PACKAGE = "deep" + "tutor"
LEGACY_BOT = "tutor" + "bot"

RULES = [
    Rule(re.compile(rf"\bfrom\s+{LEGACY_PACKAGE}(?:_ng)?(?:\.|\s+import\b)", re.IGNORECASE), "legacy Python import"),
    Rule(re.compile(rf"\bimport\s+{LEGACY_PACKAGE}(?:_ng)?(?:\b|\.)", re.IGNORECASE), "legacy Python import"),
    Rule(re.compile(rf"\b{LEGACY_PACKAGE}(?:_ng)?\.", re.IGNORECASE), "legacy Python package reference"),
    Rule(re.compile(rf"\b{LEGACY_PACKAGE}(?:_ng)?\b", re.IGNORECASE), "legacy project/package name"),
    Rule(re.compile(rf"\b{LEGACY_PACKAGE}_cli\b", re.IGNORECASE), "legacy CLI package name"),
    Rule(re.compile(rf"\b{LEGACY_BOT}\b", re.IGNORECASE), "legacy bot name"),
    Rule(re.compile(r"(?<!\.)\.next(?:[\\/]|$|\b)"), "legacy Next.js artifact/path"),
    Rule(re.compile(r"\bnext\s+(?:dev|start|build)\b"), "legacy Next.js command"),
]

DOC_ONLY_RULES = [
    Rule(re.compile(r"Frontend\s*\(Next"), "current docs still mention Next frontend"),
    Rule(re.compile(r"前端（Next"), "current Chinese docs still mention Next frontend"),
]


def is_active_path(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    first = rel.split("/", 1)[0]
    if rel in ACTIVE_FILES:
        return True
    return first in ACTIVE_DIRS


def is_text_file(path: Path) -> bool:
    if path.name in ACTIVE_FILES:
        return True
    return path.suffix in TEXT_EXTENSIONS


def should_skip(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    return any(part in SKIP_DIRS for part in rel_parts)


def allowed_line(rel: str, line: str) -> bool:
    # Compatibility variables are intentionally honored by web/runtime scripts.
    if "NEXT_PUBLIC_API_BASE" in line:
        return True
    return False


def scan() -> list[str]:
    violations: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path) or not is_active_path(path) or not is_text_file(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel == "scripts/check_ng_replacement.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rules = RULES + (DOC_ONLY_RULES if rel == "README.md" else [])
        for number, line in enumerate(text.splitlines(), start=1):
            if allowed_line(rel, line):
                continue
            for rule in rules:
                if rule.pattern.search(line):
                    violations.append(f"{rel}:{number}: {rule.message}: {line.strip()}")
    return violations


def main() -> int:
    violations = scan()
    if violations:
        print("[ng-replacement] Legacy dependency references found:")
        for item in violations:
            print(f"- {item}")
        return 1
    print("[ng-replacement] Active code and setup docs point at sparkweave/web.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

