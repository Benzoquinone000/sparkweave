#!/usr/bin/env python
"""Start the real NG backend and web frontend, then run a small smoke check."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

API_CHECKS = [
    ("system status", "/api/v1/system/status"),
    ("runtime topology", "/api/v1/system/runtime-topology"),
    ("settings", "/api/v1/settings"),
    ("plugins", "/api/v1/plugins/list"),
    ("knowledge bases", "/api/v1/knowledge/list"),
    ("sessions", "/api/v1/sessions?limit=1&offset=0"),
    ("notebooks", "/api/v1/notebook/list"),
    ("memory", "/api/v1/memory"),
    ("guide sessions", "/api/v1/guide/sessions"),
    ("sparkbots", "/api/v1/sparkbot"),
]

FRONTEND_ROUTES = [
    "/chat",
    "/knowledge",
    "/notebook",
    "/memory",
    "/playground",
    "/guide",
    "/co-writer",
    "/agents",
    "/settings",
]


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=80))

    def start_reader(self) -> None:
        def read_output() -> None:
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.lines.append(line.rstrip())

        threading.Thread(target=read_output, daemon=True).start()

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def get_text(url: str, timeout: float = 3.0) -> tuple[int, str]:
    request = Request(url, headers={"Accept": "application/json,text/html"})
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def wait_for(url: str, label: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            status, _body = get_text(url, timeout=2.0)
            if 200 <= status < 500:
                print(f"[runtime-smoke] {label} is reachable at {url}")
                return
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"{label} did not become reachable at {url}: {last_error}")


def spawn(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> ManagedProcess:
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    process = ManagedProcess(name=name, process=subprocess.Popen(command, **kwargs))  # type: ignore[arg-type]
    process.start_reader()
    print(f"[runtime-smoke] started {name} pid={process.process.pid}")
    return process


def check_backend(api_base: str) -> None:
    for label, path in API_CHECKS:
        status, body = get_text(f"{api_base}{path}")
        if not (200 <= status < 300):
            raise RuntimeError(f"{label} returned HTTP {status}")
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{label} did not return JSON") from exc
        print(f"[runtime-smoke] api ok: {label}")


def check_frontend(frontend_base: str) -> None:
    for route in FRONTEND_ROUTES:
        status, body = get_text(f"{frontend_base}{route}")
        if not (200 <= status < 300):
            raise RuntimeError(f"frontend route {route} returned HTTP {status}")
        if "<div id=\"root\"" not in body:
            raise RuntimeError(f"frontend route {route} did not return the Vite app shell")
        print(f"[runtime-smoke] route ok: {route}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-port", type=int, default=0, help="Backend port. Defaults to a free port.")
    parser.add_argument("--frontend-port", type=int, default=0, help="Frontend port. Defaults to a free port.")
    parser.add_argument("--keep-running", action="store_true", help="Leave processes running after checks pass.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend_port = args.backend_port or find_free_port()
    frontend_port = args.frontend_port or find_free_port()
    api_base = f"http://127.0.0.1:{backend_port}"
    frontend_base = f"http://127.0.0.1:{frontend_port}"
    managed: list[ManagedProcess] = []

    legacy_prefix = "deep" + "tutor"
    for legacy_dir in (legacy_prefix, f"{legacy_prefix}_ng", f"{legacy_prefix}_cli"):
        if (ROOT / legacy_dir).exists():
            raise RuntimeError(f"legacy {legacy_dir}/ directory still exists in the repository root")
    if not WEB.exists():
        raise RuntimeError("web/ is missing")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm was not found on PATH")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    frontend_env = env.copy()
    frontend_env["VITE_API_BASE"] = api_base
    frontend_env["FRONTEND_PORT"] = str(frontend_port)

    try:
        managed.append(
            spawn(
                "backend",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "sparkweave.api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                    "--log-level",
                    "warning",
                ],
                ROOT,
                env,
            )
        )
        wait_for(f"{api_base}/api/v1/system/status", "backend")
        check_backend(api_base)

        managed.append(spawn("frontend", [npm, "run", "dev"], WEB, frontend_env))
        wait_for(f"{frontend_base}/chat", "frontend")
        check_frontend(frontend_base)

        print("[runtime-smoke] NG runtime smoke passed.")
        if args.keep_running:
            print(f"[runtime-smoke] backend:  {api_base}")
            print(f"[runtime-smoke] frontend: {frontend_base}")
            while True:
                time.sleep(60)
        return 0
    except Exception:
        print("[runtime-smoke] failure logs:")
        for proc in managed:
            print(f"--- {proc.name} last output ---")
            print("\n".join(proc.lines) or "(no output)")
        raise
    finally:
        if not args.keep_running:
            for proc in reversed(managed):
                proc.stop()


if __name__ == "__main__":
    raise SystemExit(main())

