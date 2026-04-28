from __future__ import annotations

import importlib


def test_co_writer_router_uses_ng_services():
    module = importlib.import_module("sparkweave.api.routers.co_writer")

    assert module.AgenticChatPipeline.__module__ == "sparkweave.services.co_writer"
    assert module.EditAgent.__module__ == "sparkweave.services.co_writer"
    assert module.UnifiedContext.__module__ == "sparkweave.core.contracts"
    assert module.StreamBus.__module__ == "sparkweave.core.contracts"


