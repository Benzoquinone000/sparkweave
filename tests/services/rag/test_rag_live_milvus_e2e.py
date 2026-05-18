from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4
import zipfile

import pytest

from sparkweave.knowledge.add_documents import DocumentAdder
from sparkweave.knowledge.initializer import KnowledgeBaseInitializer
from sparkweave.services.kb_config import KnowledgeBaseConfigService
from sparkweave.services.rag_support import milvus_http
from sparkweave.services.rag_support.factory import reset_pipeline_cache
from sparkweave.services.rag_support.query_planner import RagSubQuery
from sparkweave.services.rag_support.service import RAGService
import sparkweave.services.rag_support.pipelines.milvus as milvus_pipeline
import sparkweave.services.rag_support.query_planner as query_planner_module
import sparkweave.services.rag_support.query_transform as query_transform_module


def _require_live_milvus() -> str:
    if os.getenv("SPARKWEAVE_RUN_LIVE_MILVUS_E2E") != "1":
        pytest.skip("set SPARKWEAVE_RUN_LIVE_MILVUS_E2E=1 to run live Milvus RAG E2E tests")
    uri = os.getenv("SPARKWEAVE_TEST_MILVUS_URI", "http://localhost:19530")
    try:
        milvus_http.list_collections(uri, None)
    except Exception as exc:
        pytest.skip(f"live Milvus REST endpoint is not available at {uri}: {exc}")
    return uri


class _DeterministicEmbeddingClient:
    def __init__(self, dim: int = 16) -> None:
        self.dim = dim
        self.calls: list[dict[str, object]] = []

    async def embed(self, texts, progress_callback=None, input_type=None):
        self.calls.append({"texts": list(texts), "input_type": input_type})
        vectors = [self._vector(text) for text in texts]
        if progress_callback:
            progress_callback(1, 1)
        return vectors

    def _vector(self, text: str) -> list[float]:
        lowered = str(text or "").lower()
        groups = [
            ("gradient", "descent"),
            ("learning rate", "step size", "scheduler"),
            ("momentum", "optimizer"),
            ("pca", "principal component", "principal components"),
            ("svd", "singular value", "singular values"),
            ("dataloader", "data loader"),
            ("train_step", "training step", "batch"),
            ("import error", "traceback", "bug"),
            ("bayes", "probability", "posterior"),
            ("theorem", "derive", "proof"),
            ("chapter", "section", "definition"),
            ("variance", "eigenvector", "matrix"),
        ]
        vector = [0.0] * self.dim
        for index, terms in enumerate(groups):
            if index >= self.dim:
                break
            vector[index] = sum(1.0 for term in terms if term in lowered)
        if not any(vector):
            for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", lowered):
                vector[hash(token) % self.dim] += 0.05
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
        + "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


@pytest.fixture()
def live_milvus_rag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    uri = _require_live_milvus()
    prefix = f"sw_e2e_{uuid4().hex[:8]}"
    client = _DeterministicEmbeddingClient(dim=16)
    env_values = {
        "MILVUS_URI": uri,
        "MILVUS_COLLECTION_PREFIX": prefix,
        "MILVUS_SIMILARITY_METRIC": "IP",
        "MILVUS_OVERWRITE_ON_INIT": "1",
        "RAG_CHUNK_SIZE": "260",
        "RAG_CHUNK_OVERLAP": "30",
        "RAG_RETRIEVAL_PROFILE": "auto",
        "RAG_QUERY_TRANSFORM": "none",
        "RAG_AGENTIC_MODE": "off",
    }

    def fake_env(name: str, default: str = "") -> str:
        return env_values.get(name, default)

    monkeypatch.setattr(milvus_pipeline, "_env", fake_env)
    monkeypatch.setattr(
        milvus_pipeline,
        "get_embedding_config",
        lambda: SimpleNamespace(dim=16, model="deterministic-test-embedding", binding="test"),
    )
    monkeypatch.setattr(milvus_pipeline, "get_embedding_client", lambda: client)
    reset_pipeline_cache()

    yield {
        "base_dir": tmp_path,
        "uri": uri,
        "prefix": prefix,
        "embedding_client": client,
    }

    reset_pipeline_cache()
    try:
        for collection in milvus_http.list_collections(uri, None):
            if str(collection).startswith(prefix):
                milvus_http.drop_collection(uri, None, str(collection))
    except Exception:
        pass


