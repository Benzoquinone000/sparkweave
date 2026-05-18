from __future__ import annotations

import importlib
import logging
from pathlib import Path
import sys
import types
from types import SimpleNamespace
import zipfile

import pytest


def _load_milvus_module(monkeypatch):
    fake_core = types.ModuleType("llama_index.core")
    fake_core.Settings = SimpleNamespace(embed_model=None)
    fake_core.StorageContext = SimpleNamespace(from_defaults=lambda **kwargs: kwargs)
    fake_core.VectorStoreIndex = object
    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", fake_core)

    fake_llamaindex = types.ModuleType("sparkweave.services.rag_support.pipelines.llamaindex")
    fake_llamaindex.DEFAULT_KB_BASE_DIR = "data/knowledge_bases"
    fake_llamaindex.CustomEmbedding = type("CustomEmbedding", (), {})
    fake_llamaindex.LlamaIndexPipeline = type("LlamaIndexPipeline", (), {})
    monkeypatch.setitem(
        sys.modules,
        "sparkweave.services.rag_support.pipelines.llamaindex",
        fake_llamaindex,
    )

    module_name = "sparkweave.services.rag_support.pipelines.milvus"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _new_pipeline(module, tmp_path: Path):
    pipeline = module.MilvusPipeline.__new__(module.MilvusPipeline)
    pipeline.kb_base_dir = str(tmp_path)
    pipeline.logger = logging.getLogger("test.milvus.pipeline")
    return pipeline


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


def test_vector_store_kwargs_stay_dense_by_default(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=8, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
        }.get(name, default),
    )
    pipeline = _new_pipeline(module, tmp_path)

    kwargs = pipeline._vector_store_kwargs("demo", overwrite=True)

    assert kwargs["uri"] == "http://localhost:19530"
    assert kwargs["dim"] == 8
    assert kwargs["overwrite"] is True
    assert "enable_sparse" not in kwargs
    assert "hybrid_ranker" not in kwargs


def test_vector_store_kwargs_enable_hybrid_rrf(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=8, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
            "MILVUS_HYBRID_RANKER": "RRFRanker",
            "MILVUS_HYBRID_RRF_K": "72",
        }.get(name, default),
    )
    pipeline = _new_pipeline(module, tmp_path)

    kwargs = pipeline._vector_store_kwargs("demo", overwrite=False, retrieval_mode="hybrid")

    assert kwargs["enable_sparse"] is True
    assert kwargs["hybrid_ranker"] == "RRFRanker"
    assert kwargs["hybrid_ranker_params"] == {"k": 72}


def test_vector_store_kwargs_enable_weighted_hybrid(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=8, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
            "MILVUS_HYBRID_RANKER": "weighted",
            "MILVUS_DENSE_WEIGHT": "1.2",
            "MILVUS_SPARSE_WEIGHT": "0.7",
        }.get(name, default),
    )
    pipeline = _new_pipeline(module, tmp_path)

    kwargs = pipeline._vector_store_kwargs("demo", overwrite=False, retrieval_mode="hybrid")

    assert kwargs["hybrid_ranker"] == "WeightedRanker"
    assert kwargs["hybrid_ranker_params"] == {"weights": [1.2, 0.7]}


def test_vector_store_kwargs_allow_search_time_weight_overrides(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=8, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
            "MILVUS_HYBRID_RANKER": "RRFRanker",
        }.get(name, default),
    )
    pipeline = _new_pipeline(module, tmp_path)

    kwargs = pipeline._vector_store_kwargs(
        "demo",
        overwrite=False,
        retrieval_mode="hybrid",
        hybrid_ranker="weighted",
        dense_weight=0.7,
        sparse_weight=1.2,
    )

    assert kwargs["hybrid_ranker"] == "WeightedRanker"
    assert kwargs["hybrid_ranker_params"] == {"weights": [0.7, 1.2]}


