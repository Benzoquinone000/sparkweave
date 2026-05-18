from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import pytest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - optional dependency in lightweight envs
    FastAPI = None
    TestClient = None

pytestmark = pytest.mark.skipif(FastAPI is None or TestClient is None, reason="fastapi not installed")

if FastAPI is not None and TestClient is not None:
    knowledge_router_module = importlib.import_module("sparkweave.api.routers.knowledge")
    router = knowledge_router_module.router
else:  # pragma: no cover - optional dependency in lightweight envs
    knowledge_router_module = None
    router = None


def _build_app() -> FastAPI:
    if FastAPI is None or router is None:  # pragma: no cover - guarded by pytestmark
        raise RuntimeError("fastapi is not installed")
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/knowledge")
    return app


class _FakeKBManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.base_dir / "kb_config.json"
        self.config: dict[str, dict] = {"knowledge_bases": {}}

    def _load_config(self) -> dict:
        return self.config

    def _save_config(self) -> None:
        pass

    def list_knowledge_bases(self) -> list[str]:
        return sorted(self.config.get("knowledge_bases", {}).keys())

    def update_kb_status(self, name: str, status: str, progress: dict | None = None) -> None:
        entry = self.config.setdefault("knowledge_bases", {}).setdefault(name, {"path": name})
        entry["status"] = status
        entry["progress"] = progress or {}

    def get_knowledge_base_path(self, name: str) -> Path:
        kb_dir = self.base_dir / name
        kb_dir.mkdir(parents=True, exist_ok=True)
        return kb_dir

    def audit_registry(self) -> dict:
        names = sorted(self.config.get("knowledge_bases", {}).keys())
        return {
            "registered_count": len(names),
            "available_count": len(names),
            "missing_count": 0,
            "discovered_count": 0,
            "available": [{"name": name, "path": str(self.base_dir / name)} for name in names],
            "missing": [],
            "discovered": [],
        }

    def prune_missing_configs(self, dry_run: bool = False) -> dict:
        return {
            "status": "dry_run" if dry_run else "success",
            "dry_run": dry_run,
            "removed": [],
            "removed_count": 0,
            "audit": self.audit_registry(),
        }


class _MissingKBDirManager(_FakeKBManager):
    def get_knowledge_base_path(self, name: str) -> Path:
        raise ValueError(f"Knowledge base not found: {name}")

    def get_raw_path(self, name: str) -> Path:
        raise ValueError(f"Knowledge base not found: {name}")


class _FakeInitializer:
    def __init__(self, kb_name: str, base_dir: str, **_kwargs) -> None:
        self.kb_name = kb_name
        self.base_dir = base_dir
        self.kb_dir = Path(base_dir) / kb_name
        self.raw_dir = self.kb_dir / "raw"
        self.progress_tracker = _kwargs.get("progress_tracker")

    def create_directory_structure(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _register_to_config(self) -> None:
        pass


def _upload_payload() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", ("demo.txt", b"hello", "text/plain"))]


def _duplicate_upload_payload() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("files", ("demo.txt", b"hello", "text/plain")),
        ("files", ("demo.txt", b"second", "text/plain")),
    ]


def test_rag_providers_returns_milvus_and_local_fallback() -> None:
    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/rag-providers")

    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload["providers"]} == {"milvus", "llamaindex"}


def test_health_includes_rag_diagnostic(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo"}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", manager.base_dir)
    monkeypatch.setattr(
        knowledge_router_module,
        "diagnose_rag",
        lambda **_kwargs: {"status": "configured", "provider": "milvus", "checks": []},
    )

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["rag"]["provider"] == "milvus"


