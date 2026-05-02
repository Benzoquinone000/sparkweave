#!/usr/bin/env python
"""Verify an exported SparkWeave competition package directory or zip archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
import zipfile


REQUIRED_FILES = [
    "START_HERE.md",
    "index.html",
    "checksums.sha256",
    "submission_manifest.md",
    "demo_materials/sparkweave-demo-deck.html",
    "demo_materials/sparkweave-competition-scorecard.md",
    "demo_materials/sparkweave-7min-recording-script.md",
    "assets/architecture.svg",
    "runtime/scripts/start_web.py",
    "screenshots/screenshots-simplified-guide.png",
]

FORBIDDEN_FILES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".secrets.baseline",
}

FORBIDDEN_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "data/user",
    "data/memory",
    "web/dist",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package",
        nargs="?",
        type=Path,
        default=Path("dist/competition_package"),
        help="Competition package directory or zip archive.",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Optional path to write the verification report.",
    )
    args = parser.parse_args()

    report = verify_package(args.package)
    emit_report(report, fmt=args.format, output=args.output)
    return 0 if report["ok"] else 1


def verify_package(package: Path) -> dict[str, object]:
    if not package.exists():
        return failure_report(
            package,
            kind="missing",
            headline=f"missing package: {package}",
        )

    if package.is_file():
        return verify_archive(package)
    return verify_directory(package)


def verify_archive(archive_path: Path) -> dict[str, object]:
    if archive_path.suffix.lower() != ".zip":
        return failure_report(
            archive_path,
            kind="archive",
            headline=f"unsupported archive type: {archive_path}",
        )
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.namelist()
            problems = unsafe_archive_entries(entries)
            if problems:
                return failure_report(
                    archive_path,
                    kind="archive",
                    headline="archive contains unsafe entries:",
                    details=problems[:10],
                    archive_entries=len(entries),
                )
            with tempfile.TemporaryDirectory(prefix="sparkweave-package-verify-") as tmp:
                archive.extractall(tmp)
                extracted = Path(tmp) / "competition_package"
                result = verify_directory(extracted, source_label=str(archive_path))
                result["kind"] = "archive"
                result["path"] = str(archive_path)
                result["archive_entries"] = len(entries)
                if not result["ok"]:
                    return result
    except zipfile.BadZipFile as exc:
        return failure_report(
            archive_path,
            kind="archive",
            headline=f"bad zip file: {exc}",
        )

    result["messages"].append(f"archive OK: {archive_path}")
    return result


def verify_directory(package_dir: Path, *, source_label: str | None = None) -> dict[str, object]:
    label = source_label or str(package_dir)
    if not package_dir.is_dir():
        return failure_report(
            package_dir,
            kind="directory",
            headline=f"package is not a directory: {package_dir}",
        )

    missing = [relative for relative in REQUIRED_FILES if not (package_dir / relative).exists()]
    if missing:
        return failure_report(
            package_dir,
            kind="directory",
            headline="missing required files:",
            details=missing,
        )

    unsafe = unsafe_directory_entries(package_dir)
    if unsafe:
        return failure_report(
            package_dir,
            kind="directory",
            headline="package contains unsafe files:",
            details=unsafe[:10],
        )

    checksum_error, checksum_count = verify_checksums(package_dir)
    if checksum_error:
        return failure_report(
            package_dir,
            kind="directory",
            headline=checksum_error,
        )

    file_count = sum(1 for path in package_dir.rglob("*") if path.is_file())
    return {
        "ok": True,
        "path": str(package_dir),
        "kind": "directory",
        "headline": f"package OK: {label} ({file_count} files)",
        "messages": [f"package OK: {label} ({file_count} files)"],
        "errors": [],
        "details": [],
        "file_count": file_count,
        "checksum_count": checksum_count,
        "archive_entries": 0,
        "required_files": REQUIRED_FILES,
    }


def failure_report(
    path: Path,
    *,
    kind: str,
    headline: str,
    details: list[str] | None = None,
    archive_entries: int = 0,
) -> dict[str, object]:
    return {
        "ok": False,
        "path": str(path),
        "kind": kind,
        "headline": headline,
        "messages": [],
        "errors": [headline],
        "details": details or [],
        "file_count": 0,
        "checksum_count": 0,
        "archive_entries": archive_entries,
        "required_files": REQUIRED_FILES,
    }


def emit_report(report: dict[str, object], *, fmt: str, output: Path | None = None) -> None:
    if fmt == "json":
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return

    for message in report.get("messages", []):
        print(f"[competition-verify] {message}")

    if not report["ok"]:
        print(f"[competition-verify] {report['headline']}")
        for item in list(report.get("details", []))[:10]:
            print(f"- {item}")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unsafe_archive_entries(entries: list[str]) -> list[str]:
    problems: list[str] = []
    for entry in entries:
        normalized = entry.replace("\\", "/").strip()
        parts = [part for part in normalized.split("/") if part]
        if not normalized or normalized.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
            problems.append(entry)
            continue
        if not normalized.startswith("competition_package/"):
            problems.append(entry)
            continue
        if is_forbidden_parts(parts):
            problems.append(entry)
    return problems


def unsafe_directory_entries(package_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in package_dir.rglob("*"):
        relative = path.relative_to(package_dir).as_posix()
        parts = [part for part in relative.split("/") if part]
        if is_forbidden_parts(parts):
            problems.append(relative)
    return problems


def is_forbidden_parts(parts: list[str]) -> bool:
    if parts and parts[-1] in FORBIDDEN_FILES:
        return True
    joined = "/".join(parts)
    wrapped = f"/{joined}/"
    return any(f"/{forbidden}/" in wrapped for forbidden in FORBIDDEN_DIRS)


def verify_checksums(package_dir: Path) -> tuple[str, int]:
    checksum_path = package_dir / "checksums.sha256"
    try:
        lines = [line.strip() for line in checksum_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        return f"checksums.sha256 is not utf-8 text: {exc}", 0

    expected_files = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file() and path != checksum_path
    }
    recorded: dict[str, str] = {}
    for line in lines:
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            return f"invalid checksum line: {line[:80]}", 0
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            return f"invalid sha256 digest for {relative}", 0
        recorded[relative] = digest.lower()

    missing = sorted(expected_files - recorded.keys())
    extra = sorted(recorded.keys() - expected_files)
    if missing:
        return "missing checksum for " + ", ".join(missing[:5]), len(recorded)
    if extra:
        return "checksum references missing file " + ", ".join(extra[:5]), len(recorded)

    mismatched = [relative for relative, digest in recorded.items() if sha256_file(package_dir / relative) != digest]
    if mismatched:
        return "checksum mismatch: " + ", ".join(mismatched[:5]), len(recorded)
    return "", len(recorded)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
