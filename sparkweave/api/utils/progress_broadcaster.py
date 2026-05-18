"""WebSocket progress broadcaster for knowledge-base jobs."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import WebSocket

from sparkweave.logging import get_logger

logger = get_logger("ProgressBroadcaster")


class ProgressBroadcaster:
    """Manage WebSocket broadcasting of knowledge-base progress."""

    _instance: Optional["ProgressBroadcaster"] = None
    _connections: dict[str, set[WebSocket]] = {}
    _lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "ProgressBroadcaster":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self, kb_name: str, websocket: WebSocket):
        async with self._lock:
            if kb_name not in self._connections:
                self._connections[kb_name] = set()
            self._connections[kb_name].add(websocket)
            logger.debug(
                "Connected WebSocket for KB %r (total: %s)",
                kb_name,
                len(self._connections[kb_name]),
            )

    async def disconnect(self, kb_name: str, websocket: WebSocket):
        async with self._lock:
            if kb_name in self._connections:
                self._connections[kb_name].discard(websocket)
                if not self._connections[kb_name]:
                    del self._connections[kb_name]
                logger.debug("Disconnected WebSocket for KB %r", kb_name)

    async def broadcast(self, kb_name: str, progress: dict):
        async with self._lock:
            if kb_name not in self._connections:
                return

            to_remove = []
            for websocket in self._connections[kb_name]:
                try:
                    await websocket.send_json({"type": "progress", "data": progress})
                except Exception as exc:
                    logger.debug("Error sending to WebSocket for KB %r: %s", kb_name, exc)
                    to_remove.append(websocket)

            for websocket in to_remove:
                self._connections[kb_name].discard(websocket)

            if not self._connections[kb_name]:
                del self._connections[kb_name]

    def get_connection_count(self, kb_name: str) -> int:
        return len(self._connections.get(kb_name, set()))


__all__ = ["ProgressBroadcaster"]


