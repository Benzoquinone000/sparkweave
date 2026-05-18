"""Runtime selection policy for NG-first LangGraph execution."""

from __future__ import annotations

import os
from typing import Literal

RuntimeName = Literal["legacy", "langgraph"]

MIGRATED_CAPABILITIES = frozenset(
    {
        "chat",
        "deep_question",
        "deep_research",
        "deep_solve",
        "math_animator",
        "visualize",
    }
)

_LANGGRAPH_VALUES = {"langgraph", "ng"}
_COMPATIBILITY_VALUES = {"compat", "compatibility", "legacy", "off", "false", "0"}
_AUTO_VALUES = {"auto", "rollout"}
_ALLOW_ALL = {"*", "all"}
_ALLOW_NONE = {"", "none", "compat", "compatibility", "legacy", "off", "false", "0"}


def select_runtime(
    *,
    capability: str | None,
    explicit_runtime: str | None = None,
    env_runtime: str | None = None,
    default_capabilities: str | None = None,
) -> RuntimeName:
    """Return the runtime selected for a capability.

    Precedence is:

    1. explicit request from payload/config
    2. ``SPARKWEAVE_RUNTIME``
    3. LangGraph default for migrated capabilities

    ``auto`` uses ``SPARKWEAVE_NG_DEFAULT_CAPABILITIES`` as an allowlist when
    provided. Without that variable, all migrated capabilities use LangGraph.
    """
    capability_name = _normalize_capability(capability)
    requested = _normalize(explicit_runtime)
    if requested:
        return _runtime_from_request(
            requested,
            capability=capability_name,
            default_capabilities=default_capabilities,
        )

    env_requested = _normalize(env_runtime)
    if not env_requested and env_runtime is None:
        env_requested = _normalize(os.getenv("SPARKWEAVE_RUNTIME", ""))
    return _runtime_from_request(
        env_requested,
        capability=capability_name,
        default_capabilities=default_capabilities,
    )


def capability_enabled_by_default(
    capability: str | None,
    default_capabilities: str | None = None,
) -> bool:
    """Return whether a capability is in the staged LangGraph default allowlist."""
    capability_name = _normalize_capability(capability)
    raw = (
        default_capabilities
        if default_capabilities is not None
        else os.getenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "all")
    )
    value = _normalize(raw)
    if value in _ALLOW_NONE:
        return False
    if value in _ALLOW_ALL:
        return capability_name in MIGRATED_CAPABILITIES
    enabled = {
        item.strip().lower()
        for item in str(raw or "").split(",")
        if item.strip()
    }
    return capability_name in enabled and capability_name in MIGRATED_CAPABILITIES


def _runtime_from_request(
    requested: str,
    *,
    capability: str,
    default_capabilities: str | None,
) -> RuntimeName:
    if not requested:
        return _default_runtime(capability)
    if requested in _LANGGRAPH_VALUES:
        return "langgraph"
    if requested in _COMPATIBILITY_VALUES:
        return "legacy"
    if requested in _AUTO_VALUES:
        if capability_enabled_by_default(capability, default_capabilities):
            return "langgraph"
        return "legacy"
    return _default_runtime(capability)


def _default_runtime(capability: str) -> RuntimeName:
    if capability in MIGRATED_CAPABILITIES:
        return "langgraph"
    return "legacy"


def _normalize(value: str | None) -> str:
    return str(value or "").strip().lower()


def _normalize_capability(capability: str | None) -> str:
    return str(capability or "chat").strip().lower() or "chat"


__all__ = [
    "MIGRATED_CAPABILITIES",
    "RuntimeName",
    "capability_enabled_by_default",
    "select_runtime",
]


