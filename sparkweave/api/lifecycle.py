"""FastAPI lifespan and startup validation helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

logger = logging.getLogger("API")

CONFIG_DRIFT_ERROR_TEMPLATE = (
    "Configuration Drift Detected: Capability tool references {drift} are not "
    "registered in the runtime tool registry. Register the missing tools or "
    "remove the stale tool names from the capability manifests."
)


def validate_tool_consistency() -> None:
    """
    Validate that capability manifests only reference tools that are actually
    registered in the runtime ``ToolRegistry``.
    """
    try:
        from sparkweave.app import get_capability_registry
        from sparkweave.tools.registry import get_tool_registry

        capability_registry = get_capability_registry()
        tool_registry = get_tool_registry()
        available_tools = set(tool_registry.list_tools())

        referenced_tools = set()
        for manifest in capability_registry.get_manifests():
            referenced_tools.update(manifest.get("tools_used", []) or [])

        drift = referenced_tools - available_tools
        if drift:
            raise RuntimeError(CONFIG_DRIFT_ERROR_TEMPLATE.format(drift=drift))
    except RuntimeError:
        logger.exception("Configuration validation failed")
        raise
    except Exception:
        logger.exception("Failed to load configuration for validation")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.

    Startup validates registry consistency, warms the configured LLM runtime, and
    starts configured SparkBot instances. Shutdown stops SparkBot instances.
    """
    logger.info("Application startup")
    validate_tool_consistency()

    try:
        from sparkweave.services.llm import get_llm_config

        llm_config = get_llm_config()
        logger.info("LLM config initialized: model=%s", llm_config.model)
    except Exception as exc:
        logger.warning("Failed to initialize LLM config at startup: %s", exc)

    try:
        from sparkweave.services.sparkbot import get_sparkbot_manager

        await get_sparkbot_manager().auto_start_bots()
    except Exception as exc:
        logger.warning("Failed to auto-start SparkBots: %s", exc)

    yield

    logger.info("Application shutdown")
    try:
        from sparkweave.services.sparkbot import get_sparkbot_manager

        await get_sparkbot_manager().stop_all()
        logger.info("SparkBots stopped")
    except Exception as exc:
        logger.warning("Failed to stop SparkBots: %s", exc)


__all__ = ["CONFIG_DRIFT_ERROR_TEMPLATE", "lifespan", "validate_tool_consistency"]
