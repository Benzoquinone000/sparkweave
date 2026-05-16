"""Factory + tool-wrapper layer tests."""

from __future__ import annotations

import pytest

from sparkweave.services.rag import (
    RAGService,
    get_available_providers,
    get_current_provider,
)
from sparkweave.services.rag_support import factory as rag_factory
from sparkweave.services.rag_support.factory import (
    DEFAULT_PROVIDER,
    LOCAL_PROVIDER,
    get_pipeline,
    list_pipelines,
    normalize_provider_name,
    reset_pipeline_cache,
)


class TestNormalizeProviderName:
    @pytest.mark.parametrize("value", [None, "", "  ", "milvus", "Milvus", "lightrag"])
    def test_defaults_to_milvus(self, value) -> None:
        assert normalize_provider_name(value) == DEFAULT_PROVIDER

    @pytest.mark.parametrize("value", ["llamaindex", "LlamaIndex", "llama_index", "local"])
    def test_keeps_llamaindex_compatibility_provider(self, value) -> None:
        assert normalize_provider_name(value) == LOCAL_PROVIDER


class TestPipelineFactory:
    def test_list_pipelines_includes_milvus_and_local_fallback(self) -> None:
        pipelines = list_pipelines()
        assert isinstance(pipelines, list)
        assert {p["id"] for p in pipelines} == {DEFAULT_PROVIDER, LOCAL_PROVIDER}

    def test_get_pipeline_returns_singleton(self) -> None:
        try:
            first = get_pipeline()
            second = get_pipeline()
        except (ValueError, ImportError) as exc:
            pytest.skip(f"RAG optional dependency missing: {exc}")
        assert first is second

    def test_get_pipeline_normalizes_legacy_names_to_milvus(self) -> None:
        try:
            b = get_pipeline("lightrag")
            c = get_pipeline("nonexistent_xyz")
        except (ValueError, ImportError) as exc:
            pytest.skip(f"RAG optional dependency missing: {exc}")
        assert b is c

    def test_get_pipeline_keeps_local_provider_separate(self) -> None:
        try:
            local = get_pipeline("llamaindex")
            local_again = get_pipeline("local")
        except (ValueError, ImportError) as exc:
            pytest.skip(f"LlamaIndex optional dependency missing: {exc}")
        assert local is local_again

    def test_get_pipeline_does_not_preflight_llamaindex_for_milvus(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        reset_pipeline_cache()
        monkeypatch.setattr(
            rag_factory,
            "_llamaindex_runtime_error",
            lambda: "llamaindex import failed",
        )

        def _fake_build_pipeline(provider: str, **_kwargs):
            return {"provider": provider}

        monkeypatch.setattr(rag_factory, "_build_pipeline", _fake_build_pipeline)

        assert get_pipeline("milvus") == {"provider": DEFAULT_PROVIDER}
        with pytest.raises(ImportError):
            get_pipeline("llamaindex")

    def test_reset_pipeline_cache_clears_cached_instances(self) -> None:
        rag_factory._PIPELINE_CACHE["demo"] = object()

        reset_pipeline_cache()

        assert rag_factory._PIPELINE_CACHE == {}


class TestRAGServiceClassHelpers:
    def test_list_providers_includes_default_and_fallback(self) -> None:
        providers = RAGService.list_providers()
        assert {p["id"] for p in providers} == {DEFAULT_PROVIDER, LOCAL_PROVIDER}

    def test_has_provider_default_true(self) -> None:
        assert RAGService.has_provider(DEFAULT_PROVIDER) is True
        assert RAGService.has_provider(LOCAL_PROVIDER) is True

    def test_has_provider_unknown_false(self) -> None:
        assert RAGService.has_provider("nonexistent") is False
        assert RAGService.has_provider("") is False

    def test_get_current_provider_honors_supported_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAG_PROVIDER", LOCAL_PROVIDER)
        assert get_current_provider() == LOCAL_PROVIDER
        monkeypatch.setenv("RAG_PROVIDER", "lightrag")
        assert get_current_provider() == DEFAULT_PROVIDER
        monkeypatch.delenv("RAG_PROVIDER", raising=False)
        assert get_current_provider() == DEFAULT_PROVIDER


class TestToolLayerExports:
    def test_get_available_providers_matches_class_method(self) -> None:
        assert get_available_providers() == RAGService.list_providers()

