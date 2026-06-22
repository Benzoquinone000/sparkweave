from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sparkweave.knowledge import document_inventory
from sparkweave.knowledge import manager as manager_module
from sparkweave.knowledge.add_documents import DocumentAdder, DocumentNameCollisionError
from sparkweave.knowledge.initializer import KnowledgeBaseInitializer
from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.knowledge.progress_tracker import ProgressStage, ProgressTracker


def test_initializer_creates_milvus_layout_by_default(tmp_path: Path) -> None:
    initializer = KnowledgeBaseInitializer(kb_name="demo", base_dir=str(tmp_path))
    initializer.create_directory_structure()

    kb_dir = tmp_path / "demo"
    assert (kb_dir / "raw").exists()
    assert (kb_dir / "milvus_storage").exists()
    assert not (kb_dir / "llamaindex_storage").exists()
    assert not (kb_dir / "images").exists()
    assert not (kb_dir / "content_list").exists()
    assert not (kb_dir / "rag_storage").exists()


def test_document_adder_does_not_create_compatibility_dirs_for_milvus(tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True, exist_ok=True)
    (kb_dir / "milvus_storage").mkdir(parents=True, exist_ok=True)
    (kb_dir / "metadata.json").write_text('{"rag_provider":"milvus"}', encoding="utf-8")

    DocumentAdder(kb_name="demo", base_dir=str(tmp_path))

    assert (kb_dir / "raw").exists()
    assert (kb_dir / "milvus_storage").exists()
    assert not (kb_dir / "llamaindex_storage").exists()
    assert not (kb_dir / "images").exists()
    assert not (kb_dir / "content_list").exists()


def test_document_adder_rejects_same_name_different_content(tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo"
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "milvus_storage").mkdir(parents=True, exist_ok=True)
    (kb_dir / "metadata.json").write_text('{"rag_provider":"milvus"}', encoding="utf-8")
    (raw_dir / "notes.txt").write_text("old content", encoding="utf-8")
    source_dir = tmp_path / "uploads"
    source_dir.mkdir()
    source = source_dir / "notes.txt"
    source.write_text("new content", encoding="utf-8")

    adder = DocumentAdder(kb_name="demo", base_dir=str(tmp_path))

    with pytest.raises(DocumentNameCollisionError):
        adder.add_documents([str(source)])

    assert (raw_dir / "notes.txt").read_text(encoding="utf-8") == "old content"


def test_progress_tracker_persists_local_progress_file(tmp_path: Path) -> None:
    tracker = ProgressTracker("demo", tmp_path)

    tracker.update(
        ProgressStage.PROCESSING_DOCUMENTS,
        "Indexing documents",
        current=1,
        total=2,
        file_name="notes.md",
    )

    progress_path = tmp_path / "demo" / ".progress.json"
    assert progress_path.exists()

    progress = tracker.get_progress()
    assert progress is not None
    assert progress["stage"] == "processing_documents"
    assert progress["message"] == "Indexing documents"
    assert progress["progress_percent"] == 50
    assert progress["file_name"] == "notes.md"


def test_manager_requires_milvus_marker_for_rag_initialized(tmp_path: Path) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    (kb_dir / "milvus_storage").mkdir(parents=True)
    manager.update_kb_status("demo", "ready")

    info = manager.get_info("demo")
    assert info["status"] == "unknown"
    assert info["statistics"]["rag_initialized"] is False

    storage_dir = kb_dir / "milvus_storage"
    (storage_dir / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )

    info = manager.get_info("demo")
    assert info["status"] == "ready"
    assert info["statistics"]["rag_initialized"] is True


def test_manager_delete_drops_http_milvus_collection_via_rest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    (kb_dir / "milvus_storage").mkdir()
    (kb_dir / "milvus_storage" / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )
    manager.update_kb_status("demo", "ready")
    dropped: list[str] = []

    monkeypatch.setattr(
        manager_module,
        "_env_value",
        lambda name, default="": "http://localhost:19530" if name == "MILVUS_URI" else default,
    )
    monkeypatch.setattr(manager_module.milvus_http, "has_collection", lambda *_args: True)
    monkeypatch.setattr(
        manager_module.milvus_http,
        "drop_collection",
        lambda _uri, _token, collection_name: dropped.append(collection_name),
    )

    assert manager.delete_knowledge_base("demo", confirm=True) is True
    assert dropped == ["sparkweave_demo"]
    assert not kb_dir.exists()
    assert "demo" not in manager._load_config().get("knowledge_bases", {})


