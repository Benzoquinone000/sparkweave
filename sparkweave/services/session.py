"""Session service facade for the NG runtime."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sparkweave.services.session_store import SQLiteSessionStore, get_sqlite_session_store

_runtime_router: Any | None = None


class CompatibilityRuntimeUnavailable:
    """Placeholder used when an injected compatibility runtime is unavailable."""

    available = False
    store: SQLiteSessionStore | None = None

    def __init__(self, reason: BaseException | None = None) -> None:
        self.reason = reason

    async def start_turn(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        raise RuntimeError(
            "SparkWeave compatibility runtime is disabled or unavailable. Use "
            "runtime='langgraph' or SPARKWEAVE_RUNTIME=ng to run through sparkweave."
        ) from self.reason

    async def subscribe_turn(
        self,
        turn_id: str,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        if False:
            yield {"turn_id": turn_id, "seq": after_seq}

    async def cancel_turn(self, turn_id: str) -> bool:
        return False


class LegacyRuntimeUnavailable(CompatibilityRuntimeUnavailable):
    """Backward-compatible alias for CompatibilityRuntimeUnavailable."""


def create_session_store(db_path: Path | None = None) -> SQLiteSessionStore:
    """Create an isolated SQLite-backed session store."""
    return SQLiteSessionStore(db_path=db_path)


def get_session_store() -> SQLiteSessionStore:
    """Return the shared session store used by the current process."""
    return get_sqlite_session_store()


def get_compatibility_turn_runtime_manager() -> Any:
    """Return the optional compatibility runtime placeholder.

    NG callers can still inject a compatibility runtime explicitly through the
    router. The default NG package does not import the old package, so deleting
    that folder does not affect the normal LangGraph runtime path.
    """
    return CompatibilityRuntimeUnavailable()


def get_legacy_turn_runtime_manager() -> Any:
    """Backward-compatible name for get_compatibility_turn_runtime_manager."""
    return get_compatibility_turn_runtime_manager()


def create_turn_runtime_manager(
    store: SQLiteSessionStore | None = None,
) -> Any:
    """Create a turn runtime manager with an explicit or shared store."""
    from sparkweave.runtime.turn_runtime import LangGraphTurnRuntimeManager

    return LangGraphTurnRuntimeManager(store=store)


def create_runtime_router(
    *,
    compatibility: Any | None = None,
    legacy: Any | None = None,
    langgraph: Any | None = None,
    store: SQLiteSessionStore | None = None,
) -> Any:
    """Create a router that selects compatibility or LangGraph turn execution."""
    from sparkweave.runtime.routing import RuntimeRoutingTurnManager

    return RuntimeRoutingTurnManager(
        compatibility=compatibility,
        legacy=legacy,
        langgraph=langgraph,
        store=store,
    )


def get_runtime_manager() -> Any:
    """Return the shared runtime router used by the current process."""
    global _runtime_router
    if _runtime_router is None:
        _runtime_router = create_runtime_router()
    return _runtime_router


__all__ = [
    "SQLiteSessionStore",
    "CompatibilityRuntimeUnavailable",
    "LegacyRuntimeUnavailable",
    "create_runtime_router",
    "create_session_store",
    "create_turn_runtime_manager",
    "get_compatibility_turn_runtime_manager",
    "get_legacy_turn_runtime_manager",
    "get_runtime_manager",
    "get_session_store",
]

