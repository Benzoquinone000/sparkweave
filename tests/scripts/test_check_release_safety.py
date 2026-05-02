from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_check_release_safety_current_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_safety.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "No tracked local env files" in result.stdout


def test_check_release_safety_flags_legacy_names_and_known_secrets(tmp_path: Path) -> None:
    legacy_name = "Deep" + "Tutor"
    known_secret = "252537dc" + "15175a6bd564e8a9764a74f3"
    (tmp_path / "notes.md").write_text(f"{legacy_name} should not be published.\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text(f"key={known_secret}\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_safety.py"), "--root", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "legacy-name" in result.stdout
    assert "known-secret" in result.stdout
    assert "2525***74f3" in result.stdout
