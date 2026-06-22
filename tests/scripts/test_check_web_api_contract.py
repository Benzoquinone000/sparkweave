from __future__ import annotations

from scripts.check_web_api_contract import (
    load_frontend_api_files,
    load_frontend_api_shapes,
    load_router_prefixes,
    normalize_route,
)


def test_normalize_route_strips_query_template_suffixes() -> None:
    assert (
        normalize_route("/api/v1/learning-effect/report${suffix}")
        == "/api/v1/learning-effect/report"
    )
    assert (
        normalize_route("/api/v1/knowledge/${encodeURIComponent(kbName)}/vectors${query}")
        == "/api/v1/knowledge/{}/vectors"
    )


def test_normalize_route_preserves_dynamic_path_templates() -> None:
    assert (
        normalize_route("/api/v1/sessions/${encodeURIComponent(sessionId)}/answers")
        == "/api/v1/sessions/{}/answers"
    )


def test_load_router_prefixes_reads_router_registry() -> None:
    prefixes = load_router_prefixes()

    assert prefixes["guide"] == "/api/v1/guide"
    assert prefixes["knowledge"] == "/api/v1/knowledge"
    assert prefixes["unified_ws"] == "/api/v1"


def test_load_frontend_api_files_includes_domain_modules() -> None:
    files = {path.as_posix() for path in load_frontend_api_files()}

    assert any(path.endswith("web/src/lib/api.ts") for path in files)
    assert any(path.endswith("web/src/lib/api/sparkbot.ts") for path in files)


def test_load_frontend_api_shapes_reads_domain_modules() -> None:
    shapes = set(load_frontend_api_shapes())

    assert "/api/v1/sparkbot" in shapes
    assert "/api/v1/sparkbot/{}/skills/upload" in shapes
