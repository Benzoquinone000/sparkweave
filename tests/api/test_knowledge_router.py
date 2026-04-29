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


def test_rag_providers_returns_llamaindex_only() -> None:
    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/knowledge/rag-providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "providers": [
            {
                "id": "llamaindex",
                "name": "LlamaIndex",
                "description": "Pure vector retrieval, fastest processing speed.",
            }
        ]
    }


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


def test_create_coerces_legacy_provider_to_llamaindex(monkeypatch, tmp_path: Path) -> None:
    """`rag_provider` is now a stub: legacy values silently normalize to llamaindex."""
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
    assert manager.config["knowledge_bases"]["kb-legacy"]["rag_provider"] == "llamaindex"


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


def test_update_config_coerces_legacy_provider_to_llamaindex() -> None:
    """Legacy `rag_provider` values are accepted and normalized to llamaindex."""

    class _FakeConfigService:
        def __init__(self) -> None:
            self.config: dict = {}

        def set_kb_config(self, kb_name: str, config: dict) -> None:
            self.kb_name = kb_name
            self.config = config

        def get_kb_config(self, _kb_name: str) -> dict:
            return {"rag_provider": "llamaindex"}

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
    assert fake_service.config.get("rag_provider") == "llamaindex"


