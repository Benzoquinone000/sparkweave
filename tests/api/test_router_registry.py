from __future__ import annotations

from sparkweave.api.router_registry import API_ROUTER_SPECS, ApiRouterSpec


def test_api_router_registry_has_stable_unique_modules() -> None:
    modules = [spec.module for spec in API_ROUTER_SPECS]

    assert len(modules) == len(set(modules))
    assert modules[-1] == "unified_ws"


def test_api_router_registry_keeps_user_task_routes_visible() -> None:
    mounted = {(spec.module, spec.prefix, spec.tags) for spec in API_ROUTER_SPECS}

    assert ("guide", "/api/v1/guide", ("guide",)) in mounted
    assert ("knowledge", "/api/v1/knowledge", ("knowledge",)) in mounted
    assert ("notebook", "/api/v1/notebook", ("notebook",)) in mounted
    assert ("settings", "/api/v1/settings", ("settings",)) in mounted


def test_api_router_spec_is_immutable() -> None:
    assert ApiRouterSpec("chat", "/api/v1", ("chat",)) in API_ROUTER_SPECS
