#!/usr/bin/env python
"""Audit the web API surface against sparkweave FastAPI routes.

This is a static guard, not a replacement for e2e tests. It catches accidental
frontend calls to endpoints that do not exist and keeps the redesigned web
workspace aligned with the current sparkweave backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
BACKEND_MAIN = ROOT / "sparkweave" / "api" / "main.py"
BACKEND_ROUTERS = ROOT / "sparkweave" / "api" / "routers"
FRONTEND_API = ROOT / "web" / "src" / "lib" / "api.ts"

ROUTE_DECORATOR_RE = re.compile(
    r"@router\.(get|post|put|patch|delete|websocket)\(\s*[\"']([^\"']*)[\"']"
)
INCLUDE_ROUTER_RE = re.compile(
    r"app\.include_router\(\s*([A-Za-z_][\w]*)\.router\s*,\s*prefix=[\"']([^\"']+)[\"']",
    re.S,
)
FRONTEND_API_LITERAL_RE = re.compile(r"([`'\"])(/api/v1.*?)(?<!\\)\1", re.S)

LEGACY_BACKEND_SHAPES = (
    "/api/v1/chat",
    "/api/v1/solve",
)
LEGACY_BACKEND_PREFIXES = (
    "/api/v1/chat/",
    "/api/v1/solve/",
)

SPARKBOT_DYNAMIC_SHAPES = {
    "/api/v1/sparkbot/recent",
    "/api/v1/sparkbot/channels/schema",
    "/api/v1/sparkbot/souls",
    "/api/v1/sparkbot/souls/{}",
    "/api/v1/sparkbot/{}",
    "/api/v1/sparkbot/{}/destroy",
    "/api/v1/sparkbot/{}/files",
    "/api/v1/sparkbot/{}/files/{}",
    "/api/v1/sparkbot/{}/history",
    "/api/v1/sparkbot/{}/ws",
}


@dataclass(frozen=True)
class Route:
    method: str
    path: str

    @property
    def shape(self) -> str:
        return normalize_route(self.path)


def join_route(prefix: str, suffix: str) -> str:
    if not suffix:
        return prefix.rstrip("/") or "/"
    return f"{prefix.rstrip('/')}/{suffix.lstrip('/')}"


def normalize_route(path: str) -> str:
    path = path.replace("\\n", "")
    path = "".join(line.strip() for line in path.splitlines())
    path = re.sub(r"\$\{\s*query\s*\}", "", path)
    path = re.sub(r"\$\{[^}]+\}", "{}", path)
    path = re.sub(r"\{[^/{}]+\}", "{}", path)
    path = path.split("?", 1)[0]
    path = re.sub(r"/+", "/", path)
    if path.endswith("/") and path != "/":
        path = path[:-1]
    return path


def route_matches(frontend_shape: str, backend_shape: str) -> bool:
    front_parts = frontend_shape.strip("/").split("/")
    back_parts = backend_shape.strip("/").split("/")
    if len(front_parts) != len(back_parts):
        return False
    return all(front == back or front == "{}" or back == "{}" for front, back in zip(front_parts, back_parts))


def load_backend_routes() -> list[Route]:
    main_text = BACKEND_MAIN.read_text(encoding="utf-8")
    prefixes = dict(INCLUDE_ROUTER_RE.findall(main_text))
    routes: list[Route] = []
    for module, prefix in prefixes.items():
        router_file = BACKEND_ROUTERS / f"{module}.py"
        if not router_file.exists():
            raise FileNotFoundError(f"Router module not found: {router_file}")
        text = router_file.read_text(encoding="utf-8")
        for method, suffix in ROUTE_DECORATOR_RE.findall(text):
            routes.append(Route(method=method.upper(), path=join_route(prefix, suffix)))
    return sorted(routes, key=lambda route: (route.path, route.method))


def load_frontend_api_shapes() -> list[str]:
    text = FRONTEND_API.read_text(encoding="utf-8")
    shapes = {normalize_route(match.group(2)) for match in FRONTEND_API_LITERAL_RE.finditer(text)}
    if "SPARKBOT_API_ROOT" in text:
        shapes.update(SPARKBOT_DYNAMIC_SHAPES)
    return sorted(shape for shape in shapes if shape.startswith("/api/v1"))


def is_legacy_backend_route(shape: str) -> bool:
    if shape in LEGACY_BACKEND_SHAPES:
        return True
    return any(shape.startswith(prefix) for prefix in LEGACY_BACKEND_PREFIXES)


def main() -> int:
    backend_routes = load_backend_routes()
    backend_shapes = sorted({route.shape for route in backend_routes})
    frontend_shapes = load_frontend_api_shapes()

    unknown_frontend = [
        shape for shape in frontend_shapes if not any(route_matches(shape, backend) for backend in backend_shapes)
    ]
    uncovered_backend = [
        shape
        for shape in backend_shapes
        if not is_legacy_backend_route(shape)
        and not any(route_matches(frontend, shape) for frontend in frontend_shapes)
    ]

    if unknown_frontend:
        print("[api-contract] web calls endpoints that are not exposed by sparkweave:")
        for shape in unknown_frontend:
            print(f"- {shape}")
        return 1

    if uncovered_backend:
        print("[api-contract] Core sparkweave routes are not represented in web/src/lib/api.ts:")
        for shape in uncovered_backend:
            print(f"- {shape}")
        print("\nLegacy /chat/* and /solve/* compatibility routes are intentionally excluded.")
        return 1

    legacy_count = sum(1 for shape in backend_shapes if is_legacy_backend_route(shape))
    print(
        "[api-contract] web API surface matches sparkweave "
        f"({len(frontend_shapes)} frontend paths, {len(backend_shapes)} backend paths, "
        f"{legacy_count} legacy paths excluded)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

