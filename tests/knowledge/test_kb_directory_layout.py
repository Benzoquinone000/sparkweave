from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sparkweave.knowledge.add_documents import DocumentAdder, DocumentNameCollisionError
from sparkweave.knowledge.initializer import KnowledgeBaseInitializer
from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.knowledge.progress_tracker import ProgressStage, ProgressTracker


def test_initializer_creates_llamaindex_only_layout(tmp_path: Path) -> None:
    initializer = KnowledgeBaseInitializer(kb_name="demo", base_dir=str(tmp_path))
    initializer.create_directory_structure()

    kb_dir = tmp_path / "demo"
    assert (kb_dir / "raw").exists()
    assert (kb_dir / "llamaindex_storage").exists()
    assert not (kb_dir / "images").exists()
    assert not (kb_dir / "content_list").exists()
    assert not (kb_dir / "rag_storage").exists()


def test_document_adder_does_not_create_compatibility_dirs(tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True, exist_ok=True)
    (kb_dir / "llamaindex_storage").mkdir(parents=True, exist_ok=True)

    DocumentAdder(kb_name="demo", base_dir=str(tmp_path))

    assert (kb_dir / "raw").exists()
    assert (kb_dir / "llamaindex_storage").exists()
    assert not (kb_dir / "images").exists()
    assert not (kb_dir / "content_list").exists()


def test_document_adder_rejects_same_name_different_content(tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo"
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "llamaindex_storage").mkdir(parents=True, exist_ok=True)
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


def test_manager_requires_core_llamaindex_files_for_rag_initialized(tmp_path: Path) -> None:
    manager = KnowledgeBaseManager(base_dir=str(tmp_path))
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    (kb_dir / "llamaindex_storage").mkdir(parents=True)
    manager.update_kb_status("demo", "ready")

    info = manager.get_info("demo")
    assert info["status"] == "unknown"
    assert info["statistics"]["rag_initialized"] is False

    storage_dir = kb_dir / "llamaindex_storage"
    for file_name in ("docstore.json", "index_store.json", "default__vector_store.json"):
        (storage_dir / file_name).write_text("{}", encoding="utf-8")

    info = manager.get_info("demo")
    assert info["status"] == "ready"
    assert info["statistics"]["rag_initialized"] is True


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

