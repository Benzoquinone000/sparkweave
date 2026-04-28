from __future__ import annotations

import importlib


def test_api_main_uses_ng_paths_and_registry_consistency() -> None:
    api_main = importlib.import_module("sparkweave.api.main")

    assert api_main.path_service.__class__.__module__ == "sparkweave.services.paths"
    api_main.validate_tool_consistency()


