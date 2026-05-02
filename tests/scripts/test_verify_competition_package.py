from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_verify_competition_package_directory_and_archive(tmp_path: Path) -> None:
    package_dir = tmp_path / "competition_package"
    archive = tmp_path / "sparkweave_package.zip"

    export = run_script("export_competition_package.py", "--output", str(package_dir), "--archive", str(archive))
    assert export.returncode == 0, export.stderr or export.stdout
    assert (package_dir / "START_HERE.md").exists()

    directory_result = run_script("verify_competition_package.py", str(package_dir))
    archive_result = run_script("verify_competition_package.py", str(archive))

    assert directory_result.returncode == 0, directory_result.stderr or directory_result.stdout
    assert archive_result.returncode == 0, archive_result.stderr or archive_result.stdout
    assert "package OK" in directory_result.stdout
    assert "archive OK" in archive_result.stdout


def test_verify_competition_package_detects_checksum_mismatch(tmp_path: Path) -> None:
    package_dir = tmp_path / "competition_package"

    export = run_script("export_competition_package.py", "--output", str(package_dir))
    assert export.returncode == 0, export.stderr or export.stdout
    (package_dir / "index.html").write_text("tampered", encoding="utf-8")

    result = run_script("verify_competition_package.py", str(package_dir))

    assert result.returncode == 1
    assert "checksum mismatch" in result.stdout


def test_verify_competition_package_detects_unsafe_file(tmp_path: Path) -> None:
    package_dir = tmp_path / "competition_package"

    export = run_script("export_competition_package.py", "--output", str(package_dir))
    assert export.returncode == 0, export.stderr or export.stdout
    shutil.copy2(ROOT / ".env.example", package_dir / ".env")

    result = run_script("verify_competition_package.py", str(package_dir))

    assert result.returncode == 1
    assert "unsafe files" in result.stdout
