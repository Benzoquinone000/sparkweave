from __future__ import annotations

from pathlib import Path
import re
import tomllib


def test_ng_package_has_no_direct_legacy_imports() -> None:
    package_root = Path(__file__).resolve().parents[2] / "sparkweave"
    direct_import = re.compile(r"^\s*(from|import)\s+sparkweave(\.|\s|$)")
    offenders: list[str] = []

    for path in package_root.rglob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if direct_import.match(line):
                offenders.append(f"{path.relative_to(package_root.parent)}:{line_no}: {line.strip()}")

    assert offenders == []


def test_legacy_source_tree_is_not_present() -> None:
    project_root = Path(__file__).resolve().parents[2]

    assert not (project_root / "sparkweave").exists()


def test_launch_configs_do_not_mount_copy_or_watch_legacy_package() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dev_compose = (project_root / "docker-compose.dev.yml").read_text(encoding="utf-8")
    dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")
    ci_workflow = (project_root / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )

    assert "./sparkweave:/app/sparkweave" in dev_compose
    assert "./sparkweave:/app/sparkweave" not in dev_compose
    assert "COPY sparkweave/ ./sparkweave/" in dockerfile
    assert "COPY sparkweave/ ./sparkweave/" not in dockerfile
    assert '"sparkweave/**"' in ci_workflow
    assert '"sparkweave/**"' not in ci_workflow
    assert "mv sparkweave _sparkweave_disabled_for_ng_test" in ci_workflow


def test_python_package_discovery_excludes_legacy_package() -> None:
    project_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    package_find = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert package_find["include"] == ["sparkweave*", "sparkweave_cli*"]
    assert "sparkweave*" not in package_find["include"]

