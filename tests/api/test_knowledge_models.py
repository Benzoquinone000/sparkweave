from __future__ import annotations

from pydantic import ValidationError
import pytest

from sparkweave.api.routers.knowledge_models import (
    MAX_RAG_EVAL_CASES,
    MAX_RAG_EVAL_STRATEGIES,
    MAX_RAG_QUERY_CHARS,
    RagEvaluationCase,
    RagEvaluationRequest,
    RagEvaluationStrategyRequest,
    RagSearchTestRequest,
)


def test_rag_search_test_rejects_oversized_query() -> None:
    with pytest.raises(ValidationError):
        RagSearchTestRequest(query="x" * (MAX_RAG_QUERY_CHARS + 1))


def test_rag_evaluation_rejects_too_many_cases() -> None:
    cases = [RagEvaluationCase(question=f"Question {index}") for index in range(MAX_RAG_EVAL_CASES + 1)]

    with pytest.raises(ValidationError):
        RagEvaluationRequest(cases=cases)


def test_rag_evaluation_rejects_too_many_strategies() -> None:
    strategies = [
        RagEvaluationStrategyRequest(name=f"strategy_{index}")
        for index in range(MAX_RAG_EVAL_STRATEGIES + 1)
    ]

    with pytest.raises(ValidationError):
        RagEvaluationRequest(cases=[RagEvaluationCase(question="What is covered?")], strategies=strategies)
