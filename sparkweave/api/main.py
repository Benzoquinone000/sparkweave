from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import secrets
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sparkweave.services.paths import get_path_service

logger = logging.getLogger("API")


class _SuppressWsNoise(logging.Filter):
    """Suppress noisy uvicorn logs for WebSocket connection churn."""

    _SUPPRESSED = ("connection open", "connection closed")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(f in msg for f in self._SUPPRESSED)


logging.getLogger("uvicorn.error").addFilter(_SuppressWsNoise())

CONFIG_DRIFT_ERROR_TEMPLATE = (
    "Configuration Drift Detected: Capability tool references {drift} are not "
    "registered in the runtime tool registry. Register the missing tools or "
    "remove the stale tool names from the capability manifests."
)

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
ACTIVE_OUTPUT_SUFFIXES = {".html", ".htm", ".svg", ".xml", ".xhtml", ".js", ".mjs"}


def _split_env_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def _safe_header_filename(value: str, *, fallback: str = "download") -> str:
    filename = Path(value).name
    filename = "".join(
        ch if ch.isprintable() and ch not in {'"', "\\", "\r", "\n"} else "_"
        for ch in filename
    )
    filename = filename.strip(" .\t")[:180]
    return filename or fallback


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


class SafeOutputStaticFiles(StaticFiles):
    """Static file mount that only exposes explicitly whitelisted artifacts."""

    def __init__(self, *args, path_service, **kwargs):
        super().__init__(*args, **kwargs)
        self._path_service = path_service

    async def get_response(self, path: str, scope):
        if not self._path_service.is_public_output_path(path):
            raise HTTPException(status_code=404, detail="Output not found")
        response = await super().get_response(path, scope)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if Path(path).suffix.lower() in ACTIVE_OUTPUT_SUFFIXES:
            filename = _safe_header_filename(path)
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            response.headers.setdefault(
                "Content-Security-Policy",
                "sandbox; default-src 'none'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'unsafe-inline'",
            )
        return response


