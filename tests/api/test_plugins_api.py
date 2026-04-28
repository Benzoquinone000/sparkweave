"""Unit tests for the NG plugin playground API router."""

from __future__ import annotations

import pytest

from sparkweave.plugins.loader import PluginManifest


@pytest.mark.asyncio
async def test_plugin_list_includes_discovered_playground_plugins(monkeypatch) -> None:
    from sparkweave.api.routers import plugins_api

    class FakeToolRegistry:
        def get_definitions(self):
            return []

    class FakeCapabilityRegistry:
        def get_manifests(self):
            return []

    monkeypatch.setattr(plugins_api, "get_tool_registry", lambda: FakeToolRegistry())
    monkeypatch.setattr(plugins_api, "get_capability_registry", lambda: FakeCapabilityRegistry())
    monkeypatch.setattr(
        plugins_api,
        "_discover_plugins",
        lambda: [
            PluginManifest(
                name="api_plugin",
                type="playground",
                description="API plugin",
                stages=["draft"],
                version="2.0.0",
                author="SparkWeave",
            )
        ],
    )

    payload = await plugins_api.list_plugins()

    assert payload["tools"] == []
    assert payload["capabilities"] == []
    assert payload["plugins"] == [
        {
            "name": "api_plugin",
            "type": "playground",
            "description": "API plugin",
            "stages": ["draft"],
            "version": "2.0.0",
            "author": "SparkWeave",
        }
    ]