def test_marker_retrieval_mode_is_backward_compatible(monkeypatch) -> None:
    module = _load_milvus_module(monkeypatch)

    assert module.MilvusPipeline._marker_retrieval_mode({}) == "dense"
    assert module.MilvusPipeline._marker_retrieval_mode({"retrieval_mode": "hybrid"}) == "hybrid"
    assert module.MilvusPipeline._marker_retrieval_mode({"enable_sparse": True}) == "hybrid"


def test_resolve_retrieval_mode_preserves_explicit_dense(monkeypatch) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(module, "_env", lambda _name, default="": default)

    assert module._resolve_retrieval_mode("dense", default="hybrid") == "dense"
    assert module._resolve_retrieval_mode("vector", default="hybrid") == "dense"
    assert module._resolve_retrieval_mode(None, default="hybrid") == "hybrid"


def test_write_marker_records_vector_count(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=8, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
        }.get(name, default),
    )
    pipeline = _new_pipeline(module, tmp_path)

    pipeline._write_marker("demo", document_count=2, retrieval_mode="dense", vector_count=17)

    import json

    marker = json.loads((tmp_path / "demo" / "milvus_storage" / "metadata.json").read_text(encoding="utf-8"))
    assert marker["schema_version"] == 1
    assert marker["kb_name"] == "demo"
    assert marker["collection_prefix"] == "sparkweave"
    assert marker["similarity_metric"] == "IP"
    assert marker["chunk_size"] == 512
    assert marker["chunk_overlap"] == 50
    assert marker["created_by"] == "sparkweave.rag.milvus"
    assert marker["document_count"] == 2
    assert marker["vector_count"] == 17
    assert marker["collection_name"] == pipeline._collection_name("demo")