def test_manager_delete_removes_canonical_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sparkweave.services.kb_config import KnowledgeBaseConfigService

    manager = KnowledgeBaseManager(base_dir=str(tmp_path / "knowledge_bases"))
    kb_dir = tmp_path / "knowledge_bases" / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    manager.update_kb_status("demo", "ready")

    service = KnowledgeBaseConfigService(tmp_path / "knowledge_bases" / "kb_config.json")
    service.set_kb_config("demo", {"path": "demo", "rag_provider": "milvus"})
    service.set_default_kb("demo")
    monkeypatch.setattr(
        "sparkweave.services.config.get_kb_config_service",
        lambda: service,
    )

    assert manager.delete_knowledge_base("demo", confirm=True) is True

    service.reload()
    assert "demo" not in service.get_all_configs().get("knowledge_bases", {})
    assert service.get_default_kb() is None


def test_manager_still_accepts_ready_llamaindex_storage(tmp_path: Path) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    storage_dir = kb_dir / "llamaindex_storage"
    storage_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text('{"rag_provider":"llamaindex"}', encoding="utf-8")
    for file_name in ("docstore.json", "index_store.json", "default__vector_store.json"):
        (storage_dir / file_name).write_text("{}", encoding="utf-8")
    manager.update_kb_status("demo", "ready")
    manager.config["knowledge_bases"]["demo"]["rag_provider"] = "llamaindex"
    manager._save_config()

    info = manager.get_info("demo")
    assert info["status"] == "ready"
    assert info["statistics"]["rag_initialized"] is True
    assert info["statistics"]["rag_provider"] == "llamaindex"


def test_initializer_records_hashes_for_initial_raw_documents(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("initial knowledge", encoding="utf-8")
    initializer = KnowledgeBaseInitializer(kb_name="demo", base_dir=str(tmp_path / "kb"))
    initializer.create_directory_structure()
    copied = [Path(item) for item in initializer.copy_documents([str(source)])]

    initializer._record_initial_hashes(copied)

    metadata = json.loads((initializer.kb_dir / "metadata.json").read_text(encoding="utf-8"))
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert metadata["file_hashes"]["source.txt"] == expected


def test_document_inventory_matches_vector_rows_by_document_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True)
    source = raw_dir / "notes.md"
    source.write_text("chunked course notes", encoding="utf-8")
    (kb_dir / "milvus_storage").mkdir()
    (kb_dir / "milvus_storage" / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )
    document_id = document_inventory.document_id_for_path(source, raw_dir)
    row = {
        "id": "chunk-1",
        "text": "Gradient descent chunk",
        "_node_content": json.dumps(
            {
                "metadata": {
                    "document_id": document_id,
                    "file_name": "notes.md",
                    "file_path": str(source),
                },
                "relationships": {
                    "SOURCE": {
                        "node_id": document_id,
                        "metadata": {"file_name": "notes.md", "file_path": str(source)},
                    }
                },
            }
        ),
    }

    monkeypatch.setattr(
        document_inventory,
        "_query_milvus_rows",
        lambda *_args, **_kwargs: ([row], {"available": True, "primary_field": "id", "returned_count": 1}),
    )

    payload = document_inventory.list_documents(manager, "demo", include_vectors=True)

    assert payload["documents"][0]["name"] == "notes.md"
    assert payload["documents"][0]["vector_count"] == 1
    assert payload["documents"][0]["sample_chunks"][0]["id"] == "chunk-1"


def test_document_inventory_matches_vector_rows_by_file_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True)
    source = raw_dir / "notes.md"
    source.write_text("chunked course notes", encoding="utf-8")
    (kb_dir / "milvus_storage").mkdir()
    (kb_dir / "milvus_storage" / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )
    row = {
        "id": "chunk-file",
        "text": "Momentum chunk",
        "metadata": json.dumps({"file_name": "notes.md"}),
    }

    monkeypatch.setattr(
        document_inventory,
        "_query_milvus_rows",
        lambda *_args, **_kwargs: ([row], {"available": True, "primary_field": "id", "returned_count": 1}),
    )

    payload = document_inventory.list_documents(manager, "demo", include_vectors=True)

    assert payload["documents"][0]["vector_count"] == 1
    assert payload["documents"][0]["sample_chunks"][0]["id"] == "chunk-file"


