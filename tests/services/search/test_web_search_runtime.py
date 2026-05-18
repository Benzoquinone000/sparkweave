"""Tests for SparkBot-style web_search runtime behavior."""

from __future__ import annotations

import pytest

from sparkweave.services.config import ResolvedSearchConfig
from sparkweave.services.search_support import web_search
from sparkweave.services.search_support.types import WebSearchResponse


class _FakeProvider:
    def __init__(self, name: str, supports_answer: bool = False):
        self.name = name
        self.supports_answer = supports_answer

    def search(self, query: str, **kwargs):
        return WebSearchResponse(
            query=query,
            answer="",
            provider=self.name,
            citations=[],
            search_results=[],
        )


def test_web_search_rejects_deprecated_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        "sparkweave.services.search_support._get_web_search_config",
        lambda: {"enabled": True},
    )
    monkeypatch.setattr(
        "sparkweave.services.search_support.resolve_search_runtime_config",
        lambda: ResolvedSearchConfig(
            provider="exa",
            requested_provider="exa",
            unsupported_provider=True,
            deprecated_provider=True,
        ),
    )
    with pytest.raises(ValueError):
        web_search("hello")


def test_web_search_perplexity_missing_key_hard_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "sparkweave.services.search_support._get_web_search_config",
        lambda: {"enabled": True},
    )
    monkeypatch.setattr(
        "sparkweave.services.search_support.resolve_search_runtime_config",
        lambda: ResolvedSearchConfig(
            provider="perplexity",
            requested_provider="perplexity",
            api_key="",
            max_results=5,
            missing_credentials=True,
        ),
    )
    monkeypatch.setattr("sparkweave.services.search_support._resolve_provider_key", lambda _p, _k: "")
    with pytest.raises(ValueError, match="perplexity requires api_key"):
        web_search("hello")


def test_web_search_iflytek_spark_missing_key_hard_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "sparkweave.services.search_support._get_web_search_config",
        lambda: {"enabled": True},
    )
    monkeypatch.setattr(
        "sparkweave.services.search_support.resolve_search_runtime_config",
        lambda: ResolvedSearchConfig(
            provider="iflytek_spark",
            requested_provider="iflytek_spark",
            api_key="",
            max_results=5,
            missing_credentials=True,
        ),
    )
    monkeypatch.setattr("sparkweave.services.search_support._resolve_provider_key", lambda _p, _k: "")
    with pytest.raises(ValueError, match="IFLYTEK_SEARCH_API_PASSWORD"):
        web_search("hello")


def test_web_search_missing_key_falls_back_to_duckduckgo(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_get_provider(name: str, **kwargs):
        captured["provider"] = name
        captured["kwargs"] = kwargs
        return _FakeProvider(name)

    monkeypatch.setattr(
        "sparkweave.services.search_support._get_web_search_config",
        lambda: {"enabled": True},
    )
    monkeypatch.setattr(
        "sparkweave.services.search_support.resolve_search_runtime_config",
        lambda: ResolvedSearchConfig(
            provider="brave",
            requested_provider="brave",
            api_key="",
            base_url="",
            max_results=3,
            proxy="http://127.0.0.1:7890",
        ),
    )
    monkeypatch.setattr("sparkweave.services.search_support._resolve_provider_key", lambda _p, _k: "")
    monkeypatch.setattr("sparkweave.services.search_support.get_provider", _fake_get_provider)
    result = web_search("hello")
    assert captured["provider"] == "duckduckgo"
    assert result["provider"] == "duckduckgo"
    kwargs = captured["kwargs"]
    assert kwargs["proxy"] == "http://127.0.0.1:7890"
    assert kwargs["max_results"] == 3


def test_web_search_searxng_uses_base_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_get_provider(name: str, **kwargs):
        captured["provider"] = name
        captured["kwargs"] = kwargs
        return _FakeProvider(name)

    monkeypatch.setattr(
        "sparkweave.services.search_support._get_web_search_config",
        lambda: {"enabled": True},
    )
    monkeypatch.setattr(
        "sparkweave.services.search_support.resolve_search_runtime_config",
        lambda: ResolvedSearchConfig(
            provider="searxng",
            requested_provider="searxng",
            base_url="https://searx.example.com",
            max_results=4,
        ),
    )
    monkeypatch.setattr("sparkweave.services.search_support.get_provider", _fake_get_provider)
    result = web_search("hello")
    assert captured["provider"] == "searxng"
    assert captured["kwargs"]["base_url"] == "https://searx.example.com"
    assert captured["kwargs"]["max_results"] == 4
    assert result["provider"] == "searxng"


def test_web_search_iflytek_spark_uses_base_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_get_provider(name: str, **kwargs):
        captured["provider"] = name
        captured["kwargs"] = kwargs
        return _FakeProvider(name)

    monkeypatch.setattr(
        "sparkweave.services.search_support._get_web_search_config",
        lambda: {"enabled": True},
    )
    monkeypatch.setattr(
        "sparkweave.services.search_support.resolve_search_runtime_config",
        lambda: ResolvedSearchConfig(
            provider="iflytek_spark",
            requested_provider="iflytek_spark",
            api_key="api-password",
            base_url="https://search-api-open.cn-huabei-1.xf-yun.com/v2/search",
            max_results=6,
        ),
    )
    monkeypatch.setattr("sparkweave.services.search_support.get_provider", _fake_get_provider)
    result = web_search("hello")
    assert captured["provider"] == "iflytek_spark"
    assert captured["kwargs"]["api_key"] == "api-password"
    assert captured["kwargs"]["base_url"] == "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"
    assert captured["kwargs"]["max_results"] == 6
    assert result["provider"] == "iflytek_spark"

