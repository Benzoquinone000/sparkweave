#!/usr/bin/env python
"""Verify an exported SparkWeave competition package directory or zip archive."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path
import zipfile


REQUIRED_FILES = [
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
    args = parser.parse_args()

    package = args.package
    if not package.exists():
        print(f"[competition-verify] missing package: {package}")
        return 1

    if package.is_file():
        return verify_archive(package)
    return verify_directory(package)


def verify_archive(archive_path: Path) -> int:
    if archive_path.suffix.lower() != ".zip":
        print(f"[competition-verify] unsupported archive type: {archive_path}")
        return 1
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.namelist()
            problems = unsafe_archive_entries(entries)
            if problems:
                print("[competition-verify] archive contains unsafe entries:")
                for item in problems[:10]:
                    print(f"- {item}")
                return 1
            with tempfile.TemporaryDirectory(prefix="sparkweave-package-verify-") as tmp:
                archive.extractall(tmp)
                extracted = Path(tmp) / "competition_package"
                result = verify_directory(extracted, source_label=str(archive_path))
                if result != 0:
                    return result
    except zipfile.BadZipFile as exc:
        print(f"[competition-verify] bad zip file: {exc}")
        return 1

    print(f"[competition-verify] archive OK: {archive_path}")
    return 0


def verify_directory(package_dir: Path, *, source_label: str | None = None) -> int:
    label = source_label or str(package_dir)
    if not package_dir.is_dir():
        print(f"[competition-verify] package is not a directory: {package_dir}")
        return 1

    missing = [relative for relative in REQUIRED_FILES if not (package_dir / relative).exists()]
    if missing:
        print("[competition-verify] missing required files:")
        for item in missing:
            print(f"- {item}")
        return 1

    unsafe = unsafe_directory_entries(package_dir)
    if unsafe:
        print("[competition-verify] package contains unsafe files:")
        for item in unsafe[:10]:
            print(f"- {item}")
        return 1

    checksum_error = verify_checksums(package_dir)
    if checksum_error:
        print(f"[competition-verify] {checksum_error}")
        return 1

    file_count = sum(1 for path in package_dir.rglob("*") if path.is_file())
    print(f"[competition-verify] package OK: {label} ({file_count} files)")
    return 0


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


def verify_checksums(package_dir: Path) -> str:
    checksum_path = package_dir / "checksums.sha256"
    try:
        lines = [line.strip() for line in checksum_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        return f"checksums.sha256 is not utf-8 text: {exc}"

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
            return f"invalid checksum line: {line[:80]}"
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            return f"invalid sha256 digest for {relative}"
        recorded[relative] = digest.lower()

    missing = sorted(expected_files - recorded.keys())
    extra = sorted(recorded.keys() - expected_files)
    if missing:
        return "missing checksum for " + ", ".join(missing[:5])
    if extra:
        return "checksum references missing file " + ", ".join(extra[:5])

    mismatched = [relative for relative, digest in recorded.items() if sha256_file(package_dir / relative) != digest]
    if mismatched:
        return "checksum mismatch: " + ", ".join(mismatched[:5])
    return ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
