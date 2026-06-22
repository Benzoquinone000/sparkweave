"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from sparkweave.api.lifecycle import lifespan
from sparkweave.api.router_registry import include_api_routers
from sparkweave.api.security import (
    install_access_log_middleware,
    install_cors_and_auth_middleware,
    install_security_headers_middleware,
)
from sparkweave.api.static_outputs import mount_public_outputs


async def root():
    return {"message": "Welcome to SparkWeave API"}


def create_app() -> FastAPI:
    """Create the configured SparkWeave API app."""
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

    install_access_log_middleware(app)
    install_security_headers_middleware(app)
    install_cors_and_auth_middleware(app)

    app.state.path_service = mount_public_outputs(app)

    # Import routers only after runtime settings are initialized.
    # Some router modules load YAML settings at import time.
    include_api_routers(app)
    app.add_api_route("/", root, methods=["GET"])
    return app


__all__ = ["create_app", "root"]