def test_document_inventory_filters_nested_document_chunks_by_stable_ref_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True)
    source = raw_dir / "week1" / "notes.md"
    source.parent.mkdir()
    source.write_text("nested course notes", encoding="utf-8")
    (kb_dir / "milvus_storage").mkdir()
    (kb_dir / "milvus_storage" / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )
    document_id = document_inventory.document_id_for_path(source, raw_dir)
    row = {
        "id": "chunk-nested",
        "text": "Nested document chunk",
        "metadata": json.dumps({"document_id": document_id}),
    }

    monkeypatch.setattr(
        document_inventory,
        "_query_milvus_rows",
        lambda *_args, **_kwargs: ([row], {"available": True, "primary_field": "id", "returned_count": 1}),
    )

    payload = document_inventory.list_vector_chunks(
        manager,
        "demo",
        document_id=document_id,
    )

    assert payload["total"] == 1
    assert payload["chunks"][0]["id"] == "chunk-nested"


def test_document_inventory_reads_vector_rows_through_milvus_rest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True)
    source = raw_dir / "notes.md"
    source.write_text("course notes", encoding="utf-8")
    (kb_dir / "milvus_storage").mkdir()
    (kb_dir / "milvus_storage" / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )
    document_id = document_inventory.document_id_for_path(source, raw_dir)

    monkeypatch.setattr(document_inventory, "_milvus_uri", lambda: "http://localhost:19530")
    monkeypatch.setattr(document_inventory, "_milvus_token", lambda: None)
    monkeypatch.setattr(document_inventory, "_prefer_rest_milvus_client", lambda _uri: True)
    monkeypatch.setattr(
        document_inventory.milvus_http,
        "describe_collection",
        lambda *_args, **_kwargs: {
            "fields": [
                {"name": "id", "primaryKey": True, "type": "VarChar"},
                {"name": "text", "type": "VarChar"},
                {"name": "metadata", "type": "JSON"},
                {"name": "embedding", "type": "FloatVector"},
            ]
        },
    )
    monkeypatch.setattr(document_inventory.milvus_http, "collection_row_count", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        document_inventory.milvus_http,
        "query_entities",
        lambda *_args, **_kwargs: [
            {
                "id": "chunk-rest",
                "text": "Gradient descent from REST",
                "metadata": {"document_id": document_id, "file_name": "notes.md"},
            }
        ],
    )

    payload = document_inventory.list_documents(manager, "demo", include_vectors=True)

    assert payload["vectors_available"] is True
    assert payload["vector_count"] == 1
    assert payload["documents"][0]["vector_count"] == 1
    assert payload["documents"][0]["sample_chunks"][0]["id"] == "chunk-rest"


def test_document_inventory_prefers_rest_for_http_milvus_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_inventory, "_env_value", lambda _name, default="": default)

    assert document_inventory._prefer_rest_milvus_client("http://localhost:19530") is True
    assert document_inventory._prefer_rest_milvus_client("https://milvus.example") is True
    assert document_inventory._prefer_rest_milvus_client("./data/milvus/sparkweave.db") is False


def test_document_inventory_allows_native_milvus_inspection_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        document_inventory,
        "_env_value",
        lambda name, default="": "native" if name == "SPARKWEAVE_MILVUS_INSPECTION_CLIENT" else default,
    )

    assert document_inventory._prefer_rest_milvus_client("http://localhost:19530") is False


def test_document_inventory_deletes_vector_rows_through_milvus_rest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    (kb_dir / "milvus_storage").mkdir()
    (kb_dir / "milvus_storage" / "metadata.json").write_text(
        '{"provider":"milvus","collection_name":"sparkweave_demo"}',
        encoding="utf-8",
    )
    calls: list[str] = []

    monkeypatch.setattr(document_inventory, "_milvus_uri", lambda: "http://localhost:19530")
    monkeypatch.setattr(document_inventory, "_milvus_token", lambda: None)
    monkeypatch.setattr(document_inventory, "_prefer_rest_milvus_client", lambda _uri: True)
    monkeypatch.setattr(
        document_inventory.milvus_http,
        "describe_collection",
        lambda *_args, **_kwargs: {"fields": [{"name": "id", "primaryKey": True}]},
    )
    monkeypatch.setattr(
        document_inventory.milvus_http,
        "delete_entities",
        lambda *_args, filter_expr, **_kwargs: calls.append(filter_expr),
    )

    deleted, error = document_inventory._delete_milvus_ids(manager, "demo", ["chunk-a", "chunk-a", "chunk-b"])

    assert error == ""
    assert deleted == 2
    assert calls == ['id in ["chunk-a", "chunk-b"]']

