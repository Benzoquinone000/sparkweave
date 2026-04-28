"""Runtime selector for compatibility and LangGraph turn managers."""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging
from typing import Any

from sparkweave.runtime.policy import select_runtime
from sparkweave.runtime.turn_runtime import LangGraphTurnRuntimeManager
from sparkweave.services.session import (
    SQLiteSessionStore,
    get_compatibility_turn_runtime_manager,
    get_session_store,
)

logger = logging.getLogger(__name__)


class RuntimeRoutingTurnManager:
    """Delegate turn operations to compatibility or NG runtime based on request config."""

    def __init__(
        self,
        *,
        compatibility: Any | None = None,
        legacy: Any | None = None,
        langgraph: Any | None = None,
        store: SQLiteSessionStore | None = None,
    ) -> None:
        if compatibility is not None and legacy is not None and compatibility is not legacy:
            raise ValueError("Pass only one of compatibility= or legacy=.")
        self.compatibility = (
            compatibility
            if compatibility is not None
            else legacy
            if legacy is not None
            else get_compatibility_turn_runtime_manager()
        )
        self.legacy = self.compatibility
        self.store = store or getattr(self.compatibility, "store", None) or get_session_store()
        self.langgraph = langgraph or LangGraphTurnRuntimeManager(store=self.store)
        self._turn_runtimes: dict[str, str] = {}

    async def start_turn(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        requested_runtime = self._runtime_from_payload(payload)
        runtime_name, runtime = self._resolve_runtime(requested_runtime)
        session, turn = await runtime.start_turn(payload)
        self._turn_runtimes[str(turn["id"])] = runtime_name
        return session, turn

    async def subscribe_turn(
        self,
        turn_id: str,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        runtime = await self._runtime_for_turn(turn_id)
        async for event in runtime.subscribe_turn(turn_id, after_seq=after_seq):
            yield event

    async def subscribe_session(
        self,
        session_id: str,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        turn = await self.store.get_active_turn(session_id)
        if turn is None:
            turn = await self.store.get_latest_turn(session_id)
        if turn is None:
            return
        async for event in self.subscribe_turn(turn["id"], after_seq=after_seq):
            yield event

    async def cancel_turn(self, turn_id: str) -> bool:
        primary = await self._runtime_for_turn(turn_id)
        if await primary.cancel_turn(turn_id):
            return True
        secondary = self.langgraph if primary is self.compatibility else self.compatibility
        return bool(await secondary.cancel_turn(turn_id))

    def _resolve_runtime(self, name: str) -> tuple[str, Any]:
        if name == "langgraph":
            return "langgraph", self.langgraph
        if self._compatibility_available():
            return "compatibility", self.compatibility
        logger.info("Compatibility runtime requested but unavailable; using LangGraph runtime.")
        return "langgraph", self.langgraph

    def _runtime_for_name(self, name: str) -> Any:
        if name in {"compatibility", "compat", "legacy"}:
            if self._compatibility_available():
                return self.compatibility
            return self.langgraph
        return self._resolve_runtime(name)[1]

    async def _runtime_for_turn(self, turn_id: str) -> Any:
        runtime_name = self._turn_runtimes.get(turn_id)
        if runtime_name is None:
            runtime_name = await self._runtime_from_persisted_events(turn_id)
            if runtime_name is not None:
                self._turn_runtimes[turn_id] = runtime_name
        return self._runtime_for_name(runtime_name or self._default_runtime_for_unknown_turn())

    async def _runtime_from_persisted_events(self, turn_id: str) -> str | None:
        for event in await self.store.get_turn_events(turn_id, after_seq=0):
            metadata = event.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            runtime = str(metadata.get("runtime") or "").strip().lower()
            source = str(event.get("source") or "").strip().lower()
            if runtime in {"langgraph", "ng"} or source == "langgraph":
                return "langgraph"
        return None

    @staticmethod
    def _runtime_from_payload(payload: dict[str, Any]) -> str:
        config = payload.get("config")
        if not isinstance(config, dict):
            config = {}
        return select_runtime(
            capability=str(payload.get("capability") or "chat"),
            explicit_runtime=str(payload.get("runtime") or config.get("_runtime") or ""),
        )

    def _default_runtime_for_unknown_turn(self) -> str:
        if self._compatibility_available():
            return "compatibility"
        return "langgraph"

    def _compatibility_available(self) -> bool:
        return bool(getattr(self.compatibility, "available", True))

    def _legacy_available(self) -> bool:
        return self._compatibility_available()


__all__ = ["RuntimeRoutingTurnManager"]

