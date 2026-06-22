from __future__ import annotations

from fastapi import FastAPI

from sparkweave.api import static_outputs


class FakePathService:
    def __init__(self, root):
        self.root = root
        self.ensure_called = False

    def get_public_outputs_root(self):
        return self.root

    def ensure_all_directories(self):
        self.ensure_called = True
        self.root.mkdir(parents=True, exist_ok=True)


def test_mount_public_outputs_mounts_filtered_static_handler(tmp_path, monkeypatch) -> None:
    service = FakePathService(tmp_path / "outputs")
    monkeypatch.setattr(static_outputs, "get_path_service", lambda: service)

    app = FastAPI()
    returned = static_outputs.mount_public_outputs(app)

    assert returned is service
    assert service.ensure_called
    assert any(route.path == "/api/outputs" for route in app.routes)
