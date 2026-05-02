from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_check_competition_readiness() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_competition_readiness.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "SparkWeave competition readiness" in result.stdout
    assert "[ok] Course template schema" in result.stdout
    assert "[ok] Offline demo material export" in result.stdout
    assert "[ok] Competition package export" in result.stdout
    assert "All required competition materials are ready." in result.stdout
