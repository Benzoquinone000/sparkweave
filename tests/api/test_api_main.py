from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_api_main_uses_ng_paths_and_registry_consistency() -> None:
    api_main = importlib.import_module("sparkweave.api.main")

    assert api_main.path_service.__class__.__module__ == "sparkweave.services.paths"
    api_main.validate_tool_consistency()


def test_api_main_security_helpers_are_env_driven(monkeypatch) -> None:
    api_main = importlib.import_module("sparkweave.api.main")

    monkeypatch.delenv("SPARKWEAVE_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("SPARKWEAVE_CORS_ORIGIN_REGEX", raising=False)
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    assert "http://localhost:3782" in api_main.configured_cors_origins()
    assert api_main.configured_cors_origin_regex()

    monkeypatch.setenv("SPARKWEAVE_CORS_ORIGINS", "https://learn.example, https://admin.example")
    assert api_main.configured_cors_origins() == ["https://learn.example", "https://admin.example"]
    monkeypatch.setenv("SPARKWEAVE_CORS_ORIGIN_REGEX", r"^https://.*\.example$")
    assert api_main.configured_cors_origin_regex() == r"^https://.*\.example$"

    monkeypatch.setenv("SPARKWEAVE_API_KEY", "one")
    monkeypatch.setenv("SPARKWEAVE_API_KEYS", "two,three")
    assert api_main.configured_api_keys() == ["one", "three", "two"]


def test_api_key_auth_protects_http_routes(monkeypatch) -> None:
    api_main = importlib.import_module("sparkweave.api.main")
    monkeypatch.setenv("SPARKWEAVE_API_KEY", "secret")

    client = TestClient(api_main.app)

    assert client.get("/api/v1/system/status").status_code == 401
    assert client.get("/api/v1/system/status", headers={"x-sparkweave-api-key": "secret"}).status_code != 401
    assert client.get("/api/v1/system/status?api_key=secret").status_code != 401


def test_api_key_auth_protects_public_outputs(monkeypatch) -> None:
    api_main = importlib.import_module("sparkweave.api.main")
    monkeypatch.setenv("SPARKWEAVE_API_KEY", "secret")

    client = TestClient(api_main.app)

    assert client.get("/api/outputs/missing.png").status_code == 401
    assert client.get("/api/outputs/missing.png?sparkweave_api_key=secret").status_code == 404


def test_public_outputs_force_active_content_to_download(tmp_path) -> None:
    api_main = importlib.import_module("sparkweave.api.main")
    output_root = tmp_path / "outputs"
    active_file = output_root / "workspace" / "chat" / "deep_solve" / "solve_1" / "artifacts" / "report.html"
    active_file.parent.mkdir(parents=True)
    active_file.write_text("<script>alert(1)</script>", encoding="utf-8")

    class FakePathService:
        def is_public_output_path(self, path: str) -> bool:
            return path.replace("\\", "/") == "workspace/chat/deep_solve/solve_1/artifacts/report.html"

    app = FastAPI()
    app.mount(
        "/api/outputs",
        api_main.SafeOutputStaticFiles(directory=str(output_root), path_service=FakePathService()),
        name="outputs",
    )

    response = TestClient(app).get("/api/outputs/workspace/chat/deep_solve/solve_1/artifacts/report.html")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="report.html"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"].startswith("sandbox")


def test_security_headers_are_added(monkeypatch) -> None:
    api_main = importlib.import_module("sparkweave.api.main")
    monkeypatch.delenv("SPARKWEAVE_API_KEY", raising=False)
    monkeypatch.delenv("SPARKWEAVE_API_KEYS", raising=False)

    response = TestClient(api_main.app).get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]


def test_api_key_auth_protects_websocket_routes(monkeypatch) -> None:
    api_main = importlib.import_module("sparkweave.api.main")
    monkeypatch.setenv("SPARKWEAVE_API_KEY", "secret")

    client = TestClient(api_main.app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws"):
            pass

    with client.websocket_connect("/api/v1/ws?sparkweave_api_key=secret") as websocket:
        websocket.send_json({"type": "unknown"})
        assert websocket.receive_json()["type"] == "error"