def validate_tool_consistency():
    """
    Validate that capability manifests only reference tools that are actually
    registered in the runtime ``ToolRegistry``.
    """
    try:
        from sparkweave.app import get_capability_registry
        from sparkweave.tools.registry import get_tool_registry

        capability_registry = get_capability_registry()
        tool_registry = get_tool_registry()
        available_tools = set(tool_registry.list_tools())

        referenced_tools = set()
        for manifest in capability_registry.get_manifests():
            referenced_tools.update(manifest.get("tools_used", []) or [])

        drift = referenced_tools - available_tools
        if drift:
            raise RuntimeError(CONFIG_DRIFT_ERROR_TEMPLATE.format(drift=drift))
    except RuntimeError:
        logger.exception("Configuration validation failed")
        raise
    except Exception:
        logger.exception("Failed to load configuration for validation")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management
    Gracefully handle startup and shutdown events, avoid CancelledError
    """
    # Execute on startup
    logger.info("Application startup")

    # Validate configuration consistency
    validate_tool_consistency()

    # Initialize LLM client early so OPENAI_* env vars are available before
    # any downstream provider integrations start.
    try:
        from sparkweave.services.llm import get_llm_config

        llm_config = get_llm_config()
        logger.info("LLM config initialized: model=%s", llm_config.model)
    except Exception as e:
        logger.warning("Failed to initialize LLM config at startup: %s", e)

    try:
        from sparkweave.services.sparkbot import get_sparkbot_manager

        await get_sparkbot_manager().auto_start_bots()
    except Exception as e:
        logger.warning(f"Failed to auto-start SparkBots: {e}")

    yield

    # Execute on shutdown
    logger.info("Application shutdown")

    # Stop SparkBots
    try:
        from sparkweave.services.sparkbot import get_sparkbot_manager

        await get_sparkbot_manager().stop_all()
        logger.info("SparkBots stopped")
    except Exception as e:
        logger.warning(f"Failed to stop SparkBots: {e}")


app = FastAPI(
    title="SparkWeave API",
    version="0.3.0",
    lifespan=lifespan,
    # Disable automatic trailing slash redirects to prevent protocol downgrade issues
    # when deployed behind HTTPS reverse proxies (e.g., nginx).
    # Without this, FastAPI's 307 redirects may change HTTPS to HTTP.
    # Keep this route lightweight so launch probes can verify the API quickly.
    redirect_slashes=False,
)

# Log only non-200 requests (uvicorn access_log is disabled in run_server.py)
_access_logger = logging.getLogger("uvicorn.access")


@app.middleware("http")
async def selective_access_log(request, call_next):
    response = await call_next(request)
    if response.status_code != 200:
        _access_logger.info(
            '%s - "%s %s HTTP/%s" %d',
            request.client.host if request.client else "-",
            request.method,
            request.url.path,
            request.scope.get("http_version", "1.1"),
            response.status_code,
        )
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


# Configure CORS. Use SPARKWEAVE_CORS_ORIGINS="*" only behind trusted network controls.
_cors_origins = configured_cors_origins()
_cors_origin_regex = configured_cors_origin_regex()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiKeyAuthMiddleware)

# Mount a filtered view over user outputs.
# Only whitelisted artifact paths are readable through the static handler.
path_service = get_path_service()
user_dir = path_service.get_public_outputs_root()

# Initialize user directories on startup
try:
    path_service.ensure_all_directories()
except Exception:
    # Fallback: just create the main directory if it doesn't exist
    if not user_dir.exists():
        user_dir.mkdir(parents=True)

app.mount(
    "/api/outputs",
    SafeOutputStaticFiles(directory=str(user_dir), path_service=path_service),
    name="outputs",
)

# Import routers only after runtime settings are initialized.
# Some router modules load YAML settings at import time.
from sparkweave.api.routers import (
    agent_config,
    chat,
    co_writer,
    dashboard,
    guide,
    guide_v2,
    knowledge,
    learner_profile,
    learning_effect,
    memory,
    notebook,
    plugins_api,
    question,
    question_notebook,
    sessions,
    settings,
    solve,
    sparkbot,
    speech,
    system,
    unified_ws,
    vision_solver,
)

# Include routers
app.include_router(solve.router, prefix="/api/v1", tags=["solve"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(question.router, prefix="/api/v1/question", tags=["question"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(co_writer.router, prefix="/api/v1/co_writer", tags=["co_writer"])
app.include_router(notebook.router, prefix="/api/v1/notebook", tags=["notebook"])
app.include_router(guide.router, prefix="/api/v1/guide", tags=["guide"])
app.include_router(guide_v2.router, prefix="/api/v1/guide/v2", tags=["guide-v2"])
app.include_router(learning_effect.router, prefix="/api/v1/learning-effect", tags=["learning-effect"])
app.include_router(learner_profile.router, prefix="/api/v1/learner-profile", tags=["learner-profile"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(
    question_notebook.router, prefix="/api/v1/question-notebook", tags=["question-notebook"]
)
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
app.include_router(speech.router, prefix="/api/v1/speech", tags=["speech"])
app.include_router(plugins_api.router, prefix="/api/v1/plugins", tags=["plugins"])
app.include_router(agent_config.router, prefix="/api/v1/agent-config", tags=["agent-config"])
app.include_router(vision_solver.router, prefix="/api/v1", tags=["vision-solver"])
app.include_router(sparkbot.router, prefix="/api/v1/sparkbot", tags=["sparkbot"])

# Unified WebSocket endpoint
app.include_router(unified_ws.router, prefix="/api/v1", tags=["unified-ws"])


@app.get("/")
async def root():
    return {"message": "Welcome to SparkWeave API"}


if __name__ == "__main__":
    from sparkweave.api.run_server import main as run_server_main

    run_server_main()


