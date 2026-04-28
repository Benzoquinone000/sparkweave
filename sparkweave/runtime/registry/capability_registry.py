"""Capability registry backed by NG graph implementations."""

from __future__ import annotations

import logging
from typing import Any

from sparkweave.app import get_capability_registry as get_manifest_registry
from sparkweave.core.capability_protocol import BaseCapability, CapabilityManifest
from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.runtime.runner import LangGraphRunner

logger = logging.getLogger(__name__)


class _GraphCapability(BaseCapability):
    """Expose a LangGraph-backed capability through the classic capability API."""

    def __init__(self, manifest: CapabilityManifest) -> None:
        self.manifest = manifest

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        previous_capability = context.active_capability
        context.active_capability = self.name
        try:
            await LangGraphRunner().run(context, stream)
        finally:
            context.active_capability = previous_capability


class CapabilityRegistry:
    """Registry of executable NG capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, BaseCapability] = {}

    def register(self, capability: BaseCapability) -> None:
        self._capabilities[capability.name] = capability
        logger.debug("Registered NG capability: %s", capability.name)

    def load_builtins(self) -> None:
        manifests = get_manifest_registry().get_manifests()
        for manifest_data in manifests:
            name = str(manifest_data["name"])
            if name in self._capabilities:
                continue
            self.register(_GraphCapability(_manifest_from_dict(manifest_data)))

    def load_plugins(self) -> None:
        """Reserved for future NG plugin capability loading."""

    def get(self, name: str) -> BaseCapability | None:
        return self._capabilities.get(name)

    def list_capabilities(self) -> list[str]:
        return list(self._capabilities.keys())

    def get_manifests(self) -> list[dict[str, Any]]:
        return [
            {
                "name": capability.manifest.name,
                "description": capability.manifest.description,
                "stages": list(capability.manifest.stages),
                "tools_used": list(capability.manifest.tools_used),
                "cli_aliases": list(capability.manifest.cli_aliases),
                "request_schema": dict(capability.manifest.request_schema),
                "config_defaults": dict(capability.manifest.config_defaults),
            }
            for capability in self._capabilities.values()
        ]


_default_registry: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    """Return the shared executable NG capability registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = CapabilityRegistry()
        _default_registry.load_builtins()
        _default_registry.load_plugins()
    return _default_registry


def _manifest_from_dict(data: dict[str, Any]) -> CapabilityManifest:
    return CapabilityManifest(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        stages=list(data.get("stages", [])),
        tools_used=list(data.get("tools_used", [])),
        cli_aliases=list(data.get("cli_aliases", [])),
        request_schema=dict(data.get("request_schema", {})),
        config_defaults=dict(data.get("config_defaults", {})),
    )


__all__ = ["CapabilityRegistry", "get_capability_registry"]

