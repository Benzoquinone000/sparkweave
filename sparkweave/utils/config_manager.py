"""Runtime YAML configuration manager."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any

import yaml

from sparkweave.services.config import get_runtime_settings_dir


class ConfigManager:
    """Minimal manager for ``data/user/settings/main.yaml``."""

    _instance: ConfigManager | None = None
    _lock = RLock()

    def __new__(cls, project_root: Path | None = None) -> ConfigManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_root: Path | None = None) -> None:
        if getattr(self, "_initialized", False):
            return

        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.config_path = get_runtime_settings_dir(self.project_root) / "main.yaml"
        self._config_cache: dict[str, Any] = {}
        self._last_mtime = 0.0
        self._initialized = True

    def load_config(self, force_reload: bool = False) -> dict[str, Any]:
        """Load the runtime YAML config, using a shallow mtime cache."""
        with self._lock:
            if not self.config_path.exists():
                self._config_cache = {}
                self._last_mtime = 0.0
                return {}

            current_mtime = self.config_path.stat().st_mtime
            if not self._config_cache or force_reload or current_mtime > self._last_mtime:
                self._config_cache = self._read_yaml()
                self._last_mtime = current_mtime

            return yaml.safe_load(yaml.safe_dump(self._config_cache, sort_keys=False)) or {}

    def save_config(self, config: dict[str, Any]) -> bool:
        """Deep-merge and atomically save runtime YAML config."""
        with self._lock:
            current = self.load_config(force_reload=True)
            self._deep_update(current, config)

            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_str = yaml.safe_dump(
                current,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

            fd, tmp_path = tempfile.mkstemp(prefix="main.yaml.", dir=str(self.config_path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    tmp.write(yaml_str)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(tmp_path, self.config_path)
                self._config_cache = current
                self._last_mtime = self.config_path.stat().st_mtime
                return True
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    def get_env_info(self) -> dict[str, str]:
        """Read selected environment information from project ``.env`` and process env."""
        parsed_env = self._load_env_file(self.project_root / ".env")

        def _get(key: str, default: str = "") -> str:
            return str(parsed_env.get(key) or os.environ.get(key, default))

        return {"model": _get("LLM_MODEL", "")}

    def validate_required_env(self, keys: list[str]) -> dict[str, list[str]]:
        """Return missing required environment keys."""
        parsed_env = self._load_env_file(self.project_root / ".env")
        missing = [key for key in keys if not (parsed_env.get(key) or os.environ.get(key))]
        return {"missing": missing}

    def _load_env_file(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
        return values

    def _read_yaml(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _deep_update(self, target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    @classmethod
    def reset_for_tests(cls) -> None:
        """Clear the process singleton for isolated tests."""
        with cls._lock:
            cls._instance = None


__all__ = ["ConfigManager"]

