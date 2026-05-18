"""Tests for OpenAICompatibleEmbeddingAdapter._extract_embeddings_from_response."""

from __future__ import annotations

import pytest

from sparkweave.services.embedding_support.adapters.openai_compatible import (
    OpenAICompatibleEmbeddingAdapter,
)

_extract = OpenAICompatibleEmbeddingAdapter._extract_embeddings_from_response

# ---------------------------------------------------------------------------
# Standard OpenAI schema: {"data": [{"embedding": [...]}, ...]}
# ---------------------------------------------------------------------------


class TestOpenAIStandardSchema:
    def test_single_embedding(self) -> None:
        data = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        result = _extract(data)
        assert result == [[0.1, 0.2, 0.3]]

    def test_multiple_embeddings(self) -> None:
        data = {
            "data": [
                {"embedding": [0.1, 0.2]},
                {"embedding": [0.3, 0.4]},
            ]
        }
        result = _extract(data)
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_with_extra_fields(self) -> None:
        data = {
            "object": "list",
            "model": "text-embedding-3-small",
            "data": [
                {"object": "embedding", "index": 0, "embedding": [1.0, 2.0]},
            ],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }
        result = _extract(data)
        assert result == [[1.0, 2.0]]


# ---------------------------------------------------------------------------
# Proxy schema: {"embeddings": [[...], ...]}
# ---------------------------------------------------------------------------


class TestProxySchema:
    def test_nested_lists(self) -> None:
        data = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        result = _extract(data)
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_single_vector(self) -> None:
        data = {"embeddings": [[0.5, 0.6, 0.7]]}
        result = _extract(data)
        assert result == [[0.5, 0.6, 0.7]]


# ---------------------------------------------------------------------------
# Ollama /api/embeddings: {"embedding": [...]}  (singular, flat vector)
# ---------------------------------------------------------------------------


class TestOllamaSingularEmbedding:
    def test_flat_float_vector(self) -> None:
        data = {"embedding": [0.1, 0.2, 0.3, 0.4]}
        result = _extract(data)
        assert result == [[0.1, 0.2, 0.3, 0.4]]

    def test_flat_int_vector(self) -> None:
        data = {"embedding": [1, 2, 3]}
        result = _extract(data)
        assert result == [[1, 2, 3]]

    def test_with_ollama_metadata(self) -> None:
        data = {
            "embedding": [0.01, -0.02, 0.03],
            "model": "nomic-embed-text",
            "total_duration": 123456789,
        }
        result = _extract(data)
        assert result == [[0.01, -0.02, 0.03]]

    def test_high_dimensional(self) -> None:
        vec = [float(i) / 1000 for i in range(768)]
        data = {"embedding": vec}
        result = _extract(data)
        assert len(result) == 1
        assert len(result[0]) == 768
        assert result[0] == vec


# ---------------------------------------------------------------------------
# Nested result/output variants
# ---------------------------------------------------------------------------


class TestNestedSchemas:
    def test_result_data_with_embedding_objects(self) -> None:
        data = {"result": {"data": [{"embedding": [0.1, 0.2]}]}}
        result = _extract(data)
        assert result == [[0.1, 0.2]]

    def test_result_embeddings_nested_lists(self) -> None:
        data = {"result": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}}
        result = _extract(data)
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_output_data_with_embedding_objects(self) -> None:
        data = {"output": {"data": [{"embedding": [0.5, 0.6]}]}}
        result = _extract(data)
        assert result == [[0.5, 0.6]]

    def test_output_embeddings_nested_lists(self) -> None:
        data = {"output": {"embeddings": [[0.7, 0.8]]}}
        result = _extract(data)
        assert result == [[0.7, 0.8]]


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="not a JSON object"):
            _extract([1, 2, 3])

    def test_error_payload_string(self) -> None:
        with pytest.raises(ValueError, match="error payload"):
            _extract({"error": "something went wrong"})

    def test_error_payload_dict_with_message(self) -> None:
        with pytest.raises(ValueError, match="model not found"):
            _extract({"error": {"message": "model not found", "code": 404}})

    def test_error_payload_dict_with_detail(self) -> None:
        with pytest.raises(ValueError, match="invalid key"):
            _extract({"error": {"detail": "invalid key"}})

    def test_unknown_schema_raises_with_keys(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse embeddings"):
            _extract({"foo": "bar", "baz": 42})

    def test_empty_data_list_falls_through(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse embeddings"):
            _extract({"data": []})

    def test_empty_embeddings_list_falls_through(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse embeddings"):
            _extract({"embeddings": []})

    def test_empty_embedding_singular_falls_through(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse embeddings"):
            _extract({"embedding": []})


class TestDimensionParameterPolicy:
    def test_unknown_openai_compatible_model_does_not_send_dimensions(self) -> None:
        assert OpenAICompatibleEmbeddingAdapter._should_send_dimensions("Qwen/Qwen3-Embedding-8B", 4096) is False

    def test_fixed_openai_model_does_not_send_dimensions(self) -> None:
        assert OpenAICompatibleEmbeddingAdapter._should_send_dimensions("text-embedding-ada-002", 1536) is False

    def test_openai_variable_model_sends_only_custom_supported_dimension(self) -> None:
        assert OpenAICompatibleEmbeddingAdapter._should_send_dimensions("text-embedding-3-small", 512) is True
        assert OpenAICompatibleEmbeddingAdapter._should_send_dimensions("text-embedding-3-small", 1536) is False
        assert OpenAICompatibleEmbeddingAdapter._should_send_dimensions("text-embedding-3-small", 1024) is False

