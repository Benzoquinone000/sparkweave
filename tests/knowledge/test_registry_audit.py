from __future__ import annotations

import json
from pathlib import Path

from sparkweave.knowledge.manager import KnowledgeBaseManager


def test_audit_registry_reports_missing_and_discovered_kbs(tmp_path: Path) -> None:
    base_dir = tmp_path / "knowledge_bases"
    base_dir.mkdir()
    (base_dir / "ready" / "raw").mkdir(parents=True)
    (base_dir / "discovered" / "raw").mkdir(parents=True)
    (base_dir / "kb_config.json").write_text(
        json.dumps(
            {
                "defaults": {"default_kb": "missing", "rag_provider": "milvus"},
                "knowledge_bases": {
                    "ready": {"path": "ready", "rag_provider": "milvus", "status": "ready"},
                    "missing": {"path": "missing", "rag_provider": "milvus", "status": "ready"},
                },
            }
        ),
        encoding="utf-8",
    )

    manager = KnowledgeBaseManager(base_dir=str(base_dir))
    audit = manager.audit_registry()

    assert audit["available_count"] == 1
    assert audit["missing_count"] == 1
    assert audit["discovered_count"] == 1
    assert audit["stale_default"] is True
    assert audit["available"][0]["name"] == "ready"
    assert audit["missing"][0]["name"] == "missing"
    assert audit["discovered"][0]["name"] == "discovered"


def test_prune_missing_configs_removes_only_stale_registry_entries(tmp_path: Path) -> None:
    base_dir = tmp_path / "knowledge_bases"
    base_dir.mkdir()
    (base_dir / "ready" / "raw").mkdir(parents=True)
    config_path = base_dir / "kb_config.json"
    config_path.write_text(
        json.dumps(
            {
                "defaults": {"default_kb": "missing", "rag_provider": "milvus"},
                "knowledge_bases": {
                    "ready": {"path": "ready", "rag_provider": "milvus"},
                    "missing": {"path": "missing", "rag_provider": "milvus"},
                },
            }
        ),
        encoding="utf-8",
    )

    manager = KnowledgeBaseManager(base_dir=str(base_dir))
    dry_run = manager.prune_missing_configs(dry_run=True)
    assert dry_run["removed"] == []
    assert "missing" in json.loads(config_path.read_text(encoding="utf-8"))["knowledge_bases"]

    result = manager.prune_missing_configs()
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))

    assert result["removed"] == ["missing"]
    assert result["removed_count"] == 1
    assert set(on_disk["knowledge_bases"]) == {"ready"}
    assert on_disk["defaults"]["default_kb"] is None
