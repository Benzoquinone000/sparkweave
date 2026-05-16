from __future__ import annotations

import json
from pathlib import Path

from sparkweave.services.rag_support import diagnostics


def test_diagnose_milvus_reads_marker_without_connection(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
            "vector_count": 11,
        }),
        encoding="utf-8",
    )

    def _fake_env(name: str, default: str = "") -> str:
        return {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default)

    monkeypatch.setattr(diagnostics, "_env_value", _fake_env)
    monkeypatch.setattr(diagnostics, "_embedding_snapshot", lambda: {"embedding_model": "test-embedding", "embedding_dim": 8})

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=False)

    assert report["status"] == "configured"
    assert report["provider"] == "milvus"
    assert report["uri"] == "http://localhost:19530"
    assert report["collection_name"] == "sparkweave_demo"
    assert report["marker_present"] is True
    assert report["vector_row_count"] == 11
    assert "11 条向量" in report["readiness"]["summary"]
    assert any(check["name"] == "connection" and check["status"] == "skipped" for check in report["checks"])


def test_diagnose_accepts_legacy_marker_schema(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )
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
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=False)

    assert report["status"] == "configured"
    assert report["marker_schema_version"] is None
    assert any(check["name"] == "marker_schema" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_warns_on_unsupported_marker_schema(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "schema_version": 999,
            "collection_name": "sparkweave_demo",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )
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
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=False)

    assert report["status"] == "warning"
    assert report["marker_schema_version"] == 999
    assert any(check["name"] == "marker_schema" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_milvus_warns_when_marker_missing(monkeypatch, tmp_path: Path) -> None:
    def _fake_env(name: str, default: str = "") -> str:
        return {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default)

    monkeypatch.setattr(diagnostics, "_env_value", _fake_env)
    monkeypatch.setattr(diagnostics, "_embedding_snapshot", lambda: {"embedding_model": "test-embedding", "embedding_dim": 8})

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="missing", check_connection=False)

    assert report["status"] == "warning"
    assert report["marker_present"] is False
    assert report["needs_reindex"] is False
    assert any(check["name"] == "marker" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_milvus_warns_when_legacy_storage_needs_reindex(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "legacy" / "llamaindex_storage").mkdir(parents=True)

    def _fake_env(name: str, default: str = "") -> str:
        return {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default)

    monkeypatch.setattr(diagnostics, "_env_value", _fake_env)
    monkeypatch.setattr(diagnostics, "_embedding_snapshot", lambda: {"embedding_model": "test-embedding", "embedding_dim": 8})

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="legacy", check_connection=False)

    assert report["status"] == "warning"
    assert report["marker_present"] is False
    assert report["legacy_storage_present"] is True
    assert report["needs_reindex"] is True
    assert any(check["name"] == "legacy_storage" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_kb_without_marker_skips_live_connection(monkeypatch, tmp_path: Path) -> None:
    def _fake_env(name: str, default: str = "") -> str:
        return {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default)

    monkeypatch.setattr(diagnostics, "_env_value", _fake_env)
    monkeypatch.setattr(diagnostics, "_embedding_snapshot", lambda: {"embedding_model": "test-embedding", "embedding_dim": 8})

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="missing", check_connection=True)

    assert report["status"] == "warning"
    assert "connection_timeout_seconds" not in report
    assert any(check["name"] == "connection" and check["status"] == "skipped" for check in report["checks"])


def test_diagnose_warns_when_embedding_config_differs_from_marker(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "embedding_model": "indexed-embedding",
            "embedding_dim": 4096,
        }),
        encoding="utf-8",
    )

    def _fake_env(name: str, default: str = "") -> str:
        return {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default)

    monkeypatch.setattr(diagnostics, "_env_value", _fake_env)
    monkeypatch.setattr(
        diagnostics,
        "_embedding_snapshot",
        lambda: {"embedding_model": "current-embedding", "embedding_dim": 2560},
    )

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=False)

    assert report["status"] == "warning"
    assert report["needs_reindex"] is True
    assert report["embedding_mismatch"] is True
    assert report["embedding_model_mismatch"] is True
    assert report["embedding_dim_mismatch"] is True
    assert report["indexed_embedding_dim"] == 4096
    assert report["current_embedding_dim"] == 2560
    assert any(check["name"] == "embedding" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_warns_when_runtime_uri_differs_from_marker(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "uri": "http://milvus:19530",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )

    def _fake_env(name: str, default: str = "") -> str:
        return {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default)

    monkeypatch.setattr(diagnostics, "_env_value", _fake_env)
    monkeypatch.setattr(
        diagnostics,
        "_embedding_snapshot",
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=False)

    assert report["status"] == "warning"
    assert report["uri_mismatch"] is True
    assert report["indexed_uri"] == "http://milvus:19530"
    assert report["uri_mismatch_kind"] == "docker_marker_host_runtime"
    assert report["readiness"]["label"] == "地址不一致"
    assert report["needs_reindex"] is False
    assert any(check["name"] == "milvus_uri" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_uri_mismatch_keeps_specific_readiness_on_connection_error(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "uri": "http://milvus:19530",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )

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
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )

    def _raise_connection_error(*_args, **_kwargs):
        raise RuntimeError("HTTP 502")

    monkeypatch.setattr(diagnostics.milvus_http, "describe_collection", _raise_connection_error)

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=True)

    assert report["status"] == "error"
    assert report["uri_mismatch"] is True
    assert report["readiness"]["state"] == "error"
    assert report["readiness"]["label"] == "地址不一致"
    assert "MILVUS_URI" in report["readiness"]["primary_action"]


