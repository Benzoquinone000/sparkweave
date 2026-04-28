"""Dependency helpers for optional LangChain/LangGraph integrations."""

from __future__ import annotations

from importlib import import_module
from typing import Any

LANGGRAPH_EXTRA = "langgraph"


def dependency_error(package: str) -> RuntimeError:
    """Build a consistent runtime error for missing optional dependencies."""
    return RuntimeError(
        f"{package} is required for the LangGraph runtime. "
        f"Install it with `pip install -e .[{LANGGRAPH_EXTRA}]` or "
        "`pip install -r requirements/cli.txt`."
    )


def import_required(module_name: str) -> Any:
    """Import an optional dependency and raise a user-facing error if missing."""
    try:
        return import_module(module_name)
    except ImportError as exc:
        raise dependency_error(module_name.split(".", 1)[0]) from exc
