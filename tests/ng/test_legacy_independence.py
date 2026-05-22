from __future__ import annotations

from pathlib import Path
import tomllib

from scripts import check_ng_replacement


def test_active_tree_has_no_legacy_replacement_violations() -> None:
    assert check_ng_replacement.scan() == []


def test_active_source_tree_and_frontend_are_present() -> None:
    project_root = Path(__file__).resolve().parents[2]

    assert (project_root / "sparkweave").is_dir()
    assert (project_root / "web").is_dir()
    assert not (project_root / "web" / ("." + "next")).exists()


def test_launch_configs_point_at_active_package_and_vite_frontend() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dev_compose = (project_root / "docker-compose.dev.yml").read_text(encoding="utf-8")
    dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")
    ci_workflow = (project_root / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "sparkweave" in dockerfile
    assert "web" in dockerfile
    assert "Vite" in dockerfile
    assert "npm run check:replacement" in ci_workflow
    assert "services: {}" in dev_compose


def test_python_package_discovery_includes_active_package() -> None:
    project_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    package_find = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert package_find["include"] == ["sparkweave*", "sparkweave_cli*"]
