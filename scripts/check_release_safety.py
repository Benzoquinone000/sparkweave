#!/usr/bin/env python
"""Check tracked files for release-blocking legacy names and known secrets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent

LEGACY_TERMS = [
    "Deep" + "Tutor",
    "deep" + "tutor",
    "Tutor" + "Bot",
    "tutor" + "bot",
]

KNOWN_SECRET_FRAGMENTS = [
    "186" + "ae140",
    "252537dc" + "15175a6bd564e8a9764a74f3",
    "YTc0NjNi" + "YjRhMmZiNzQxNzI5OTVmMTAx",
]

ALLOWLISTED_PATHS = {
    ".env.example",
}

TEXT_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".css",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    value: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root to scan.")
    args = parser.parse_args()

    root = args.root.resolve()
    tracked_files = list_tracked_files(root)
    findings: list[Finding] = []
    tracked_env_files: list[str] = []

    for relative in tracked_files:
        if relative in ALLOWLISTED_PATHS:
            continue
        path = root / relative
        if path.name == ".env" or path.suffix == ".env":
            tracked_env_files.append(relative)
        findings.extend(scan_file(relative, path))

    print("SparkWeave release safety check")
    print("=" * 36)
    if tracked_env_files:
        for relative in tracked_env_files:
            print(f"[fail] tracked local env file: {relative}")
    if findings:
        for finding in findings:
            print(f"[fail] {finding.path}:{finding.line} {finding.kind}: {finding.value}")
    if not tracked_env_files and not findings:
        print("[ok] No tracked local env files, known secrets, or legacy project names found.")
        return 0
    print("=" * 36)
    print("Remove these items before publishing or packaging the project.")
    return 1


def list_tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    ]


def scan_file(relative: str, path: Path) -> list[Finding]:
    if not should_scan(path):
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for value in LEGACY_TERMS:
            if value in line:
                findings.append(Finding(relative, line_number, "legacy-name", value))
        for value in KNOWN_SECRET_FRAGMENTS:
            if value in line:
                findings.append(Finding(relative, line_number, "known-secret", mask(value)))
    return findings


def should_scan(path: Path) -> bool:
    if path.suffix in TEXT_EXTENSIONS:
        return True
    return path.name in {"Dockerfile", "LICENSE", "README", "Makefile"}


def mask(value: str) -> str:
    if len(value) <= 8:
        return f"{value[:2]}***{value[-2:]}"
    return f"{value[:4]}***{value[-4:]}"


if __name__ == "__main__":
    raise SystemExit(main())