def test_http_docx_extraction_and_structured_chunks(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    docx = tmp_path / "notes.docx"
    _write_docx(
        docx,
        [
            "Chapter 1 Gradient Descent",
            "Gradient descent updates parameters along the negative gradient.",
            "1.1 Learning Rate",
            "The learning rate controls step size.",
        ],
    )

    text = pipeline._extract_docx_text(docx)
    documents = [
        module._LoadedDocument(
            text=text,
            metadata={"file_name": "notes.docx", "document_id": "doc-1"},
            document_id="doc-1",
        )
    ]
    pipeline.chunk_size = 120
    pipeline.chunk_overlap = 10

    chunks = pipeline._split_http_documents(documents)

    assert "Gradient Descent" in text
    assert len(chunks) >= 2
    assert chunks[0].metadata["section_title"] == "Chapter 1 Gradient Descent"
    assert any(chunk.metadata.get("section_title") == "Learning Rate" for chunk in chunks)


def test_pdf_page_markers_become_chunk_metadata(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    documents = [
        module._LoadedDocument(
            text="[[sparkweave-page:3]]\n# Loss Function\nMean squared error notes.",
            metadata={"file_name": "course.pdf", "document_id": "doc-1"},
            document_id="doc-1",
        )
    ]
    pipeline.chunk_size = 200
    pipeline.chunk_overlap = 20

    chunks = pipeline._split_http_documents(documents)

    assert chunks[0].metadata["page_label"] == "3"
    assert chunks[0].metadata["section_title"] == "Loss Function"
    assert "sparkweave-page" not in chunks[0].text


def test_http_chunking_recursively_prefers_semantic_boundaries(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    text = (
        "Intro paragraph explains Alpha.\n\n"
        "Beta block has one sentence. Gamma block has another sentence, with comma detail."
    )

    chunks = pipeline._split_segment_text(text, chunk_size=55, overlap=0)

    assert chunks[0] == "Intro paragraph explains Alpha."
    assert all(len(chunk) <= 55 for chunk in chunks)
    assert any(chunk.endswith("sentence.") for chunk in chunks)
    assert any(chunk.startswith("Gamma block") for chunk in chunks)


def test_http_chunking_falls_back_to_overlapping_character_windows(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)

    chunks = pipeline._split_segment_text("x" * 95, chunk_size=30, overlap=5)

    assert all(len(chunk) <= 30 for chunk in chunks)
    assert chunks == ["x" * 30, "x" * 30, "x" * 30, "x" * 20]


def test_collection_row_count_uses_rest_for_http_uri(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
        }.get(name, default),
    )
    monkeypatch.setattr(module.milvus_http, "collection_row_count", lambda *_args, **_kwargs: 9)
    pipeline = _new_pipeline(module, tmp_path)

    assert pipeline._collection_row_count("demo", retries=1) == 9


def test_ensure_http_collection_rejects_dense_collection_for_hybrid(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=3, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
        }.get(name, default),
    )
    monkeypatch.setattr(module.milvus_http, "has_collection", lambda *_args: True)
    monkeypatch.setattr(
        module.milvus_http,
        "describe_collection",
        lambda *_args: {
            "fields": [
                {"name": "id", "type": "VarChar", "primaryKey": True},
                {"name": "embedding", "type": "FloatVector"},
            ]
        },
    )

    with pytest.raises(RuntimeError, match="BM25 sparse field"):
        pipeline._ensure_http_collection(
            "sparkweave_demo",
            overwrite=False,
            retrieval_mode="hybrid",
        )


@pytest.mark.asyncio
async def test_initialize_http_uses_rest_ingestion_without_llamaindex_indexer(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=3, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
        }.get(name, default),
    )
    monkeypatch.setattr(
        pipeline,
        "_configure_llamaindex_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("LlamaIndex indexer should not be used")),
    )

    async def fake_load_documents(_file_paths):
        return [
            module._LoadedDocument(
                text="gradient descent updates model parameters",
                metadata={
                    "file_name": "course.md",
                    "file_path": str(tmp_path / "demo" / "raw" / "course.md"),
                    "relative_path": "course.md",
                    "document_id": "doc-1",
                    "doc_id": "doc-1",
                    "ref_doc_id": "doc-1",
                },
                document_id="doc-1",
            )
        ]

    class FakeEmbeddingClient:
        async def embed(self, texts, progress_callback=None, input_type=None):
            if progress_callback:
                progress_callback(1, 1)
            assert input_type in {None, "search_document"}
            return [[1.0, 0.0, 0.0] for _ in texts]

    inserted_rows: list[dict] = []
    progress_events: list[tuple[int, int]] = []

    monkeypatch.setattr(pipeline, "_load_http_documents", fake_load_documents)
    monkeypatch.setattr(module, "get_embedding_client", lambda: FakeEmbeddingClient())
    monkeypatch.setattr(module.milvus_http, "has_collection", lambda *_args: False)
    monkeypatch.setattr(module.milvus_http, "create_dense_collection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.milvus_http, "load_collection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.milvus_http, "insert_entities", lambda *_args: inserted_rows.extend(_args[-1]) or len(_args[-1]))
    monkeypatch.setattr(module.milvus_http, "collection_row_count", lambda *_args, **_kwargs: len(inserted_rows))

    result = await pipeline.initialize(
        "demo",
        ["course.md"],
        progress_callback=lambda current, total: progress_events.append((current, total)),
    )

    assert result is True
    assert len(inserted_rows) == 1
    assert inserted_rows[0]["text"] == "gradient descent updates model parameters"
    assert inserted_rows[0]["document_id"] == "doc-1"
    assert progress_events == [(1, 1)]

    import json

    marker = json.loads((tmp_path / "demo" / "milvus_storage" / "metadata.json").read_text(encoding="utf-8"))
    assert marker["provider"] == "milvus"
    assert marker["vector_count"] == 1
    assert marker["document_count"] == 1


