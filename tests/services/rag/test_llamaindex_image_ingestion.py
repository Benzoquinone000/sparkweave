"""Image OCR ingestion behavior for the LlamaIndex/Milvus RAG pipeline."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

import pytest


def _load_llamaindex_module(monkeypatch: pytest.MonkeyPatch):
    class FakeDocument:
        def __init__(self, text: str, id_: str | None = None, metadata: dict | None = None):
            self.text = text
            self.id_ = id_
            self.metadata = metadata or {}

    class FakeSettings:
        embed_model = None
        chunk_size = 0
        chunk_overlap = 0

    class FakeStorageContext:
        @staticmethod
        def from_defaults(**kwargs):
            del kwargs
            return FakeStorageContext()

    class FakeVectorStoreIndex:
        @staticmethod
        def from_documents(*args, **kwargs):
            del args, kwargs
            return FakeVectorStoreIndex()

    class FakeBaseEmbedding:
        def __init__(self, **kwargs):
            del kwargs

    fake_core = types.ModuleType("llama_index.core")
    fake_core.Document = FakeDocument
    fake_core.Settings = FakeSettings
    fake_core.StorageContext = FakeStorageContext
    fake_core.VectorStoreIndex = FakeVectorStoreIndex
    fake_core.load_index_from_storage = lambda storage_context: storage_context

    fake_embedding_base = types.ModuleType("llama_index.core.base.embeddings.base")
    fake_embedding_base.BaseEmbedding = FakeBaseEmbedding

    fake_pydantic = types.ModuleType("llama_index.core.bridge.pydantic")
    fake_pydantic.PrivateAttr = lambda default=None: default

    monkeypatch.setitem(sys.modules, "llama_index", types.ModuleType("llama_index"))
    monkeypatch.setitem(sys.modules, "llama_index.core", fake_core)
    monkeypatch.setitem(sys.modules, "llama_index.core.base", types.ModuleType("llama_index.core.base"))
    monkeypatch.setitem(
        sys.modules,
        "llama_index.core.base.embeddings",
        types.ModuleType("llama_index.core.base.embeddings"),
    )
    monkeypatch.setitem(sys.modules, "llama_index.core.base.embeddings.base", fake_embedding_base)
    monkeypatch.setitem(sys.modules, "llama_index.core.bridge", types.ModuleType("llama_index.core.bridge"))
    monkeypatch.setitem(sys.modules, "llama_index.core.bridge.pydantic", fake_pydantic)
    sys.modules.pop("sparkweave.services.rag_support.pipelines.llamaindex", None)
    return importlib.import_module("sparkweave.services.rag_support.pipelines.llamaindex")


@pytest.mark.asyncio
async def test_load_documents_routes_images_through_ocr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamaindex_module = _load_llamaindex_module(monkeypatch)
    monkeypatch.setattr(
        llamaindex_module.LlamaIndexPipeline,
        "_configure_settings",
        lambda self: None,
    )
    monkeypatch.setattr(llamaindex_module, "is_ocr_configured", lambda: True)

    calls: list[tuple[bytes, str]] = []

    def fake_recognize_image(image: bytes, *, encoding: str = "png", config=None) -> str:
        del config
        calls.append((image, encoding))
        return "OCR extracted markdown\n\n梯度下降沿负梯度方向更新参数。"

    monkeypatch.setattr(llamaindex_module, "recognize_image", fake_recognize_image)

    image_path = tmp_path / "scan.jpeg"
    image_path.write_bytes(b"fake-image")

    pipeline = llamaindex_module.LlamaIndexPipeline(kb_base_dir=str(tmp_path))
    documents = await pipeline._load_documents([str(image_path)])

    assert len(documents) == 1
    assert "梯度下降" in documents[0].text
    assert documents[0].metadata["file_name"] == "scan.jpeg"
    assert documents[0].metadata["document_id"]
    assert documents[0].metadata["doc_id"] == documents[0].metadata["document_id"]
    assert documents[0].metadata["ref_doc_id"] == documents[0].metadata["document_id"]
    assert documents[0].metadata["source_type"] == "image_ocr"
    assert calls == [(b"fake-image", "jpeg")]
