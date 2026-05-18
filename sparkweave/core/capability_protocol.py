"""Capability protocol contracts owned by the NG runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sparkweave.core.contracts import StreamBus, UnifiedContext


@dataclass
class CapabilityManifest:
    """Static metadata for a capability implementation."""

    name: str
    description: str
    stages: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    cli_aliases: list[str] = field(default_factory=list)
    request_schema: dict[str, Any] = field(default_factory=dict)
    config_defaults: dict[str, Any] = field(default_factory=dict)


class BaseCapability(ABC):
    """Base class for multi-step capability implementations."""

    manifest: CapabilityManifest

    @abstractmethod
    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        """Execute the capability and emit streaming events."""
        ...

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def stages(self) -> list[str]:
        return self.manifest.stages


__all__ = ["BaseCapability", "CapabilityManifest"]

