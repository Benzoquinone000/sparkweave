"""User interface settings helpers owned by ``sparkweave``."""

from __future__ import annotations

import json
from typing import Any

from sparkweave.services.paths import get_path_service

INTERFACE_SETTINGS_FILE = get_path_service().get_settings_file("interface")

DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "theme": "light",
    "language": "en",
}


def _normalize_language(language: Any, default: str = "en") -> str:
    if language is None or language == "":
        language = default

    if isinstance(language, str):
        value = language.lower().strip()
        if value in {"en", "english"}:
            return "en"
        if value in {"zh", "chinese", "cn"}:
            return "zh"

    if isinstance(default, str):
        return _normalize_language(default, "en")
    return "en"


def get_ui_settings() -> dict[str, Any]:
    """Read UI settings from ``data/user/settings/interface.json``."""
    if INTERFACE_SETTINGS_FILE.exists():
        try:
            saved = json.loads(INTERFACE_SETTINGS_FILE.read_text(encoding="utf-8")) or {}
            merged = {**DEFAULT_UI_SETTINGS, **saved}
            merged["language"] = _normalize_language(
                merged.get("language"),
                DEFAULT_UI_SETTINGS["language"],
            )
            return merged
        except Exception:
            return DEFAULT_UI_SETTINGS.copy()

    return DEFAULT_UI_SETTINGS.copy()


def get_ui_language(default: str = "en") -> str:
    """Return the selected UI language with a safe default."""
    settings = get_ui_settings()
    return _normalize_language(settings.get("language"), default)


__all__ = [
    "DEFAULT_UI_SETTINGS",
    "INTERFACE_SETTINGS_FILE",
    "get_ui_language",
    "get_ui_settings",
]

