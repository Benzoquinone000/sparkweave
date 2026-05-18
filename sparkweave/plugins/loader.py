"""Manifest discovery for optional NG playground plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any, Iterable

import yaml

logger = logging.getLogger(__name__)

PLUGIN_PATH_ENV = "SPARKWEAVE_NG_PLUGIN_PATH"
LEGACY_PLUGIN_PATH_ENV = "SPARKWEAVE_PLUGIN_PATH"
MANIFEST_FILENAMES = (
    "manifest.yaml",
    "manifest.yml",
    "plugin.yaml",
    "plugin.yml",
    "plugin.json",
)


@dataclass(frozen=True)
class PluginManifest:
    """Small manifest record used by the plugin API and CLI listing."""

    name: str
    type: str = "playground"
    description: str = ""
    stages: list[str] = field(default_factory=list)
    version: str = "0.1.0"
    author: str = ""
    path: str = ""
    entrypoint: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "stages": list(self.stages),
            "version": self.version,
            "author": self.author,
            "path": self.path,
            "entrypoint": self.entrypoint,
        }


def discover_plugins(paths: Iterable[str | Path] | None = None) -> list[PluginManifest]:
    """Discover plugin manifests from configured roots.

    Each root may either contain a manifest directly or contain child
    directories that each provide one. Invalid manifests are skipped so a
    broken plugin cannot take down the API plugin listing.
    """
    manifests: list[PluginManifest] = []
    seen_paths: set[Path] = set()
    seen_names: set[str] = set()
    for root in _plugin_roots(paths):
        if not root.exists() or not root.is_dir():
            continue
        for manifest_path in _manifest_paths(root):
            resolved = manifest_path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            try:
                manifest = load_plugin_manifest(manifest_path)
            except Exception as exc:
                logger.warning("Skipping invalid plugin manifest %s: %s", manifest_path, exc)
                continue

            name_key = manifest.name.casefold()
            if name_key in seen_names:
                logger.info("Skipping duplicate plugin manifest %s for %s", manifest_path, manifest.name)
                continue
            seen_names.add(name_key)
            manifests.append(manifest)
    manifests.sort(key=lambda item: (item.type, item.name))
    return manifests


def load_plugin_manifest(path: str | Path) -> PluginManifest:
    """Load one plugin manifest file."""
    manifest_path = Path(path)
    payload = _read_manifest_payload(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError("plugin manifest must be a mapping")

    name = str(payload.get("name") or manifest_path.parent.name).strip()
    if not name:
        raise ValueError("plugin manifest is missing `name`")

    raw_stages = payload.get("stages", [])
    if isinstance(raw_stages, str):
        stages = [item.strip() for item in raw_stages.split(",") if item.strip()]
    elif isinstance(raw_stages, list):
        stages = [str(item).strip() for item in raw_stages if str(item).strip()]
    else:
        stages = []

    entrypoint = (
        payload.get("entrypoint")
        or payload.get("entry_point")
        or payload.get("module")
        or payload.get("capability")
        or ""
    )
    return PluginManifest(
        name=name,
        type=str(payload.get("type") or "playground").strip() or "playground",
        description=str(payload.get("description") or "").strip(),
        stages=stages,
        version=str(payload.get("version") or "0.1.0").strip() or "0.1.0",
        author=str(payload.get("author") or "").strip(),
        path=str(manifest_path.parent),
        entrypoint=str(entrypoint or "").strip(),
        raw=dict(payload),
    )


def _read_manifest_payload(manifest_path: Path) -> Any:
    raw_text = manifest_path.read_text(encoding="utf-8")
    if manifest_path.suffix.lower() == ".json":
        return json.loads(raw_text or "{}")
    return yaml.safe_load(raw_text) or {}


def _plugin_roots(paths: Iterable[str | Path] | None) -> list[Path]:
    candidates: list[Path] = []
    if paths is not None:
        candidates.extend(Path(item).expanduser() for item in paths)
    else:
        candidates.append(Path(__file__).parent)
        candidates.append(Path(__file__).resolve().parents[2] / "plugins")
        candidates.extend(_env_paths(os.getenv(PLUGIN_PATH_ENV, "")))
        candidates.extend(_env_paths(os.getenv(LEGACY_PLUGIN_PATH_ENV, "")))

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _env_paths(raw: str) -> list[Path]:
    return [Path(item).expanduser() for item in raw.split(os.pathsep) if item.strip()]


def _manifest_paths(root: Path) -> list[Path]:
    direct = _find_manifest(root)
    if direct is not None:
        return [direct]

    manifests: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("__"):
            continue
        manifest = _find_manifest(child)
        if manifest is not None:
            manifests.append(manifest)
    return manifests


def _find_manifest(directory: Path) -> Path | None:
    for filename in MANIFEST_FILENAMES:
        path = directory / filename
        if path.is_file():
            return path
    return None


__all__ = [
    "LEGACY_PLUGIN_PATH_ENV",
    "MANIFEST_FILENAMES",
    "PLUGIN_PATH_ENV",
    "PluginManifest",
    "discover_plugins",
    "load_plugin_manifest",
]

