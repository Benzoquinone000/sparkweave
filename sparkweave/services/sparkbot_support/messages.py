"""Inbound/outbound message contracts for SparkBot channels."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SparkBotInboundMessage:
    channel: str
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_key: str | None = None


@dataclass(slots=True)
class SparkBotOutboundMessage:
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SparkBotMessageBus:
    """Small NG-owned bus that mirrors the old SparkBot inbound/outbound queues."""

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[SparkBotInboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[SparkBotOutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: SparkBotInboundMessage) -> None:
        await self.inbound.put(msg)

    async def consume_inbound(self) -> SparkBotInboundMessage:
        return await self.inbound.get()

    async def publish_outbound(self, msg: SparkBotOutboundMessage) -> None:
        await self.outbound.put(msg)

    async def consume_outbound(self) -> SparkBotOutboundMessage:
        return await self.outbound.get()


__all__ = [
    "SparkBotInboundMessage",
    "SparkBotMessageBus",
    "SparkBotOutboundMessage",
]
