from __future__ import annotations

from fastapi.testclient import TestClient

from sparkweave.api.app_factory import create_app


def test_create_app_wires_root_route_and_path_service() -> None:
    app = create_app()

    assert app.title == "SparkWeave API"
    assert app.state.path_service.__class__.__module__ == "sparkweave.services.paths"
    assert TestClient(app).get("/").json() == {"message": "Welcome to SparkWeave API"}
