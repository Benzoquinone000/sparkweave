"""Setup and port helpers owned by ``sparkweave``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from sparkweave.services.config import get_env_store
from sparkweave.services.paths import get_path_service

logger = logging.getLogger(__name__)

DEFAULT_INTERFACE_SETTINGS = {
    "theme": "light",
    "language": "en",
    "sidebar_description": "SparkWeave 星火织学",
    "sidebar_nav_order": {
        "start": ["/", "/history", "/knowledge", "/notebook"],
        "learnResearch": ["/question", "/solver", "/guide", "/research", "/co_writer"],
    },
}

DEFAULT_MAIN_SETTINGS = {
    "system": {
        "language": "en",
    },
    "logging": {
        "level": "WARNING",
        "save_to_file": True,
        "console_output": True,
    },
    "personalization": {
        "auto_update": True,
        "max_react_rounds": 6,
        "agents": {
            "reflection": True,
            "summary": True,
            "weakness": True,
        },
    },
    "tools": {
        "run_code": {
            "allowed_roots": ["./data/user"],
        },
        "web_search": {
            "enabled": True,
        },
    },
    "capabilities": {
        "question": {
            "max_parallel_questions": 1,
            "idea_loop": {"max_rounds": 3, "ideas_per_round": 5},
            "generation": {"max_retries": 2},
        },
        "solve": {
            "max_react_iterations": 10,
            "max_plan_steps": 10,
            "max_replans": 2,
            "observation_max_tokens": 2000,
            "enable_citations": True,
            "save_intermediate_results": True,
            "detailed_answer": True,
        },
        "research": {
            "researching": {
                "note_agent_mode": "auto",
                "tool_timeout": 60,
                "tool_max_retries": 2,
                "paper_search_years_limit": 3,
            },
        },
    },
}

DEFAULT_AGENTS_SETTINGS = {
    "capabilities": {
        "solve": {"temperature": 0.3, "max_tokens": 8192},
        "research": {"temperature": 0.5, "max_tokens": 12000},
        "question": {"temperature": 0.7, "max_tokens": 4096},
        "guide": {"temperature": 0.5, "max_tokens": 16192},
        "co_writer": {"temperature": 0.7, "max_tokens": 4096},
    },
    "tools": {
        "brainstorm": {"temperature": 0.8, "max_tokens": 2048},
    },
    "services": {
        "personalization": {"temperature": 0.5, "max_tokens": 8192},
    },
    "plugins": {
        "vision_solver": {"temperature": 0.3, "max_tokens": 12000},
        "math_animator": {"temperature": 0.4, "max_tokens": 12000},
    },
    "diagnostics": {
        "llm_probe": {"max_tokens": 1024},
    },
}


def init_user_directories(project_root: Path | None = None) -> None:
    """Create the NG user-data layout and seed essential settings once."""
    del project_root
    path_service = get_path_service()
    path_service.ensure_all_directories()
    _ensure_essential_settings(path_service)


def _ensure_essential_settings(path_service) -> None:
    interface_file = path_service.get_settings_file("interface")
    _write_json_if_missing(interface_file, DEFAULT_INTERFACE_SETTINGS)

    main_file = path_service.get_runtime_config_file("main")
    _write_yaml_if_missing(main_file, DEFAULT_MAIN_SETTINGS)

    agents_file = path_service.get_runtime_config_file("agents")
    _write_yaml_if_missing(agents_file, DEFAULT_AGENTS_SETTINGS)


def _write_json_if_missing(file_path: Path, payload: dict) -> None:
    if file_path.exists():
        return
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Created default settings: %s", file_path)
    except Exception as exc:
        logger.warning("Failed to create default JSON file %s: %s", file_path, exc)


def _write_yaml_if_missing(file_path: Path, payload: dict) -> None:
    if file_path.exists():
        return
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        logger.info("Created default settings: %s", file_path)
    except Exception as exc:
        logger.warning("Failed to create default YAML file %s: %s", file_path, exc)


def _port_from_env(key: str, default: int) -> int:
    raw = get_env_store().get(key, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s: %s, using default %s", key, raw, default)
        return default


def get_backend_port(project_root: Path | None = None) -> int:
    """Return the backend port from `.env` or environment variables."""
    del project_root
    return _port_from_env("BACKEND_PORT", 8001)


def get_frontend_port(project_root: Path | None = None) -> int:
    """Return the frontend port from `.env` or environment variables."""
    del project_root
    return _port_from_env("FRONTEND_PORT", 3782)


def get_ports(project_root: Path | None = None) -> tuple[int, int]:
    """Return `(backend_port, frontend_port)`."""
    return get_backend_port(project_root), get_frontend_port(project_root)


__all__ = [
    "DEFAULT_AGENTS_SETTINGS",
    "DEFAULT_INTERFACE_SETTINGS",
    "DEFAULT_MAIN_SETTINGS",
    "get_backend_port",
    "get_frontend_port",
    "get_ports",
    "init_user_directories",
]

