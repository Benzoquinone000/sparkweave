"""Central API router registration for the FastAPI application."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


@dataclass(frozen=True)
class ApiRouterSpec:
    """Metadata needed to mount one router module."""

    module: str
    prefix: str
    tags: tuple[str, ...]


API_ROUTER_SPECS: tuple[ApiRouterSpec, ...] = (
    ApiRouterSpec("solve", "/api/v1", ("solve",)),
    ApiRouterSpec("chat", "/api/v1", ("chat",)),
    ApiRouterSpec("question", "/api/v1/question", ("question",)),
    ApiRouterSpec("knowledge", "/api/v1/knowledge", ("knowledge",)),
    ApiRouterSpec("dashboard", "/api/v1/dashboard", ("dashboard",)),
    ApiRouterSpec("co_writer", "/api/v1/co_writer", ("co_writer",)),
    ApiRouterSpec("notebook", "/api/v1/notebook", ("notebook",)),
    ApiRouterSpec("guide", "/api/v1/guide", ("guide",)),
    ApiRouterSpec("guide_v2", "/api/v1/guide/v2", ("guide-v2",)),
    ApiRouterSpec("learning_effect", "/api/v1/learning-effect", ("learning-effect",)),
    ApiRouterSpec("learner_profile", "/api/v1/learner-profile", ("learner-profile",)),
    ApiRouterSpec("memory", "/api/v1/memory", ("memory",)),
    ApiRouterSpec("sessions", "/api/v1/sessions", ("sessions",)),
    ApiRouterSpec("question_notebook", "/api/v1/question-notebook", ("question-notebook",)),
    ApiRouterSpec("settings", "/api/v1/settings", ("settings",)),
    ApiRouterSpec("system", "/api/v1/system", ("system",)),
    ApiRouterSpec("speech", "/api/v1/speech", ("speech",)),
    ApiRouterSpec("plugins_api", "/api/v1/plugins", ("plugins",)),
    ApiRouterSpec("agent_config", "/api/v1/agent-config", ("agent-config",)),
    ApiRouterSpec("vision_solver", "/api/v1", ("vision-solver",)),
    ApiRouterSpec("sparkbot", "/api/v1/sparkbot", ("sparkbot",)),
    ApiRouterSpec("unified_ws", "/api/v1", ("unified-ws",)),
)


def include_api_routers(
    app: FastAPI,
    specs: Iterable[ApiRouterSpec] = API_ROUTER_SPECS,
) -> None:
    """Import and mount all configured API routers in a stable order."""

    for spec in specs:
        module = import_module(f"sparkweave.api.routers.{spec.module}")
        app.include_router(module.router, prefix=spec.prefix, tags=list(spec.tags))


__all__ = ["API_ROUTER_SPECS", "ApiRouterSpec", "include_api_routers"]
