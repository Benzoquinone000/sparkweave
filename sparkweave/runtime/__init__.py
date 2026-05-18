"""Runtime runners for next-generation SparkWeave graphs."""

from .mode import RunMode, get_mode, is_cli, is_server, set_mode


def __getattr__(name: str):
    if name == "ChatOrchestrator":
        from .orchestrator import ChatOrchestrator

        return ChatOrchestrator
    if name == "LangGraphRunner":
        from .runner import LangGraphRunner

        return LangGraphRunner
    if name == "LangGraphTurnRuntimeManager":
        from .turn_runtime import LangGraphTurnRuntimeManager

        return LangGraphTurnRuntimeManager
    if name == "MIGRATED_CAPABILITIES":
        from .policy import MIGRATED_CAPABILITIES

        return MIGRATED_CAPABILITIES
    if name == "RuntimeRoutingTurnManager":
        from .routing import RuntimeRoutingTurnManager

        return RuntimeRoutingTurnManager
    if name == "TurnRunResult":
        from .turn_runtime import TurnRunResult

        return TurnRunResult
    if name == "capability_enabled_by_default":
        from .policy import capability_enabled_by_default

        return capability_enabled_by_default
    if name == "select_runtime":
        from .policy import select_runtime

        return select_runtime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ChatOrchestrator",
    "LangGraphRunner",
    "LangGraphTurnRuntimeManager",
    "MIGRATED_CAPABILITIES",
    "RunMode",
    "RuntimeRoutingTurnManager",
    "TurnRunResult",
    "capability_enabled_by_default",
    "get_mode",
    "is_cli",
    "is_server",
    "select_runtime",
    "set_mode",
]

