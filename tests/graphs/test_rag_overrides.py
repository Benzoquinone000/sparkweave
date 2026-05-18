from __future__ import annotations

from sparkweave.graphs.rag_overrides import RAG_OVERRIDE_KEYS, apply_rag_overrides
from sparkweave.services.validation import ChatRequestConfig, DeepSolveRequestConfig


def test_rag_override_keys_are_valid_runtime_config_fields() -> None:
    chat_fields = set(ChatRequestConfig.model_fields)
    deep_solve_fields = set(DeepSolveRequestConfig.model_fields)

    assert set(RAG_OVERRIDE_KEYS).issubset(chat_fields)
    assert set(RAG_OVERRIDE_KEYS).issubset(deep_solve_fields)


def test_apply_rag_overrides_preserves_explicit_tool_args_and_skips_empty_values() -> None:
    args = {"query": "MP model", "top_k": 3}
    apply_rag_overrides(
        args,
        {
            "top_k": 8,
            "agentic_max_context_chars": 5000,
            "agentic_max_sources": 8,
            "agentic_min_score": "",
        },
    )

    assert args == {
        "query": "MP model",
        "top_k": 3,
        "agentic_max_context_chars": 5000,
        "agentic_max_sources": 8,
    }
