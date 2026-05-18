from __future__ import annotations

import pytest

from sparkweave.services import config as ng_config
from sparkweave.services import search as search_service


@pytest.mark.asyncio
async def test_web_search_facade_calls_ng_sync_search(monkeypatch):
    calls: dict[str, object] = {}

    def fake_sync_search(**kwargs):
        calls.update(kwargs)
        return {"answer": "ok", "provider": kwargs.get("provider")}

    monkeypatch.setattr(search_service, "_sync_web_search", fake_sync_search)

    result = await search_service.web_search(
        query="langgraph",
        provider="duckduckgo",
        verbose=True,
        max_results=2,
    )

    assert result == {"answer": "ok", "provider": "duckduckgo"}
    assert calls["query"] == "langgraph"
    assert calls["verbose"] is True
    assert calls["max_results"] == 2


def test_search_runtime_config_is_ng_owned(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "SEARCH_PROVIDER=brave",
                "SEARCH_API_KEY=",
            ]
        ),
        encoding="utf-8",
    )
    env_store = ng_config.EnvStore(env_path)
    catalog = {
        "version": 1,
        "services": {
            "llm": {"active_profile_id": None, "active_model_id": None, "profiles": []},
            "embedding": {"active_profile_id": None, "active_model_id": None, "profiles": []},
            "search": {"active_profile_id": None, "profiles": []},
        },
    }

    resolved = ng_config.resolve_search_runtime_config(
        catalog=catalog,
        env_store=env_store,
    )

    assert resolved.requested_provider == "brave"
    assert resolved.provider == "duckduckgo"
    assert resolved.fallback_reason == "brave requires api_key, falling back to duckduckgo"

