"""HTTP, CORS, and API-key security helpers for the FastAPI app."""

from __future__ import annotations

import logging
import os
import secrets
from urllib.parse import parse_qs

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

LOCAL_CORS_ORIGINS = (
    "http://localhost:3782",
    "http://127.0.0.1:3782",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
LOCAL_CORS_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"198\.18\.\d{1,3}\.\d{1,3}"
    r"):\d+$"
)
API_KEY_PROTECTED_PATH_PREFIXES = ("/api/v1", "/api/outputs")


class _SuppressWsNoise(logging.Filter):
    """Suppress noisy uvicorn logs for WebSocket connection churn."""

    _SUPPRESSED = ("connection open", "connection closed")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(f in msg for f in self._SUPPRESSED)


def suppress_websocket_noise() -> None:
    logging.getLogger("uvicorn.error").addFilter(_SuppressWsNoise())


def _split_env_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def configured_cors_origins() -> list[str]:
    """Resolve browser origins allowed to call the API."""
    raw = os.getenv("SPARKWEAVE_CORS_ORIGINS") or os.getenv("CORS_ORIGINS") or ""
    origins = _split_env_list(raw)
    return origins or list(LOCAL_CORS_ORIGINS)


def configured_cors_origin_regex() -> str | None:
    """Resolve the regex for local dev origins with dynamic frontend ports."""
    raw = os.getenv("SPARKWEAVE_CORS_ORIGIN_REGEX") or os.getenv("CORS_ORIGIN_REGEX") or ""
    return raw.strip() or LOCAL_CORS_ORIGIN_REGEX


def configured_api_keys() -> list[str]:
    """Resolve optional API keys for local/private deployments."""
    keys = _split_env_list(os.getenv("SPARKWEAVE_API_KEYS", ""))
    single_key = os.getenv("SPARKWEAVE_API_KEY", "").strip()
    if single_key:
        keys.append(single_key)
    return sorted(set(keys))


def _api_key_from_headers(headers: dict[str, str]) -> str:
    header_key = headers.get("x-sparkweave-api-key", "").strip()
    if header_key:
        return header_key
    authorization = headers.get("authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip()
    return ""


def _api_key_from_scope(scope: dict) -> str:
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    candidate = _api_key_from_headers(headers)
    if candidate:
        return candidate

    query = parse_qs(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=False)
    for name in ("sparkweave_api_key", "api_key"):
        values = query.get(name)
        if values and values[0].strip():
            return values[0].strip()
    return ""


def _is_authorized_scope(scope: dict, api_keys: list[str]) -> bool:
    candidate = _api_key_from_scope(scope)
    return bool(candidate) and any(secrets.compare_digest(candidate, key) for key in api_keys)


class ApiKeyAuthMiddleware:
    """Optional API key protection for both HTTP and WebSocket API routes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        api_keys = configured_api_keys()
        path = scope.get("path", "")
        method = scope.get("method", "")
        should_check = (
            api_keys
            and method != "OPTIONS"
            and any(path.startswith(prefix) for prefix in API_KEY_PROTECTED_PATH_PREFIXES)
        )
        if not should_check or _is_authorized_scope(scope, api_keys):
            await self.app(scope, receive, send)
            return

        if scope_type == "websocket":
            await send({"type": "websocket.close", "code": 1008, "reason": "Unauthorized"})
            return

        response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
        await response(scope, receive, send)


def install_access_log_middleware(app: FastAPI) -> None:
    """Log only non-200 HTTP requests when uvicorn access logging is disabled."""
    access_logger = logging.getLogger("uvicorn.access")

    @app.middleware("http")
    async def selective_access_log(request, call_next):
        response = await call_next(request)
        if response.status_code != 200:
            access_logger.info(
                '%s - "%s %s HTTP/%s" %d',
                request.client.host if request.client else "-",
                request.method,
                request.url.path,
                request.scope.get("http_version", "1.1"),
                response.status_code,
            )
        return response


def install_security_headers_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response


def install_cors_and_auth_middleware(app: FastAPI) -> None:
    """Install CORS and optional API-key middleware."""
    cors_origins = configured_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=configured_cors_origin_regex(),
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiKeyAuthMiddleware)


__all__ = [
    "API_KEY_PROTECTED_PATH_PREFIXES",
    "LOCAL_CORS_ORIGIN_REGEX",
    "LOCAL_CORS_ORIGINS",
    "ApiKeyAuthMiddleware",
    "_SuppressWsNoise",
    "configured_api_keys",
    "configured_cors_origin_regex",
    "configured_cors_origins",
    "install_access_log_middleware",
    "install_cors_and_auth_middleware",
    "install_security_headers_middleware",
    "suppress_websocket_noise",
]