def test_diagnose_connection_refused_has_service_not_running_readiness(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "uri": "http://localhost:19530",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )
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
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )
    monkeypatch.setattr(
        diagnostics.milvus_http,
        "describe_collection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("[WinError 10061] refused")),
    )

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=True)

    assert report["status"] == "error"
    assert report["connection_error_kind"] == "connection_refused"
    assert report["milvus_service_running"] is False
    assert report["readiness"]["label"] == "服务未启动"
    assert "start_docker.py --milvus-only" in report["readiness"]["primary_action"]


def test_diagnose_records_proxy_bypass_for_local_milvus(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:10090")
    monkeypatch.setattr(
        diagnostics,
        "_env_value",
        lambda name, default="": {
            "RAG_PROVIDER": "milvus",
            "MILVUS_URI": "http://localhost:19530",
        }.get(name, default),
    )
    monkeypatch.setattr(diagnostics, "_embedding_snapshot", lambda: {"embedding_model": "test-embedding", "embedding_dim": 8})
    monkeypatch.setattr(diagnostics.milvus_http, "list_collections", lambda *_args, **_kwargs: [])

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, check_connection=True)

    assert report["proxy"]["http_proxy_configured"] is True
    assert report["proxy"]["milvus_proxy_bypassed"] is True
    assert any(check["name"] == "proxy" and check["status"] == "ok" for check in report["checks"])


def test_preflight_rag_environment_includes_docker_and_commands(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        diagnostics,
        "diagnose_rag",
        lambda **_kwargs: {
            "status": "error",
            "uri": "http://localhost:19530",
            "readiness": {
                "state": "error",
                "label": "服务未启动",
                "summary": "Milvus 未启动。",
                "primary_action": "启动 Milvus。",
            },
        },
    )
    monkeypatch.setattr(
        diagnostics,
        "_docker_snapshot",
        lambda: {"docker_cli_present": True, "docker_running": False, "error": "Docker is not running"},
    )

    report = diagnostics.preflight_rag_environment(kb_base_dir=tmp_path, kb_name="demo")

    assert report["label"] == "服务未启动"
    assert report["docker"]["docker_running"] is False
    assert any("reindex demo" in command for command in report["recommended_commands"])


def test_diagnose_reads_milvus_row_count_through_rest(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )

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
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )
    monkeypatch.setattr(diagnostics.milvus_http, "describe_collection", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(diagnostics.milvus_http, "collection_row_count", lambda *_args, **_kwargs: 7)

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=True)

    assert report["status"] == "ok"
    assert report["collection_present"] is True
    assert report["vector_row_count"] == 7
    assert report["readiness"]["state"] == "ready"
    assert report["readiness"]["label"] == "检索就绪"
    assert any(check["name"] == "collection" and check["status"] == "ok" for check in report["checks"])


def test_diagnose_warns_when_rest_collection_has_zero_rows(monkeypatch, tmp_path: Path) -> None:
    kb_dir = tmp_path / "demo" / "milvus_storage"
    kb_dir.mkdir(parents=True)
    (kb_dir / "metadata.json").write_text(
        json.dumps({
            "collection_name": "sparkweave_demo",
            "embedding_model": "test-embedding",
            "embedding_dim": 8,
        }),
        encoding="utf-8",
    )

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
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )
    monkeypatch.setattr(diagnostics.milvus_http, "describe_collection", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(diagnostics.milvus_http, "collection_row_count", lambda *_args, **_kwargs: 0)

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="demo", check_connection=True)

    assert report["status"] == "warning"
    assert report["vector_row_count"] == 0
    assert report["readiness"]["state"] == "attention"
    assert report["readiness"]["label"] == "没有向量"
    assert any(check["name"] == "vector_rows" and check["status"] == "warning" for check in report["checks"])


def test_diagnose_local_provider_returns_compatibility_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        diagnostics,
        "_env_value",
        lambda name, default="": "llamaindex" if name == "RAG_PROVIDER" else default,
    )
    monkeypatch.setattr(diagnostics, "_embedding_snapshot", lambda: {"embedding_model": "test-embedding", "embedding_dim": 8})

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, check_connection=True)

    assert report["status"] == "configured"
    assert report["provider"] == "llamaindex"
    assert report["uri"] == "local"
    assert report["readiness"]["state"] == "ready"
    assert report["checks"][0]["name"] == "provider"


def test_diagnose_uses_kb_provider_before_runtime_provider(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "local-kb").mkdir()
    (tmp_path / "kb_config.json").write_text(
        json.dumps({
            "knowledge_bases": {
                "local-kb": {
                    "path": "local-kb",
                    "rag_provider": "llamaindex",
                }
            }
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        diagnostics,
        "_env_value",
        lambda name, default="": "milvus" if name == "RAG_PROVIDER" else default,
    )
    monkeypatch.setattr(
        diagnostics,
        "_embedding_snapshot",
        lambda: {"embedding_model": "test-embedding", "embedding_dim": 8},
    )

    report = diagnostics.diagnose_rag(kb_base_dir=tmp_path, kb_name="local-kb", check_connection=True)

    assert report["provider"] == "llamaindex"
    assert report["provider_source"] == "knowledge_base"
    assert report["uri"] == "local"
