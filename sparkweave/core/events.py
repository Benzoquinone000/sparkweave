"""Adapters from LangGraph runtime activity to SparkWeave stream events."""

from __future__ import annotations

from typing import Any

from sparkweave.core.contracts import StreamBus


class StreamEventAdapter:
    """Small convenience wrapper around the legacy ``StreamBus``."""

    def __init__(self, stream: StreamBus, *, source: str) -> None:
        self.stream = stream
        self.source = source

    async def progress(self, message: str, *, stage: str, **metadata: Any) -> None:
        await self.stream.progress(
            message=message,
            source=self.source,
            stage=stage,
            metadata=metadata,
        )

    async def content(self, text: str, *, stage: str, **metadata: Any) -> None:
        await self.stream.content(
            text,
            source=self.source,
            stage=stage,
            metadata=metadata,
        )

    async def error(self, message: str, *, stage: str = "", **metadata: Any) -> None:
        await self.stream.error(
            message,
            source=self.source,
            stage=stage,
            metadata=metadata,
        )

