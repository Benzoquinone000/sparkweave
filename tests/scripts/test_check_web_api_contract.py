from __future__ import annotations

from scripts.check_web_api_contract import normalize_route


def test_normalize_route_strips_query_template_suffixes() -> None:
    assert normalize_route("/api/v1/learning-effect/report${suffix}") == "/api/v1/learning-effect/report"
    assert normalize_route("/api/v1/knowledge/${encodeURIComponent(kbName)}/vectors${query}") == "/api/v1/knowledge/{}/vectors"


def test_normalize_route_preserves_dynamic_path_templates() -> None:
    assert normalize_route("/api/v1/sessions/${encodeURIComponent(sessionId)}/answers") == "/api/v1/sessions/{}/answers"