@pytest.mark.asyncio
async def test_initialize_http_can_create_true_hybrid_collection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=3, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
            "MILVUS_HYBRID_RANKER": "RRFRanker",
        }.get(name, default),
    )

    async def fake_load_documents(_file_paths):
        return [
            module._LoadedDocument(
                text="gradient descent learning rate",
                metadata={"file_name": "course.md", "document_id": "doc-1"},
                document_id="doc-1",
            )
        ]

    class FakeEmbeddingClient:
        async def embed(self, texts, progress_callback=None, input_type=None):
            return [[1.0, 0.0, 0.0] for _ in texts]

    inserted_rows: list[dict] = []
    created: list[str] = []

    monkeypatch.setattr(pipeline, "_load_http_documents", fake_load_documents)
    monkeypatch.setattr(module, "get_embedding_client", lambda: FakeEmbeddingClient())
    monkeypatch.setattr(module.milvus_http, "has_collection", lambda *_args: False)
    monkeypatch.setattr(
        module.milvus_http,
        "create_hybrid_collection",
        lambda _uri, _token, collection_name, **_kwargs: created.append(collection_name),
    )
    monkeypatch.setattr(
        module.milvus_http,
        "create_dense_collection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dense collection should not be created")),
    )
    monkeypatch.setattr(module.milvus_http, "load_collection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.milvus_http, "insert_entities", lambda *_args: inserted_rows.extend(_args[-1]) or len(_args[-1]))
    monkeypatch.setattr(module.milvus_http, "collection_row_count", lambda *_args, **_kwargs: len(inserted_rows))

    result = await pipeline.initialize("demo", ["course.md"], retrieval_mode="hybrid")

    assert result is True
    assert created == [pipeline._collection_name("demo")]
    assert len(inserted_rows) == 1

    import json

    marker = json.loads((tmp_path / "demo" / "milvus_storage" / "metadata.json").read_text(encoding="utf-8"))
    assert marker["retrieval_mode"] == "hybrid"
    assert marker["enable_sparse"] is True
    assert marker["hybrid_backend"] == "milvus_bm25"
    assert marker["dense_field"] == "embedding"
    assert marker["sparse_field"] == "sparse"


@pytest.mark.asyncio
async def test_add_documents_http_updates_existing_marker(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=3, model="fake-embedding"))
    monkeypatch.setattr(
        module,
        "_env",
        lambda name, default="": {
            "MILVUS_URI": "http://localhost:19530",
            "MILVUS_COLLECTION_PREFIX": "sparkweave",
        }.get(name, default),
    )
    (tmp_path / "demo" / "milvus_storage").mkdir(parents=True)
    pipeline._write_marker("demo", document_count=2, retrieval_mode="dense", vector_count=2)

    async def fake_load_documents(_file_paths):
        return [
            module._LoadedDocument(
                text="new neural network notes",
                metadata={"file_name": "new.md", "document_id": "doc-3"},
                document_id="doc-3",
            )
        ]

    class FakeEmbeddingClient:
        async def embed(self, texts, progress_callback=None, input_type=None):
            return [[0.0, 1.0, 0.0] for _ in texts]

    inserted_rows: list[dict] = []
    monkeypatch.setattr(pipeline, "_load_http_documents", fake_load_documents)
    monkeypatch.setattr(module, "get_embedding_client", lambda: FakeEmbeddingClient())
    monkeypatch.setattr(module.milvus_http, "has_collection", lambda *_args: True)
    monkeypatch.setattr(module.milvus_http, "load_collection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.milvus_http, "insert_entities", lambda *_args: inserted_rows.extend(_args[-1]) or len(_args[-1]))
    monkeypatch.setattr(module.milvus_http, "collection_row_count", lambda *_args, **_kwargs: 3)

    result = await pipeline.add_documents("demo", ["new.md"])

    assert result is True
    assert len(inserted_rows) == 1

    import json

    marker = json.loads((tmp_path / "demo" / "milvus_storage" / "metadata.json").read_text(encoding="utf-8"))
    assert marker["document_count"] == 3
    assert marker["vector_count"] == 3


@pytest.mark.asyncio
async def test_search_reports_legacy_storage_needs_reindex(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    (tmp_path / "legacy-kb" / "llamaindex_storage").mkdir(parents=True)

    result = await pipeline.search("gradient descent", "legacy-kb")

    assert result["success"] is False
    assert result["error"] == "legacy_llamaindex_storage_needs_reindex"
    assert result["needs_reindex"] is True
    assert result["legacy_storage_present"] is True


@pytest.mark.asyncio
async def test_search_reports_missing_milvus_index_for_empty_kb(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)

    result = await pipeline.search("gradient descent", "empty-kb")

    assert result["success"] is False
    assert result["error"] == "no_milvus_collection_metadata"
    assert result["needs_reindex"] is False
    assert result["legacy_storage_present"] is False


@pytest.mark.asyncio
async def test_http_search_limits_final_sources_to_top_k(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(
        pipeline,
        "_read_marker",
        lambda _kb_name: {
            "collection_name": "sparkweave_demo",
            "retrieval_mode": "dense",
            "similarity_metric": "IP",
        },
    )
    monkeypatch.setattr(pipeline, "_milvus_uri", lambda: "http://localhost:19530")
    monkeypatch.setattr(pipeline, "_milvus_token", lambda: None)

    async def _fake_http_search_nodes(**kwargs):
        return [
            SimpleNamespace(
                score=1.0 - index / 10,
                node=SimpleNamespace(
                    text=f"chunk {index}",
                    node_id=f"node-{index}",
                    metadata={"file_name": "course.md", "file_path": "/kb/course.md"},
                ),
            )
            for index in range(kwargs["limit"])
        ]

    monkeypatch.setattr(pipeline, "_http_search_nodes", _fake_http_search_nodes)

    result = await pipeline.search(
        "gradient descent",
        "demo",
        top_k=2,
        candidate_top_k=5,
        reranker="none",
        max_context_chars=1000,
    )

    assert result["success"] is True
    assert result["transport"] == "milvus_rest"
    assert result["candidate_top_k"] == 5
    assert result["source_count"] == 2
    assert [source["chunk_id"] for source in result["sources"]] == ["node-0", "node-1"]


@pytest.mark.asyncio
async def test_http_hybrid_search_uses_milvus_bm25_hybrid_endpoint(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(
        pipeline,
        "_read_marker",
        lambda _kb_name: {
            "collection_name": "sparkweave_demo",
            "retrieval_mode": "hybrid",
            "enable_sparse": True,
            "similarity_metric": "IP",
        },
    )
    monkeypatch.setattr(pipeline, "_milvus_uri", lambda: "http://localhost:19530")
    monkeypatch.setattr(pipeline, "_milvus_token", lambda: None)

    async def _fake_query_embedding(_query):
        return [0.1, 0.2, 0.3]

    calls: list[dict] = []

    def _fake_hybrid_search(*_args, **kwargs):
        calls.append(kwargs)
        return [
            {
                "id": "node-hybrid",
                "distance": 0.88,
                "text": "gradient descent updates parameters with a learning rate",
                "file_name": "course.md",
                "file_path": "/kb/course.md",
            }
        ]

    monkeypatch.setattr(pipeline, "_query_embedding", _fake_query_embedding)
    monkeypatch.setattr(module.milvus_http, "hybrid_search_entities", _fake_hybrid_search)

    result = await pipeline.search(
        "gradient descent",
        "demo",
        retrieval_mode="hybrid",
        top_k=1,
        candidate_top_k=4,
        reranker="none",
        max_context_chars=1000,
    )

    assert result["retrieval_mode"] == "hybrid"
    assert result["transport"] == "milvus_rest"
    assert result["hybrid_lite_applied"] is False
    assert result["needs_reindex_for_hybrid"] is False
    assert result["sources"][0]["chunk_id"] == "node-hybrid"
    assert calls[0]["dense_vector"] == [0.1, 0.2, 0.3]
    assert calls[0]["query_text"] == "gradient descent"
    assert calls[0]["sparse_field"] == "sparse"


@pytest.mark.asyncio
async def test_http_hybrid_request_uses_hybrid_lite_keyword_rerank(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    monkeypatch.setattr(
        pipeline,
        "_read_marker",
        lambda _kb_name: {
            "collection_name": "sparkweave_demo",
            "retrieval_mode": "dense",
            "similarity_metric": "IP",
        },
    )
    monkeypatch.setattr(pipeline, "_milvus_uri", lambda: "http://localhost:19530")
    monkeypatch.setattr(pipeline, "_milvus_token", lambda: None)

    async def _fake_http_search_nodes(**kwargs):
        del kwargs
        return [
            SimpleNamespace(
                score=0.99,
                node=SimpleNamespace(
                    text="unrelated optimizer notes",
                    node_id="node-a",
                    metadata={"file_name": "course.md", "file_path": "/kb/course.md"},
                ),
            ),
            SimpleNamespace(
                score=0.7,
                node=SimpleNamespace(
                    text="gradient descent updates parameters",
                    node_id="node-b",
                    metadata={"file_name": "course.md", "file_path": "/kb/course.md"},
                ),
            ),
        ]

    monkeypatch.setattr(pipeline, "_http_search_nodes", _fake_http_search_nodes)

    result = await pipeline.search(
        "gradient descent",
        "demo",
        retrieval_mode="hybrid",
        top_k=1,
        candidate_top_k=2,
        reranker="none",
        max_context_chars=1000,
    )

    assert result["retrieval_mode"] == "dense"
    assert result["requested_retrieval_mode"] == "hybrid"
    assert result["hybrid_lite_applied"] is True
    assert result["needs_reindex_for_hybrid"] is True
    assert result["hybrid_fallback_reason"] == "dense_index_requires_reindex_for_true_hybrid"
    assert result["reranker"] == "keyword"
    assert result["sources"][0]["chunk_id"] == "node-b"


@pytest.mark.asyncio
async def test_http_search_failure_returns_readiness_payload(monkeypatch, tmp_path: Path) -> None:
    module = _load_milvus_module(monkeypatch)
    pipeline = _new_pipeline(module, tmp_path)
    (tmp_path / "demo" / "milvus_storage").mkdir(parents=True)
    (tmp_path / "demo" / "milvus_storage" / "metadata.json").write_text(
        """
        {
          "collection_name": "sparkweave_demo",
          "uri": "http://milvus:19530",
          "retrieval_mode": "dense",
          "similarity_metric": "IP",
          "embedding_model": "fake-embedding",
          "embedding_dim": 8,
          "vector_count": 17
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "get_embedding_config", lambda: SimpleNamespace(dim=8, model="fake-embedding"))
    monkeypatch.setattr(pipeline, "_milvus_uri", lambda: "http://localhost:19530")
    monkeypatch.setattr(pipeline, "_milvus_token", lambda: None)

    from sparkweave.services.rag_support import diagnostics

    monkeypatch.setattr(
        diagnostics,
        "_env_value",
        lambda name, default="": {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default),
    )
    monkeypatch.setattr(
        diagnostics,
        "_embedding_snapshot",
        lambda: {"embedding_model": "fake-embedding", "embedding_dim": 8},
    )

    async def _raise_http_failure(**_kwargs):
        raise RuntimeError("Milvus REST /v2/vectordb/entities/search failed: connection reset")

    monkeypatch.setattr(pipeline, "_http_search_nodes", _raise_http_failure)

    result = await pipeline.search("gradient descent", "demo")

    assert result["success"] is False
    assert result["source_count"] == 0
    assert result["error_code"] == "milvus_uri_mismatch"
    assert result["readiness"]["state"] == "error"
    assert result["readiness"]["label"] == "地址不一致"
    assert result["diagnostic"]["uri_mismatch"] is True
    assert "下一步" in result["answer"]
