from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "start_docker.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("start_docker", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


start_docker = _load_module()


def test_milvus_only_starts_only_vector_database_services(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []
    endpoint_modes: list[bool] = []

    monkeypatch.setattr(sys, "argv", ["start_docker.py", "--milvus-only"])
    monkeypatch.setattr(start_docker, "_docker_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(start_docker.shutil, "which", lambda name: "docker" if name == "docker" else None)
    monkeypatch.setattr(start_docker, "_ensure_docker_engine", lambda _docker: None)
    monkeypatch.setattr(start_docker, "_ensure_env_file", lambda: None)
    monkeypatch.setattr(
        start_docker,
        "_run",
        lambda command, *, check=True: commands.append(list(command))
        or subprocess.CompletedProcess(command, 0),
    )
    monkeypatch.setattr(
        start_docker,
        "_print_endpoints",
        lambda *, milvus_only=False: endpoint_modes.append(milvus_only),
    )

    start_docker.main()

    assert commands == [
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--remove-orphans",
            "milvus-etcd",
            "milvus-minio",
            "milvus",
        ]
    ]
    assert endpoint_modes == [True]


def test_full_stack_still_builds_sparkweave_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(sys, "argv", ["start_docker.py"])
    monkeypatch.setattr(start_docker, "_docker_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(start_docker.shutil, "which", lambda name: "docker" if name == "docker" else None)
    monkeypatch.setattr(start_docker, "_ensure_docker_engine", lambda _docker: None)
    monkeypatch.setattr(start_docker, "_ensure_env_file", lambda: None)
    monkeypatch.setattr(
        start_docker,
        "_run",
        lambda command, *, check=True: commands.append(list(command))
        or subprocess.CompletedProcess(command, 0),
    )
    monkeypatch.setattr(start_docker, "_print_endpoints", lambda *, milvus_only=False: None)

    start_docker.main()

    assert commands == [["docker", "compose", "up", "-d", "--remove-orphans", "--build"]]


def test_docker_engine_error_explains_how_to_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command == ["docker", "version", "--format", "{{.Server.Version}}"]
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr='open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.',
        )

    monkeypatch.setattr(start_docker.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        start_docker._ensure_docker_engine("docker")

    message = str(exc_info.value)
    assert "Docker Desktop is not running" in message
    assert "python scripts/start_docker.py --milvus-only" in message
    assert "dockerDesktopLinuxEngine" in message