def test_knowledge_diagnostics_endpoint(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    def _fake_diagnose(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "provider": "milvus", "checks": []}

    monkeypatch.setattr(knowledge_router_module, "diagnose_rag", _fake_diagnose)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/diagnostics?check_connection=false")

    assert response.status_code == 200
    assert response.json()["provider"] == "milvus"
    assert captured["kb_base_dir"] == manager.base_dir
    assert captured["check_connection"] is False


def test_knowledge_preflight_endpoint(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    def _fake_preflight(**kwargs):
        captured.update(kwargs)
        return {"status": "error", "label": "服务未启动", "recommended_commands": []}

    monkeypatch.setattr(knowledge_router_module, "preflight_rag_environment", _fake_preflight)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/preflight?check_connection=false&check_docker=false")

    assert response.status_code == 200
    assert response.json()["label"] == "服务未启动"
    assert captured["kb_base_dir"] == manager.base_dir
    assert captured["check_connection"] is False
    assert captured["check_docker"] is False


def test_knowledge_config_audit_endpoint(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/configs/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["registered_count"] == 1
    assert body["available"][0]["name"] == "demo"


def test_knowledge_config_prune_missing_endpoint(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    class _FakeConfigService:
        def __init__(self) -> None:
            self.reload_called = False

        def reload(self) -> dict:
            self.reload_called = True
            return {}

    service = _FakeConfigService()
    monkeypatch.setattr(knowledge_router_module, "get_kb_config_service", lambda: service)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/knowledge/configs/prune-missing?dry_run=true")

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["removed_count"] == 0
    assert service.reload_called is True


def test_knowledge_base_diagnostics_endpoint(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    def _fake_diagnose(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "provider": "milvus", "kb_name": kwargs.get("kb_name"), "checks": []}

    monkeypatch.setattr(knowledge_router_module, "diagnose_rag", _fake_diagnose)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/demo/diagnostics?check_connection=false")

    assert response.status_code == 200
    body = response.json()
    assert body["kb_name"] == "demo"
    assert captured["kb_base_dir"] == manager.base_dir
    assert captured["kb_name"] == "demo"
    assert captured["check_connection"] is False


def test_knowledge_base_preflight_endpoint(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    def _fake_preflight(**kwargs):
        captured.update(kwargs)
        return {"status": "error", "label": "地址不一致", "kb_name": kwargs.get("kb_name")}

    monkeypatch.setattr(knowledge_router_module, "preflight_rag_environment", _fake_preflight)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/demo/preflight?check_connection=false&check_docker=false")

    assert response.status_code == 200
    assert response.json()["kb_name"] == "demo"
    assert captured["kb_name"] == "demo"
    assert captured["check_docker"] is False


def test_task_status_endpoint_returns_metadata_and_stream_snapshot(tmp_path: Path) -> None:
    task_id = f"kb_status_{tmp_path.name}"
    task_manager = knowledge_router_module.TaskIDManager.get_instance()
    stream_manager = knowledge_router_module.get_task_stream_manager()
    task_manager.update_task_status(task_id, "queued", task_type="kb_test")
    stream_manager.ensure_task(task_id)
    stream_manager.emit_status(task_id, "queued", "Queued for test.")
    stream_manager.emit_log(task_id, "Test log line")

    with TestClient(_build_app()) as client:
        response = client.get(f"/api/v1/knowledge/tasks/{task_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["known"] is True
    assert body["metadata"]["status"] == "queued"
    assert body["stream"]["event_count"] >= 2
    assert body["stream"]["latest_event"]["event"] == "log"


def test_task_status_endpoint_returns_404_for_unknown_task(tmp_path: Path) -> None:
    task_id = f"missing_{tmp_path.name}"

    with TestClient(_build_app()) as client:
        response = client.get(f"/api/v1/knowledge/tasks/{task_id}")

    assert response.status_code == 404


def test_rag_eval_endpoint_uses_kb_default_provider(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    async def _fake_run_evaluation(**kwargs):
        captured.update(kwargs)
        return {
            "summary": [{"strategy": "baseline", "cases": 1, "success_rate": 1.0}],
            "summary_by_query_type": [{"strategy": "baseline", "query_type": "concept", "cases": 1}],
            "baseline_strategy": "baseline",
            "deltas": [],
            "records": [{"case_id": "case-1", "strategy": "baseline", "success": True}],
        }

    monkeypatch.setattr(knowledge_router_module, "run_evaluation", _fake_run_evaluation)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/demo/rag-eval",
            json={
                "cases": [
                    {
                        "id": "case-1",
                        "question": "What is gradient descent?",
                        "query_type": "concept",
                        "expected_keywords": ["gradient"],
                    }
                ],
                "strategies": [{"name": "baseline", "params": {"top_k": 3}}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["kb_name"] == "demo"
    assert body["provider"] == "milvus"
    assert body["case_count"] == 1
    assert body["strategy_count"] == 1
    assert captured["default_kb"] == "demo"
    assert captured["default_provider"] == "milvus"
    assert captured["strategies"][0].params == {"top_k": 3}
    assert captured["cases"][0]["question"] == "What is gradient descent?"
    latest_path = manager.get_knowledge_base_path("demo") / "rag_eval" / "latest.json"
    assert latest_path.exists()

    with TestClient(_build_app()) as client:
        latest_response = client.get("/api/v1/knowledge/demo/rag-eval/latest")

    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["available"] is True
    assert latest["report"]["kb_name"] == "demo"
    assert latest["report"]["summary"][0]["strategy"] == "baseline"


def test_rag_eval_endpoint_accepts_upgrade_preset(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    async def _fake_run_evaluation(**kwargs):
        captured.update(kwargs)
        strategies = kwargs["strategies"]
        return {
            "summary": [{"strategy": strategies[-1].name, "cases": 1, "success_rate": 1.0}],
            "summary_by_query_type": [],
            "baseline_strategy": "baseline",
            "deltas": [],
            "records": [],
        }

    monkeypatch.setattr(knowledge_router_module, "run_evaluation", _fake_run_evaluation)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/demo/rag-eval",
            json={
                "preset": "rag-upgrade",
                "cases": [{"id": "case-1", "question": "What is gradient descent?"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["preset"] == "rag-upgrade"
    assert body["strategy_count"] == 6
    assert [item.name for item in captured["strategies"]] == [
        "baseline",
        "adaptive_policy",
        "wide_context",
        "hybrid_keyword_rerank",
        "hyde_hybrid_rerank",
        "agentic_hyde",
    ]
    assert captured["strategies"][1].params["retrieval_profile"] == "auto"
    assert captured["strategies"][-1].params["agentic_rag"] == "auto"


def test_rag_eval_endpoint_accepts_quick_check_preset(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    async def _fake_run_evaluation(**kwargs):
        captured.update(kwargs)
        strategies = kwargs["strategies"]
        return {
            "summary": [{"strategy": strategies[0].name, "cases": 1, "success_rate": 1.0}],
            "summary_by_query_type": [],
            "baseline_strategy": "baseline",
            "deltas": [],
            "records": [],
        }

    monkeypatch.setattr(knowledge_router_module, "run_evaluation", _fake_run_evaluation)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/demo/rag-eval",
            json={
                "preset": "quick-check",
                "cases": [{"id": "case-1", "question": "What is gradient descent?"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["preset"] == "quick-check"
    assert body["strategy_count"] == 2
    assert body["dataset_profile"]["label_status"] == "smoke_check"
    assert body["dataset_profile"]["keyword_labelled_cases"] == 0
    assert [item.name for item in captured["strategies"]] == ["baseline", "adaptive_policy"]
    assert captured["strategies"][1].params["retrieval_profile"] == "auto"


def test_rag_eval_endpoint_rejects_unknown_preset(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/demo/rag-eval",
            json={
                "preset": "not-real",
                "cases": [{"id": "case-1", "question": "What is gradient descent?"}],
            },
        )

    assert response.status_code == 400
    assert "Unknown RAG eval strategy preset" in response.json()["detail"]


def test_rag_eval_latest_returns_empty_when_missing(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/demo/rag-eval/latest")

    assert response.status_code == 200
    assert response.json() == {"kb_name": "demo", "available": False, "report": None}


def test_readonly_kb_artifacts_return_empty_for_registered_pending_kb(monkeypatch, tmp_path: Path) -> None:
    manager = _MissingKBDirManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["pending"] = {
        "path": "pending",
        "rag_provider": "milvus",
        "status": "initializing",
    }
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    with TestClient(_build_app()) as client:
        documents = client.get("/api/v1/knowledge/pending/documents")
        vectors = client.get("/api/v1/knowledge/pending/vectors?limit=10")
        latest_eval = client.get("/api/v1/knowledge/pending/rag-eval/latest")

    assert documents.status_code == 200
    assert documents.json()["documents"] == []
    assert documents.json()["document_count"] == 0
    assert documents.json()["vectors_available"] is False
    assert vectors.status_code == 200
    assert vectors.json()["chunks"] == []
    assert vectors.json()["available"] is False
    assert latest_eval.status_code == 200
    assert latest_eval.json() == {"kb_name": "pending", "available": False, "report": None}


def test_rag_test_endpoint_uses_kb_default_provider_and_returns_sources(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    class _FakeRAGService:
        def __init__(self, *, kb_base_dir: str, provider: str | None = None) -> None:
            captured["kb_base_dir"] = kb_base_dir
            captured["provider"] = provider

        async def search(self, **kwargs):
            captured["search_kwargs"] = kwargs
            return {
                "success": True,
                "content": "MP 模型由 Warren McCulloch 和 Walter Pitts 提出。",
                "sources": [
                    {
                        "title": "深度学习-chap1-绪论.pdf",
                        "content": "MP 模型是早期神经元模型。",
                        "score": 0.92,
                        "matched_keywords": ["MP", "感知器"],
                        "evidence_reason": "命中问题关键词：MP、感知器",
                    }
                ],
                "source_count": 1,
                "retrieval_profile": "auto",
                "retrieval_mode": "hybrid",
                "requested_retrieval_mode": "hybrid",
                "indexed_retrieval_mode": "hybrid",
                "query_transform": "none",
                "query_transform_applied": False,
                "agentic_rag": True,
                "agentic_quality": {
                    "status": "sufficient",
                    "quality_score": 0.96,
                    "relevant_coverage_ratio": 1.0,
                },
                "agentic_repair": {"strategy": "subquery_repair", "accepted_branches": 1},
                "agentic_explanation": {"decision": "subquery_repair", "schema_version": 1},
                "agentic_context_pack": {"context_chars": 2600, "max_context_chars": 3000},
                "subquery_results": [{"query": "MP模型是什么？", "relevant": True}],
                "query_plan": {"enabled": True},
                "context_pack": {"source_count": 1},
                "readiness": {
                    "state": "ready",
                    "label": "检索就绪",
                    "summary": "知识库已连接并可检索。",
                    "primary_action": "可以在聊天中启用知识库问答。",
                },
            }

    monkeypatch.setattr(knowledge_router_module, "RAGService", _FakeRAGService)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/demo/rag-test",
            json={
                "query": "MP模型是什么？感知器是谁提出的？",
                "retrieval_profile": "auto",
                "retrieval_mode": "hybrid",
                "top_k": 4,
                "candidate_top_k": 9,
                "reranker": "keyword",
                "query_transform": "none",
                "agentic_rag": "force",
                "agentic_max_context_chars": 3000,
                "agentic_max_sources": 8,
                "agentic_min_sources": 2,
                "agentic_min_coverage_ratio": 0.5,
                "agentic_min_relevant_coverage_ratio": 0.67,
                "agentic_min_context_chars": 120,
                "agentic_min_score": 0.2,
                "max_context_chars": 4000,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["kb_name"] == "demo"
    assert body["provider"] == "milvus"
    assert body["source_count"] == 1
    assert body["sources"][0]["matched_keywords"] == ["MP", "感知器"]
    assert body["agentic_rag"] is True
    assert body["agentic_quality"]["quality_score"] == 0.96
    assert body["agentic_explanation"]["decision"] == "subquery_repair"
    assert body["agentic_context_pack"]["max_context_chars"] == 3000
    assert body["subquery_results"][0]["relevant"] is True
    assert body["readiness"]["label"] == "检索就绪"
    assert captured["kb_base_dir"] == str(manager.base_dir)
    assert captured["provider"] == "milvus"
    assert captured["search_kwargs"] == {
        "query": "MP模型是什么？感知器是谁提出的？",
        "kb_name": "demo",
        "top_k": 4,
        "max_context_chars": 4000,
        "candidate_top_k": 9,
        "retrieval_profile": "auto",
        "retrieval_mode": "hybrid",
        "reranker": "keyword",
        "query_transform": "none",
        "agentic_rag": "force",
        "agentic_max_context_chars": 3000,
        "agentic_max_sources": 8,
        "agentic_min_sources": 2,
        "agentic_min_coverage_ratio": 0.5,
        "agentic_min_relevant_coverage_ratio": 0.67,
        "agentic_min_context_chars": 120,
        "agentic_min_score": 0.2,
    }


def test_rag_test_endpoint_accepts_explicit_provider(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    class _FakeRAGService:
        def __init__(self, *, kb_base_dir: str, provider: str | None = None) -> None:
            captured["provider"] = provider

        async def search(self, **kwargs):
            captured["search_kwargs"] = kwargs
            return {"success": True, "content": "local context", "sources": []}

    monkeypatch.setattr(knowledge_router_module, "RAGService", _FakeRAGService)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/demo/rag-test",
            json={"query": "hello", "provider": "llamaindex", "top_k": 2, "candidate_top_k": 1},
        )

    assert response.status_code == 200
    assert response.json()["provider"] == "llamaindex"
    assert captured["provider"] == "llamaindex"
    assert captured["search_kwargs"]["candidate_top_k"] == 2


def test_rag_test_endpoint_rejects_empty_query(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["demo"] = {"path": "demo", "rag_provider": "milvus"}
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/knowledge/demo/rag-test", json={"query": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"


def test_create_kb_does_not_require_llm_precheck(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)
    monkeypatch.setattr(knowledge_router_module, "KnowledgeBaseInitializer", _FakeInitializer)
    monkeypatch.setattr(knowledge_router_module, "get_llm_config", lambda: (_ for _ in ()).throw(RuntimeError("should not be called")), raising=False)

    async def _noop_init_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(knowledge_router_module, "run_initialization_task", _noop_init_task)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", tmp_path / "knowledge_bases")

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/create",
            data={"name": "kb-new", "rag_provider": "llamaindex"},
            files=_upload_payload(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "kb-new"
    assert isinstance(body.get("task_id"), str) and body["task_id"]
    assert manager.config["knowledge_bases"]["kb-new"]["rag_provider"] == "llamaindex"
    assert manager.config["knowledge_bases"]["kb-new"]["needs_reindex"] is False


def test_create_coerces_legacy_provider_to_milvus(monkeypatch, tmp_path: Path) -> None:
    """Legacy provider values normalize to the Milvus default."""
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    async def _noop_init_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(knowledge_router_module, "run_initialization_task", _noop_init_task)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", tmp_path / "knowledge_bases")

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/create",
            data={"name": "kb-legacy", "rag_provider": "lightrag"},
            files=_upload_payload(),
        )

    assert response.status_code == 200
    assert manager.config["knowledge_bases"]["kb-legacy"]["rag_provider"] == "milvus"


def test_upload_returns_409_when_kb_needs_reindex(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["legacy-kb"] = {
        "path": "legacy-kb",
        "rag_provider": "llamaindex",
        "needs_reindex": True,
        "status": "needs_reindex",
    }
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/knowledge/legacy-kb/upload", files=_upload_payload())

    assert response.status_code == 409
    assert "needs reindex" in response.json()["detail"].lower()


def test_reindex_ready_kb_returns_task_id(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["legacy-kb"] = {
        "path": "legacy-kb",
        "rag_provider": "llamaindex",
        "needs_reindex": True,
        "status": "needs_reindex",
    }
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", tmp_path / "knowledge_bases")

    async def _noop_reindex_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(knowledge_router_module, "run_reindex_processing_task", _noop_reindex_task)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/legacy-kb/reindex",
            json={"rag_provider": "lightrag", "backup": False},
        )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("task_id"), str) and body["task_id"]
    assert body["rag_provider"] == "milvus"
    assert manager.config["knowledge_bases"]["legacy-kb"]["rag_provider"] == "milvus"


def test_upload_ready_kb_returns_task_id(monkeypatch, tmp_path: Path) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["ready-kb"] = {
        "path": "ready-kb",
        "rag_provider": "llamaindex",
        "needs_reindex": False,
        "status": "ready",
    }
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", tmp_path / "knowledge_bases")

    async def _noop_upload_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(knowledge_router_module, "run_upload_processing_task", _noop_upload_task)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/knowledge/ready-kb/upload", files=_upload_payload())

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("task_id"), str) and body["task_id"]
    kb_path = tmp_path / "knowledge_bases" / "ready-kb"
    assert not (kb_path / "raw" / "demo.txt").exists()
    staged_files = list((kb_path / ".uploads").glob("*/demo.txt"))
    assert len(staged_files) == 1


def test_upload_duplicate_filename_returns_400_and_rolls_back_staging(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["ready-kb"] = {
        "path": "ready-kb",
        "rag_provider": "llamaindex",
        "needs_reindex": False,
        "status": "ready",
    }
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", tmp_path / "knowledge_bases")

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/ready-kb/upload",
            files=_duplicate_upload_payload(),
        )

    assert response.status_code == 400
    assert "duplicate filename" in response.json()["detail"].lower()
    assert not list((tmp_path / "knowledge_bases" / "ready-kb" / ".uploads").rglob("demo.txt"))


def test_upload_rejects_mime_extension_mismatch_and_rolls_back_staging(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = _FakeKBManager(tmp_path / "knowledge_bases")
    manager.config["knowledge_bases"]["ready-kb"] = {
        "path": "ready-kb",
        "rag_provider": "llamaindex",
        "needs_reindex": False,
        "status": "ready",
    }
    monkeypatch.setattr(knowledge_router_module, "get_kb_manager", lambda: manager)
    monkeypatch.setattr(knowledge_router_module, "_kb_base_dir", tmp_path / "knowledge_bases")

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/knowledge/ready-kb/upload",
            files=[("files", ("lesson.pdf", b"<html></html>", "text/html"))],
        )

    assert response.status_code == 400
    assert "does not match file extension" in response.json()["detail"].lower()
    assert not list((tmp_path / "knowledge_bases" / "ready-kb" / ".uploads").rglob("lesson.pdf"))


def test_upload_processing_marks_error_when_no_staged_file_indexes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "knowledge_bases"
    kb_dir = base_dir / "ready-kb"
    staging_dir = kb_dir / ".uploads" / "task-1"
    staging_dir.mkdir(parents=True)
    staged_file = staging_dir / "demo.txt"
    staged_file.write_text("hello", encoding="utf-8")

    class _FailingAdder:
        def __init__(self, **_kwargs) -> None:
            pass

        def add_documents(self, file_paths, allow_duplicates=False):
            return [Path(file_paths[0])]

        async def process_new_documents(self, _staged_files):
            return []

    monkeypatch.setattr(knowledge_router_module, "DocumentAdder", _FailingAdder)

    asyncio.run(
        knowledge_router_module.run_upload_processing_task(
            kb_name="ready-kb",
            base_dir=str(base_dir),
            uploaded_file_paths=[str(staged_file)],
            task_id="kb_upload_test_no_indexed_files",
            rag_provider="llamaindex",
        )
    )

    progress = knowledge_router_module.ProgressTracker("ready-kb", base_dir).get_progress()
    assert progress is not None
    assert progress["stage"] == "error"
    assert "No staged files were indexed successfully" in progress["error"]
    assert not staging_dir.exists()


def test_reindex_processing_marks_progress_error_on_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "knowledge_bases"
    task_id = f"kb_reindex_failed_{tmp_path.name}"

    async def _failing_rebuild(*_args, **_kwargs):
        raise RuntimeError("milvus unavailable")

    monkeypatch.setattr(knowledge_router_module, "rebuild_knowledge_index", _failing_rebuild)

    asyncio.run(
        knowledge_router_module.run_reindex_processing_task(
            kb_name="ready-kb",
            base_dir=str(base_dir),
            task_id=task_id,
            rag_provider="milvus",
            backup=False,
        )
    )

    progress = knowledge_router_module.ProgressTracker("ready-kb", base_dir).get_progress()
    metadata = knowledge_router_module.TaskIDManager.get_instance().get_task_metadata(task_id)
    assert progress is not None
    assert progress["stage"] == "error"
    assert "milvus unavailable" in progress["error"]
    assert metadata is not None
    assert metadata["status"] == "error"


def test_update_config_coerces_legacy_provider_to_milvus() -> None:
    """Legacy `rag_provider` values are accepted and normalized to milvus."""

    class _FakeConfigService:
        def __init__(self) -> None:
            self.config: dict = {}

        def set_kb_config(self, kb_name: str, config: dict) -> None:
            self.kb_name = kb_name
            self.config = config

        def get_kb_config(self, _kb_name: str) -> dict:
            return {"rag_provider": "milvus"}

    fake_service = _FakeConfigService()

    app = _build_app()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            knowledge_router_module,
            "get_kb_config_service",
            lambda: fake_service,
        )
        with TestClient(app) as client:
            response = client.put(
                "/api/v1/knowledge/demo/config",
                json={"rag_provider": "raganything"},
            )

    assert response.status_code in {200, 204}
    assert fake_service.config.get("rag_provider") == "milvus"


