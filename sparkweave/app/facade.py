"""Stable application-layer facade owned by ``sparkweave``."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time
from typing import Any, AsyncIterator

from sparkweave.services.notebook import RecordType, get_notebook_manager
from sparkweave.services.session import get_runtime_manager
from sparkweave.services.session_store import get_sqlite_session_store
from sparkweave.services.validation import (
    ChatRequestConfig,
    DeepQuestionRequestConfig,
    DeepResearchRequestConfig,
    DeepSolveRequestConfig,
    MathAnimatorRequestConfig,
    VisualizeRequestConfig,
)


@dataclass(slots=True)
class TurnRequest:
    """Stable turn payload used by SDK and CLI adapters."""

    content: str
    capability: str = "chat"
    session_id: str | None = None
    tools: list[str] = field(default_factory=list)
    knowledge_bases: list[str] = field(default_factory=list)
    language: str = "en"
    config: dict[str, Any] = field(default_factory=dict)
    runtime: str = ""
    notebook_references: list[dict[str, Any]] = field(default_factory=list)
    history_references: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        config = dict(self.config)
        runtime = str(self.runtime or "").strip().lower()
        if runtime and runtime != "default":
            config["_runtime"] = runtime
        return {
            "content": self.content,
            "capability": self.capability,
            "session_id": self.session_id,
            "tools": list(self.tools),
            "knowledge_bases": list(self.knowledge_bases),
            "language": self.language,
            "config": config,
            "notebook_references": list(self.notebook_references),
            "history_references": list(self.history_references),
            "attachments": list(self.attachments),
        }


@dataclass(slots=True)
class CapabilityAvailability:
    """Availability result for optional capabilities."""

    name: str
    available: bool
    install_hint: str = ""


@dataclass(frozen=True)
class CapabilityManifest:
    """Small NG-owned capability manifest used by public facades."""

    name: str
    description: str
    stages: list[str]
    tools_used: list[str]
    cli_aliases: list[str]
    request_schema: dict[str, Any]
    config_defaults: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stages": list(self.stages),
            "tools_used": list(self.tools_used),
            "cli_aliases": list(self.cli_aliases),
            "request_schema": dict(self.request_schema),
            "config_defaults": dict(self.config_defaults),
        }


def _schema(model: type) -> dict[str, Any]:
    return model.model_json_schema()


def _builtins() -> list[CapabilityManifest]:
    return [
        CapabilityManifest(
            name="chat",
            description="Agentic chat with autonomous tool selection across enabled tools.",
            stages=["thinking", "acting", "observing", "responding"],
            tools_used=[
                "rag",
                "web_search",
                "external_video_search",
                "code_execution",
                "paper_search",
                "geogebra_analysis",
                "brainstorm",
                "reason",
            ],
            cli_aliases=["chat"],
            request_schema=_schema(ChatRequestConfig),
        ),
        CapabilityManifest(
            name="deep_solve",
            description="Multi-agent problem solving.",
            stages=["planning", "reasoning", "writing"],
            tools_used=["rag", "web_search", "code_execution", "reason"],
            cli_aliases=["solve"],
            request_schema=_schema(DeepSolveRequestConfig),
        ),
        CapabilityManifest(
            name="deep_question",
            description="Fast question generation and mimic generation.",
            stages=["ideation", "generation"],
            tools_used=["rag", "web_search", "code_execution"],
            cli_aliases=["quiz"],
            request_schema=_schema(DeepQuestionRequestConfig),
        ),
        CapabilityManifest(
            name="deep_research",
            description="Multi-agent deep research with report generation.",
            stages=["rephrasing", "decomposing", "researching", "reporting"],
            tools_used=["rag", "web_search", "paper_search", "code_execution"],
            cli_aliases=["research"],
            request_schema=_schema(DeepResearchRequestConfig),
            config_defaults={"mode": "report", "depth": "quick", "sources": ["web"]},
        ),
        CapabilityManifest(
            name="visualize",
            description="Generate SVG, Chart.js, or Mermaid visualizations.",
            stages=["analyzing", "generating", "reviewing"],
            tools_used=[],
            cli_aliases=["visualize", "viz"],
            request_schema=_schema(VisualizeRequestConfig),
        ),
        CapabilityManifest(
            name="math_animator",
            description="Generate math animations or storyboard images with Manim.",
            stages=[
                "concept_analysis",
                "concept_design",
                "code_generation",
                "code_retry",
                "summary",
                "render_output",
            ],
            tools_used=[],
            cli_aliases=["animate"],
            request_schema=_schema(MathAnimatorRequestConfig),
            config_defaults={
                "output_mode": "video",
                "quality": "medium",
                "style_hint": "",
            },
        ),
    ]


class CapabilityRegistry:
    """Registry of NG-supported built-in capabilities."""

    def __init__(self) -> None:
        self._manifests = {manifest.name: manifest for manifest in _builtins()}

    def list_capabilities(self) -> list[str]:
        return sorted(self._manifests)

    def get_manifests(self) -> list[dict[str, Any]]:
        return [self._manifests[name].to_dict() for name in self.list_capabilities()]

    def get_manifest(self, name: str) -> dict[str, Any] | None:
        manifest = self._manifests.get(name)
        return manifest.to_dict() if manifest else None


_capability_registry: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    """Return the shared NG capability registry."""
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry


class SparkWeaveApp:
    """Facade around NG runtime, session, notebook, and capability contracts."""

    def __init__(self) -> None:
        self.runtime = get_runtime_manager()
        self.store = get_sqlite_session_store()
        self.notebooks = get_notebook_manager()
        self.capabilities = get_capability_registry()

    def resolve_capability(self, value: str | None) -> str:
        requested = str(value or "chat").strip() or "chat"
        for manifest in self.capabilities.get_manifests():
            if manifest["name"] == requested:
                return requested
            aliases = {str(alias).strip() for alias in manifest.get("cli_aliases", [])}
            if requested in aliases:
                return str(manifest["name"])
        available = ", ".join(self.capabilities.list_capabilities())
        raise ValueError(f"Unknown capability `{requested}`. Available: {available}")

    def get_capability_contracts(self) -> list[dict[str, Any]]:
        return [
            {
                **manifest,
                "availability": self.get_capability_availability(manifest["name"]).__dict__,
            }
            for manifest in self.capabilities.get_manifests()
        ]

    def get_capability_contract(self, value: str) -> dict[str, Any]:
        resolved = self.resolve_capability(value)
        manifest = self.capabilities.get_manifest(resolved)
        if manifest is None:
            raise ValueError(f"Capability not found: {resolved}")
        return {
            **manifest,
            "availability": self.get_capability_availability(resolved).__dict__,
        }

    def get_capability_availability(self, capability: str) -> CapabilityAvailability:
        resolved = self.resolve_capability(capability)
        if resolved == "math_animator":
            available = importlib.util.find_spec("manim") is not None
            return CapabilityAvailability(
                name=resolved,
                available=available,
                install_hint=(
                    ""
                    if available
                    else "Install with `pip install sparkweave-cli[math-animator]` "
                    "or `pip install -r requirements/math-animator.txt`."
                ),
            )
        return CapabilityAvailability(name=resolved, available=True)

    async def start_turn(
        self,
        request: TurnRequest | dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if isinstance(request, dict):
            request = TurnRequest(**request)
        resolved_capability = self.resolve_capability(request.capability)
        session, turn = await self.runtime.start_turn(
            {
                **request.to_payload(),
                "capability": resolved_capability,
            }
        )
        await self.store.update_session_preferences(
            session["id"],
            {
                "language": request.language,
                "notebook_references": request.notebook_references,
                "history_references": request.history_references,
            },
        )
        return session, turn

    async def stream_turn(self, turn_id: str, after_seq: int = 0) -> AsyncIterator[dict[str, Any]]:
        async for item in self.runtime.subscribe_turn(turn_id, after_seq=after_seq):
            yield item

    async def cancel_turn(self, turn_id: str) -> bool:
        return await self.runtime.cancel_turn(turn_id)

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await self.store.list_sessions(limit=limit, offset=offset)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return await self.store.get_session_with_messages(session_id)

    async def rename_session(self, session_id: str, title: str) -> bool:
        return await self.store.update_session_title(session_id, title)

    async def delete_session(self, session_id: str) -> bool:
        return await self.store.delete_session(session_id)

    async def get_active_turn(self, session_id: str) -> dict[str, Any] | None:
        return await self.store.get_active_turn(session_id)

    def list_notebooks(self) -> list[dict[str, Any]]:
        return self.notebooks.list_notebooks()

    def create_notebook(
        self,
        name: str,
        description: str = "",
        *,
        color: str = "#3B82F6",
        icon: str = "book",
    ) -> dict[str, Any]:
        return self.notebooks.create_notebook(
            name=name,
            description=description,
            color=color,
            icon=icon,
        )

    def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        return self.notebooks.get_notebook(notebook_id)

    def add_record(self, **kwargs: Any) -> dict[str, Any]:
        return self.notebooks.add_record(**kwargs)

    def update_record(self, notebook_id: str, record_id: str, **kwargs: Any) -> dict[str, Any] | None:
        return self.notebooks.update_record(notebook_id, record_id, **kwargs)

    def remove_record(self, notebook_id: str, record_id: str) -> bool:
        return self.notebooks.remove_record(notebook_id, record_id)

    def get_records_by_references(self, notebook_references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.notebooks.get_records_by_references(notebook_references)

    def import_markdown_into_notebook(self, notebook_id: str, path: str | Path) -> dict[str, Any]:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {resolved_path}")
        content = resolved_path.read_text(encoding="utf-8")
        title = _extract_markdown_title(content, fallback=resolved_path.stem)
        metadata = {
            "source": "co_writer",
            "saved_via": "cli",
            "source_path": str(resolved_path),
            "source_hash": sha256(content.encode("utf-8")).hexdigest(),
            "imported_at": time.time(),
        }
        return self.notebooks.add_record(
            notebook_ids=[notebook_id],
            record_type=RecordType.CO_WRITER,
            title=title,
            summary="",
            user_query=title,
            output=content,
            metadata=metadata,
            kb_name=None,
        )

    def replace_markdown_record(
        self,
        notebook_id: str,
        record_id: str,
        path: str | Path,
    ) -> dict[str, Any]:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {resolved_path}")
        existing = self.notebooks.get_record(notebook_id, record_id)
        if existing is None:
            raise ValueError(f"Record not found: {record_id}")
        if str(existing.get("type", "")) != RecordType.CO_WRITER.value:
            raise ValueError("Only `co_writer` notebook records can be replaced from markdown.")

        content = resolved_path.read_text(encoding="utf-8")
        title = _extract_markdown_title(content, fallback=resolved_path.stem)
        updated = self.notebooks.update_record(
            notebook_id,
            record_id,
            title=title,
            user_query=title,
            output=content,
            metadata={
                "source": "co_writer",
                "saved_via": "cli",
                "source_path": str(resolved_path),
                "source_hash": sha256(content.encode("utf-8")).hexdigest(),
                "replaced_at": time.time(),
            },
            kb_name=None,
        )
        if updated is None:
            raise ValueError(f"Failed to update record: {record_id}")
        return updated


def _extract_markdown_title(content: str, *, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title
    return fallback.strip() or "Untitled"


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "CapabilityAvailability",
    "CapabilityManifest",
    "CapabilityRegistry",
    "SparkWeaveApp",
    "TurnRequest",
    "dumps_json",
    "get_capability_registry",
]

