from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rag_e2e_acceptance.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("rag_e2e_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rag_e2e = _load_module()


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any],
        *,
        status_code: int = 200,
        method: str = "GET",
        path: str = "/",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request(method, f"http://test.local{path}")
        self.text = json.dumps(payload, ensure_ascii=False)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=self,
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes: dict[tuple[str, str], list[Any]] = {
            key: list(value) if isinstance(value, list) else [value]
            for key, value in routes.items()
        }
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, path: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "path": path, "kwargs": kwargs})
        key = (method, path)
        if key not in self.routes:
            raise AssertionError(f"Unexpected request: {method} {path}")
        payloads = self.routes[key]
        payload = payloads.pop(0) if len(payloads) > 1 else payloads[0]
        if isinstance(payload, FakeResponse):
            return payload
        return FakeResponse(payload, method=method, path=path)

    def close(self) -> None:
        self.closed = True


def _args(*argv: str):
    return rag_e2e.build_parser().parse_args(
        [
            "--base-url",
            "http://test.local",
            "--timeout",
            "0.01",
            "--poll-interval",
            "0.001",
            *argv,
        ]
    )


def _success_routes(kb_name: str = "accept-kb") -> dict[tuple[str, str], Any]:
    return {
        ("GET", "/api/v1/knowledge/preflight?check_connection=true&check_docker=false"): {
            "status": "ready",
            "label": "检索就绪",
            "summary": "RAG runtime is ready.",
            "diagnostic": {"readiness": {"state": "ready"}},
            "recommended_commands": [],
        },
        ("POST", "/api/v1/knowledge/create"): {"name": kb_name, "task_id": "task-1"},
        ("GET", f"/api/v1/knowledge/{kb_name}/progress"): {
            "stage": "completed",
            "percent": 100,
        },
        ("GET", f"/api/v1/knowledge/{kb_name}/documents?include_vectors=true"): {
            "document_count": 1,
            "vector_count": 2,
            "vectors_available": True,
            "documents": [
                {
                    "id": "doc-1",
                    "name": rag_e2e.DEFAULT_FIXTURE_NAME,
                    "vector_count": 2,
                    "content_available": True,
                }
            ],
        },
        ("GET", f"/api/v1/knowledge/{kb_name}/vectors?limit=5"): {
            "available": True,
            "total": 2,
            "collection": "sparkweave_accept",
            "chunks": [{"id": "chunk-1"}, {"id": "chunk-2"}],
        },
        ("GET", f"/api/v1/knowledge/{kb_name}/diagnostics?check_connection=true"): {
            "status": "ok",
            "provider": "milvus",
            "marker_present": True,
            "collection_present": True,
            "vector_row_count": 2,
            "readiness": {"ready": True},
            "checks": [],
        },
        ("POST", f"/api/v1/knowledge/{kb_name}/rag-test"): {
            "success": True,
            "provider": "milvus",
            "content": "Ada Lovelace named the Quasar Lantern.",
            "sources": [
                {
                    "source": rag_e2e.DEFAULT_FIXTURE_NAME,
                    "content": "The verification phrase is Quasar Lantern. Ada Lovelace named it.",
                }
            ],
            "source_count": 1,
            "retrieval_profile": "auto",
            "retrieval_mode": "hybrid",
        },
        ("DELETE", f"/api/v1/knowledge/{kb_name}"): {"status": "deleted"},
    }


def test_run_acceptance_success_path_checks_upload_vectors_and_rag() -> None:
    client = FakeClient(_success_routes())
    runner = rag_e2e.RagAcceptanceRunner(_args("--kb", "accept-kb", "--cleanup"), client=client)

    report = runner.run()

    assert report["status"] == "passed"
    assert [step["name"] for step in report["steps"]] == [
        "configuration",
        "rag_preflight",
        "create_knowledge_base",
        "wait_for_indexing",
        "document_inventory",
        "vector_inventory",
        "rag_diagnostics",
        "rag_search",
        "cleanup",
    ]
    create_request = client.requests[1]
    assert create_request["method"] == "POST"
    assert create_request["kwargs"]["data"] == {"name": "accept-kb"}
    assert create_request["kwargs"]["files"][0][1][0] == rag_e2e.DEFAULT_FIXTURE_NAME
    assert client.closed is False


def test_missing_uploaded_document_fails_inventory_check() -> None:
    routes = _success_routes()
    routes[("GET", "/api/v1/knowledge/accept-kb/documents?include_vectors=true")] = {
        "document_count": 1,
        "documents": [{"id": "other", "name": "other.md"}],
    }
    runner = rag_e2e.RagAcceptanceRunner(_args("--kb", "accept-kb"), client=FakeClient(routes))

    with pytest.raises(rag_e2e.AcceptanceError, match="documents to appear"):
        runner.run()


def test_insufficient_vector_rows_fail_vector_check() -> None:
    routes = _success_routes()
    routes[("GET", "/api/v1/knowledge/accept-kb/vectors?limit=5")] = {
        "available": True,
        "total": 0,
        "chunks": [],
    }
    runner = rag_e2e.RagAcceptanceRunner(_args("--kb", "accept-kb"), client=FakeClient(routes))

    with pytest.raises(rag_e2e.AcceptanceError, match="vector rows"):
        runner.run()


