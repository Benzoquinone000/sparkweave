from fastapi import FastAPI

from sparkweave.api.app_factory import create_app, root
from sparkweave.api.lifecycle import lifespan, validate_tool_consistency
from sparkweave.api.security import (
    ApiKeyAuthMiddleware,
    _SuppressWsNoise,
    configured_api_keys,
    configured_cors_origin_regex,
    configured_cors_origins,
    suppress_websocket_noise,
)
from sparkweave.api.static_outputs import (
    SafeOutputStaticFiles,
    _safe_header_filename,
)

suppress_websocket_noise()

app = create_app()
path_service = app.state.path_service


__all__ = [
    "ApiKeyAuthMiddleware",
    "FastAPI",
    "SafeOutputStaticFiles",
    "_SuppressWsNoise",
    "_safe_header_filename",
    "app",
    "create_app",
    "configured_api_keys",
    "configured_cors_origin_regex",
    "configured_cors_origins",
    "lifespan",
    "path_service",
    "root",
    "validate_tool_consistency",
]


if __name__ == "__main__":
    from sparkweave.api.run_server import main as run_server_main

    run_server_main()