def _write_course_docs(source_dir: Path) -> list[str]:
    source_dir.mkdir(parents=True, exist_ok=True)
    optimization = source_dir / "optimization_notes.md"
    optimization.write_text(
        "\n".join(
            [
                "# Optimization Chapter",
                "Gradient descent updates parameters in the negative gradient direction.",
                "The learning rate controls the step size and stability of training.",
                "Momentum helps the optimizer keep useful velocity across noisy batches.",
            ]
        ),
        encoding="utf-8",
    )
    api_debugging = source_dir / "api_debugging.txt"
    api_debugging.write_text(
        "The DataLoader import error happens before train_step(batch) runs. "
        "Check the package path, batch shape, and traceback for the failing module.",
        encoding="utf-8",
    )
    linear_algebra = source_dir / "linear_algebra.docx"
    _write_docx(
        linear_algebra,
        [
            "Chapter 3 Principal Components",
            "PCA finds principal components that explain maximum variance.",
            "SVD decomposes a matrix into singular values and singular vectors.",
        ],
    )
    derivation = source_dir / "math_derivation.md"
    derivation.write_text(
        "\n".join(
            [
                "# Theorem Proof Notes",
                "To derive x^2 = 4, take square roots and keep both solution branches.",
                "The proof gives x = 2 and x = -2 as the complete solution set.",
            ]
        ),
        encoding="utf-8",
    )
    return [str(optimization), str(api_debugging), str(linear_algebra), str(derivation)]


def _assert_content_contains(result: dict, *phrases: str) -> None:
    content = str(result.get("content") or result.get("answer") or "")
    lowered = content.lower()
    missing = [phrase for phrase in phrases if phrase.lower() not in lowered]
    assert not missing, {"missing": missing, "content": content, "result": result}


def _assert_source_content_contains(result: dict, *phrases: str) -> None:
    source_text = "\n".join(str(source.get("content") or "") for source in result.get("sources") or [])
    lowered = source_text.lower()
    missing = [phrase for phrase in phrases if phrase.lower() not in lowered]
    assert not missing, {"missing": missing, "source_text": source_text, "result": result}