def test_rag_search_requires_sources() -> None:
    client = FakeClient({
        ("POST", "/api/v1/knowledge/accept-kb/rag-test"): {
            "success": True,
            "content": "No evidence here.",
            "sources": [],
            "source_count": 0,
        }
    })
    runner = rag_e2e.RagAcceptanceRunner(_args("--kb", "accept-kb"), client=client)

    with pytest.raises(rag_e2e.AcceptanceError, match="Expected at least 1 RAG sources"):
        runner._check_rag_search([])


def test_reuse_existing_does_not_create_or_expect_default_fixture() -> None:
    kb_name = "existing-kb"
    routes = {
        ("GET", f"/api/v1/knowledge/{kb_name}/preflight?check_connection=true&check_docker=false"): {
            "status": "ready",
            "label": "检索就绪",
            "diagnostic": {"readiness": {"state": "ready"}},
        },
        ("GET", f"/api/v1/knowledge/{kb_name}/documents?include_vectors=true"): {
            "document_count": 1,
            "documents": [{"id": "doc-1", "name": "course-notes.md"}],
        },
        ("GET", f"/api/v1/knowledge/{kb_name}/vectors?limit=5"): {
            "available": True,
            "total": 1,
            "chunks": [{"id": "chunk-1"}],
        },
        ("GET", f"/api/v1/knowledge/{kb_name}/diagnostics?check_connection=true"): {
            "status": "ok",
            "provider": "milvus",
            "marker_present": True,
            "collection_present": True,
            "vector_row_count": 1,
        },
        ("POST", f"/api/v1/knowledge/{kb_name}/rag-test"): {
            "success": True,
            "content": "Existing knowledge base evidence.",
            "sources": [{"source": "course-notes.md", "content": "Existing evidence."}],
            "source_count": 1,
        },
    }
    client = FakeClient(routes)
    runner = rag_e2e.RagAcceptanceRunner(
        _args("--kb", kb_name, "--reuse-existing", "--question", "What is covered?"),
        client=client,
    )

    report = runner.run()

    assert report["status"] == "passed"
    assert all(request["path"] != "/api/v1/knowledge/create" for request in client.requests)
    assert report["steps"][2]["details"]["mode"] == "reuse-existing"


def test_preflight_failure_stops_before_creating_knowledge_base() -> None:
    routes = {
        ("GET", "/api/v1/knowledge/preflight?check_connection=true&check_docker=false"): {
            "status": "error",
            "label": "服务未启动",
            "summary": "Milvus is not reachable.",
            "primary_action": "Start Milvus before acceptance.",
            "diagnostic": {"readiness": {"state": "error", "label": "服务未启动"}},
            "recommended_commands": ["docker compose up -d milvus"],
        },
    }
    client = FakeClient(routes)
    runner = rag_e2e.RagAcceptanceRunner(_args("--kb", "accept-kb"), client=client)

    with pytest.raises(rag_e2e.AcceptanceError, match="服务未启动"):
        runner.run()

    assert [request["path"] for request in client.requests] == [
        "/api/v1/knowledge/preflight?check_connection=true&check_docker=false"
    ]


def test_cleanup_runs_when_created_knowledge_base_fails_later() -> None:
    kb_name = "accept-kb"
    routes = {
        ("GET", "/api/v1/knowledge/preflight?check_connection=true&check_docker=false"): {
            "status": "ready",
            "diagnostic": {"readiness": {"state": "ready"}},
        },
        ("POST", "/api/v1/knowledge/create"): {"name": kb_name, "task_id": "task-1"},
        ("GET", f"/api/v1/knowledge/{kb_name}/progress"): FakeResponse(
            {"detail": "proxy failed"},
            status_code=502,
            method="GET",
            path=f"/api/v1/knowledge/{kb_name}/progress",
        ),
        ("DELETE", f"/api/v1/knowledge/{kb_name}"): {"status": "deleted"},
    }
    client = FakeClient(routes)
    runner = rag_e2e.RagAcceptanceRunner(_args("--kb", kb_name, "--cleanup"), client=client)

    with pytest.raises(rag_e2e.AcceptanceError, match="HTTP 502"):
        runner.run()

    assert [request["path"] for request in client.requests] == [
        "/api/v1/knowledge/preflight?check_connection=true&check_docker=false",
        "/api/v1/knowledge/create",
        f"/api/v1/knowledge/{kb_name}/progress",
        f"/api/v1/knowledge/{kb_name}",
    ]
    assert runner.steps[-1].name == "cleanup"
    assert runner.steps[-1].status == "passed"


def test_local_api_urls_bypass_proxy_by_default(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(rag_e2e.httpx, "Client", DummyClient)

    runner = rag_e2e.RagAcceptanceRunner(_args("--base-url", "http://127.0.0.1:8001"))
    runner.close()

    assert captured["trust_env"] is False


def test_remote_api_urls_keep_proxy_support_by_default(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(rag_e2e.httpx, "Client", DummyClient)

    runner = rag_e2e.RagAcceptanceRunner(_args("--base-url", "https://api.example.com"))
    runner.close()

    assert captured["trust_env"] is True


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://localhost:8001", "ws://localhost:8001/api/v1/chat"),
        ("https://api.example.com/root/", "wss://api.example.com/root/api/v1/chat"),
    ],
)
def test_chat_ws_url_uses_matching_websocket_scheme(base_url: str, expected: str) -> None:
    assert rag_e2e._chat_ws_url(base_url) == expected
