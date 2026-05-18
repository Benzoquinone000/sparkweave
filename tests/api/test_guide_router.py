from __future__ import annotations

import importlib


def test_guide_router_uses_ng_services():
    guide_module = importlib.import_module("sparkweave.api.routers.guide")

    assert guide_module.BaseAgent.__module__ == "sparkweave.services.guide_generation"
    assert guide_module.GuideManager.__module__ == "sparkweave.services.guide_generation"
    assert guide_module.NotebookAnalysisAgent.__module__ == "sparkweave.services.context"
    assert guide_module.notebook_manager.__class__.__module__ == "sparkweave.services.notebook"


