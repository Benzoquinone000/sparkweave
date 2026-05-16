#!/usr/bin/env python
"""Start SparkWeave with Docker Compose.

This is the preferred runtime launcher for normal use. It starts the full stack:

- SparkWeave backend
- SparkWeave frontend
- Milvus standalone
- Milvus etcd
- Milvus MinIO

The legacy scripts/start_web.py remains available for local development only.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MILVUS_SERVICES = ["milvus-etcd", "milvus-minio", "milvus"]


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=check,
        text=True,
    )


def _docker_compose_command() -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("Docker was not found on PATH. Install Docker Desktop first.")

    probe = subprocess.run(
        [docker, "compose", "version"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return [docker, "compose"]

    legacy = shutil.which("docker-compose")
    if legacy:
        return [legacy]

    raise SystemExit("Docker Compose was not found. Install Docker Desktop with Compose v2.")


def _ensure_docker_engine(docker: str) -> None:
    completed = subprocess.run(
        [docker, "version", "--format", "{{.Server.Version}}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return

    raw_error = (completed.stderr or completed.stdout or "Docker engine is unavailable.").strip()
    raise SystemExit(
        "[start_docker] Docker Desktop is not running or the Docker engine is unavailable.\n"
        "[start_docker] Start Docker Desktop, wait until it says Docker is running, then rerun:\n"
        "  python scripts/start_docker.py --milvus-only\n\n"
        "[start_docker] Raw Docker error:\n"
        f"  {raw_error}"
    )


def _compose_base_command(compose: list[str], *, dev: bool) -> list[str]:
    if not dev:
        return compose
    return [*compose, "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"]


def _ensure_env_file() -> None:
    env_file = PROJECT_ROOT / ".env"
    example = PROJECT_ROOT / ".env.example"
    if env_file.exists() or not example.exists():
        return
    shutil.copyfile(example, env_file)
    print("[start_docker] Created .env from .env.example. Fill API keys before using model features.")


def _env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return default
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return raw_value.strip().strip('"').strip("'") or default
    return default


def _print_endpoints(*, milvus_only: bool = False) -> None:
    backend_port = _env_value("BACKEND_PORT", "8001")
    frontend_port = _env_value("FRONTEND_PORT", "3782")
    milvus_port = _env_value("MILVUS_PORT", "19530")
    milvus_webui_port = _env_value("MILVUS_WEBUI_PORT", "9091")
    print()
    if milvus_only:
        print("[start_docker] Milvus stack is starting for RAG.")
    else:
        print("[start_docker] SparkWeave is starting with Docker Compose.")
        print(f"[start_docker] Frontend:      http://localhost:{frontend_port}")
        print(f"[start_docker] Backend:       http://localhost:{backend_port}")
        print(f"[start_docker] API docs:      http://localhost:{backend_port}/docs")
    print(f"[start_docker] Milvus:        http://localhost:{milvus_port}")
    print(f"[start_docker] Milvus Web UI: http://localhost:{milvus_webui_port}/webui/")
    print()
    print("[start_docker] Useful commands:")
    print("  docker compose ps")
    print("  docker compose logs -f milvus")
    if milvus_only:
        print("  sparkweave kb preflight <kb-name> --no-docker")
        print("  sparkweave kb reindex <kb-name> --provider milvus")
    else:
        print("  docker compose logs -f sparkweave")
        print("  docker compose down")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start SparkWeave via Docker Compose.")
    parser.add_argument("--no-build", action="store_true", help="Skip image build and only start containers.")
    parser.add_argument("--pull", action="store_true", help="Pull newer base/service images before starting.")
    parser.add_argument("--logs", action="store_true", help="Follow sparkweave service logs after startup.")
    parser.add_argument("--down", action="store_true", help="Stop the Docker Compose stack.")
    parser.add_argument("--status", action="store_true", help="Show Docker Compose service status.")
    parser.add_argument("--recreate", action="store_true", help="Force recreate containers to refresh ports/config.")
    parser.add_argument(
        "--milvus-only",
        action="store_true",
        help="Start only Milvus, etcd and MinIO for local RAG verification.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use docker-compose.dev.yml for backend reload and frontend Vite hot reload.",
    )
    args = parser.parse_args()

    compose = _compose_base_command(_docker_compose_command(), dev=args.dev)
    docker = shutil.which("docker")
    if docker:
        _ensure_docker_engine(docker)

    if args.down:
        if args.milvus_only:
            _run([*compose, "stop", *MILVUS_SERVICES])
        else:
            _run([*compose, "down"])
        return

    if args.status:
        command = [*compose, "ps"]
        if args.milvus_only:
            command.extend(MILVUS_SERVICES)
        _run(command, check=False)
        return

    _ensure_env_file()

    if args.pull:
        command = [*compose, "pull"]
        if args.milvus_only:
            command.extend(MILVUS_SERVICES)
        _run(command, check=False)

    command = [*compose, "up", "-d", "--remove-orphans"]
    if not args.no_build and not args.milvus_only:
        command.append("--build")
    if args.recreate:
        command.append("--force-recreate")
    if args.milvus_only:
        command.extend(MILVUS_SERVICES)
    _run(command)
    _print_endpoints(milvus_only=args.milvus_only)

    if args.logs:
        log_services = MILVUS_SERVICES if args.milvus_only else ["sparkweave"]
        _run([*compose, "logs", "-f", *log_services], check=False)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