async def _initialize_kb(
    *,
    kb_name: str,
    base_dir: Path,
    source_files: list[str],
    search_mode: str = "hybrid",
) -> dict:
    initializer = KnowledgeBaseInitializer(kb_name=kb_name, base_dir=str(base_dir), rag_provider="milvus")
    initializer.create_directory_structure()
    KnowledgeBaseConfigService(config_path=base_dir / "kb_config.json").set_search_mode(kb_name, search_mode)
    initializer.copy_documents(source_files)
    assert await initializer.process_documents() is True
    marker_path = base_dir / kb_name / "milvus_storage" / "metadata.json"
    return json.loads(marker_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_live_milvus_rag_full_hybrid_lifecycle(live_milvus_rag, monkeypatch: pytest.MonkeyPatch) -> None:
    base_dir = live_milvus_rag["base_dir"]
    source_files = _write_course_docs(base_dir / "source_docs")

    async def fake_hyde(query: str, *, max_chars: int) -> str:
        del max_chars
        return f"{query} PCA SVD principal components gradient descent learning rate"

    async def fake_plan(query: str, *, max_subqueries: int):
        del query, max_subqueries
        return [
            RagSubQuery("PCA SVD principal components", "linear algebra branch"),
            RagSubQuery("gradient descent learning rate", "optimization branch"),
        ]

    monkeypatch.setattr(query_transform_module, "_complete_hypothetical_answer", fake_hyde)
    monkeypatch.setattr(query_planner_module, "_llm_plan_subqueries", fake_plan)

    marker = await _initialize_kb(
        kb_name="hybrid_kb",
        base_dir=base_dir,
        source_files=source_files,
        search_mode="hybrid",
    )

    assert marker["retrieval_mode"] == "hybrid"
    assert marker["enable_sparse"] is True
    assert marker["hybrid_backend"] == "milvus_bm25"
    assert int(marker["vector_count"]) >= 4

    service = RAGService(kb_base_dir=str(base_dir))

    concept = await service.search(
        query="What is gradient descent?",
        kb_name="hybrid_kb",
        top_k=3,
        candidate_top_k=8,
        reranker="keyword",
        max_context_chars=3000,
    )
    assert concept["success"] is True, concept
    assert concept["retrieval_profile"] == "concept"
    assert concept["retrieval_mode"] == "hybrid"
    assert concept["context_pack"]["source_count"] >= 1
    assert concept["context_pack"]["context_chars"] == len(concept["content"])
    _assert_content_contains(concept, "Gradient descent updates parameters", "learning rate")
    _assert_source_content_contains(concept, "Gradient descent updates parameters")
    assert any(source.get("matched_keywords") for source in concept["sources"])
    assert all(source.get("evidence_reason") for source in concept["sources"])

    exact = await service.search(
        query="Which chapter defines principal components?",
        kb_name="hybrid_kb",
        top_k=3,
        candidate_top_k=8,
        reranker="keyword",
        max_context_chars=3000,
    )
    assert exact["success"] is True, exact.get("error_detail") or exact
    assert exact["retrieval_profile"] == "exact"
    assert exact["retrieval_mode"] == "hybrid"
    assert exact["transport"] == "milvus_rest"
    assert exact["source_count"] >= 1
    assert exact["needs_reindex_for_hybrid"] is False
    assert any("linear_algebra.docx" in str(source) for source in exact["sources"])
    assert any("Principal Components" in source.get("content", "") for source in exact["sources"])
    _assert_content_contains(exact, "Chapter 3 Principal Components", "PCA finds principal components")
    _assert_source_content_contains(exact, "Principal Components")

    fast = await service.search(
        query="PCA",
        kb_name="hybrid_kb",
        top_k=2,
        candidate_top_k=5,
        max_context_chars=2000,
    )
    assert fast["success"] is True, fast
    assert fast["retrieval_profile"] == "fast"
    assert fast["retrieval_mode"] == "dense"
    assert any("PCA" in source.get("content", "") for source in fast["sources"])
    _assert_content_contains(fast, "PCA finds principal components")

    code = await service.search(
        query="Explain train_step(batch) import error",
        kb_name="hybrid_kb",
        top_k=2,
        candidate_top_k=8,
        max_context_chars=2000,
    )
    assert code["success"] is True, code
    assert code["retrieval_profile"] == "code"
    assert any("api_debugging.txt" in str(source) for source in code["sources"])
    _assert_content_contains(code, "DataLoader import error", "train_step(batch)")
    _assert_source_content_contains(code, "traceback")

    formula = await service.search(
        query="How do we derive x^2 = 4 theorem proof?",
        kb_name="hybrid_kb",
        top_k=2,
        candidate_top_k=8,
        max_context_chars=2000,
    )
    assert formula["success"] is True, formula
    assert formula["retrieval_profile"] == "formula"
    assert formula["retrieval_mode"] == "hybrid"
    _assert_content_contains(formula, "derive x^2 = 4", "x = -2")
    assert any("math_derivation.md" in str(source) for source in formula["sources"])

    agentic = await service.search(
        query="Compare PCA and SVD and summarize learning rate choices",
        kb_name="hybrid_kb",
        agentic_rag="force",
        query_transform="hyde",
        top_k=2,
        candidate_top_k=8,
        reranker="keyword",
        max_context_chars=4000,
        agentic_min_relevant_coverage_ratio=0.0,
    )
    assert agentic["success"] is True, agentic
    assert agentic["agentic_rag"] is True
    assert agentic["query_plan"]["agentic_enabled"] is True
    assert len(agentic["query_plan"]["subqueries"]) == 2
    assert agentic["agentic_quality"]["status"] == "sufficient"
    assert agentic["agentic_context_pack"]["included_subqueries"] == 2
    _assert_content_contains(
        agentic,
        "### PCA SVD principal components",
        "### gradient descent learning rate",
        "PCA finds principal components",
        "learning rate controls the step size",
    )
    assert any(source.get("subquery") == "PCA SVD principal components" for source in agentic["sources"])
    assert any(
        group.get("query") == "gradient descent learning rate" and group.get("source_count", 0) >= 1
        for group in agentic["agentic_evidence_groups"]
    ), agentic

    new_doc = base_dir / "source_docs" / "probability_notes.md"
    new_doc.write_text(
        "# Probability Chapter\nBayes theorem combines likelihood and prior probability into a posterior.",
        encoding="utf-8",
    )
    adder = DocumentAdder(kb_name="hybrid_kb", base_dir=str(base_dir), rag_provider="milvus")
    staged = adder.add_documents([str(new_doc)])
    processed = await adder.process_new_documents(staged)
    adder.update_metadata(len(processed))
    assert processed

    added = await service.search(
        query="Bayes theorem probability posterior",
        kb_name="hybrid_kb",
        top_k=2,
        candidate_top_k=8,
        max_context_chars=2000,
    )
    assert added["success"] is True, added
    assert any("probability_notes.md" in str(source) for source in added["sources"])
    _assert_content_contains(added, "Bayes theorem", "posterior")


@pytest.mark.asyncio
async def test_live_milvus_dense_kb_reports_hybrid_reindex_need(live_milvus_rag) -> None:
    base_dir = live_milvus_rag["base_dir"]
    source_files = _write_course_docs(base_dir / "dense_source_docs")
    marker = await _initialize_kb(
        kb_name="dense_kb",
        base_dir=base_dir,
        source_files=source_files[:1],
        search_mode="dense",
    )

    assert marker["retrieval_mode"] == "dense"
    assert marker["enable_sparse"] is False

    service = RAGService(kb_base_dir=str(base_dir))
    result = await service.search(
        query="gradient descent learning rate",
        kb_name="dense_kb",
        retrieval_mode="hybrid",
        top_k=2,
        candidate_top_k=5,
        max_context_chars=2000,
    )

    assert result["success"] is True
    assert result["requested_retrieval_mode"] == "hybrid"
    assert result["indexed_retrieval_mode"] == "dense"
    assert result["retrieval_mode"] == "dense"
    assert result["needs_reindex_for_hybrid"] is True
    assert result["hybrid_lite_applied"] is True
    assert result["hybrid_fallback_reason"] == "dense_index_requires_reindex_for_true_hybrid"
    assert result["source_count"] >= 1
    _assert_content_contains(result, "Gradient descent updates parameters", "learning rate")
    assert result["context_pack"]["context_chars"] == len(result["content"])
