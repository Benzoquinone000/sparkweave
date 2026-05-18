"""Legacy-shaped deep-solve facade backed by the NG DeepSolveGraph."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from inspect import isawaitable
from pathlib import Path
import time
from typing import Any
import uuid

from sparkweave.core.contracts import StreamBus, StreamEvent, StreamEventType, UnifiedContext
from sparkweave.core.trace_bridge import stream_event_to_trace_payload
from sparkweave.graphs.deep_solve import DeepSolveGraph
from sparkweave.logging import get_logger
from sparkweave.services.config import PROJECT_ROOT, load_config_with_main


@dataclass(frozen=True)
class CapabilityManifest:
    name: str
    description: str
    stages: list[str]
    tools_used: list[str]
    cli_aliases: list[str] = field(default_factory=list)
    request_schema: dict[str, Any] = field(default_factory=dict)


class DeepSolveCapability:
    """Minimal capability descriptor used by legacy solve routes."""

    manifest = CapabilityManifest(
        name="deep_solve",
        description="LangGraph problem solving.",
        stages=["planning", "reasoning", "writing"],
        tools_used=["rag", "web_search", "code_execution", "reason"],
        cli_aliases=["solve"],
    )


class _LoggerAdapter:
    def __init__(self, name: str) -> None:
        config = load_config_with_main("main.yaml", PROJECT_ROOT)
        log_dir = config.get("paths", {}).get("user_log_dir") or config.get(
            "logging", {}
        ).get("log_dir")
        self.logger = get_logger(name, log_dir=log_dir)
        self.display_manager = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.logger, name)


class SolverSessionManager:
    """Small in-memory fallback for pre-shared-store solve sessions."""

    DEFAULT_TOKEN_STATS = {
        "model": "Unknown",
        "calls": 0,
        "tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0.0,
    }

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(
        self,
        title: str | None = None,
        kb_name: str = "",
        token_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id = f"solve_{uuid.uuid4().hex[:12]}"
        now = time.time()
        session = {
            "session_id": session_id,
            "title": title or "New Solver Session",
            "messages": [],
            "kb_name": kb_name,
            "token_stats": token_stats or self.DEFAULT_TOKEN_STATS.copy(),
            "created_at": now,
            "updated_at": now,
        }
        self._sessions[session_id] = session
        return dict(session)

    def add_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        output_dir: str = "",
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.setdefault("messages", []).append(
            {
                "role": role,
                "content": content,
                "output_dir": output_dir,
                "timestamp": time.time(),
            }
        )
        session["updated_at"] = time.time()

    def update_token_stats(self, *, session_id: str, token_stats: dict[str, Any]) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session["token_stats"] = token_stats
            session["updated_at"] = time.time()

    def list_sessions(self, limit: int = 20, include_messages: bool = False) -> list[dict[str, Any]]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda item: float(item.get("updated_at", 0) or 0),
            reverse=True,
        )[:limit]
        if include_messages:
            return [dict(item) for item in sessions]
        return [
            {
                "session_id": session.get("session_id"),
                "title": session.get("title"),
                "message_count": len(session.get("messages", [])),
                "kb_name": session.get("kb_name"),
                "token_stats": session.get("token_stats"),
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at"),
                "last_message": (
                    str(session.get("messages", [{}])[-1].get("content", ""))[:100]
                    if session.get("messages")
                    else ""
                ),
            }
            for session in sessions
        ]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        return dict(session) if session is not None else None

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None


class MainSolver:
    """Compatibility wrapper exposing the legacy MainSolver surface."""

    def __init__(
        self,
        *,
        config_path: str | None = None,
        kb_name: str | None = None,
        output_base_dir: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        model: str | None = None,
        language: str = "en",
        enabled_tools: list[str] | None = None,
        disable_memory: bool = False,
        disable_planner_retrieve: bool = False,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.config_path = config_path
        self.kb_name = kb_name
        self.output_base_dir = output_base_dir
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.model = model
        self.language = language
        self.enabled_tools = list(enabled_tools or [])
        self.disable_memory = disable_memory
        self.disable_planner_retrieve = disable_planner_retrieve
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = _LoggerAdapter("MainSolver")
        self.token_tracker = None
        self._send_progress_update = None
        self._trace_callback = None

    async def ainit(self) -> None:
        return None

    def set_trace_callback(self, callback: Any) -> None:
        """Register a callback that receives structured trace events."""
        self._trace_callback = callback

    async def solve(
        self,
        question: str,
        verbose: bool = True,
        detailed: bool = False,
    ) -> dict[str, Any]:
        bus = StreamBus()
        events: list[StreamEvent] = []
        final_answer = ""

        context = UnifiedContext(
            user_message=question,
            active_capability="deep_solve",
            enabled_tools=self._effective_tools(),
            knowledge_bases=[self.kb_name] if self.kb_name else [],
            language=self.language,
            config_overrides={"detailed_answer": detailed, "verbose": verbose},
        metadata={
                "api_key": self.api_key,
                "base_url": self.base_url,
                "api_version": self.api_version,
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )

        forward_task = asyncio.create_task(self._collect_events(bus, events))
        try:
            await DeepSolveGraph().run(context, bus)
        finally:
            await bus.close()
            await forward_task

        for event in events:
            if event.type == StreamEventType.CONTENT:
                final_answer = event.content
            elif event.type == StreamEventType.RESULT:
                response = str(event.metadata.get("response") or "")
                if response:
                    final_answer = response

        output_dir = self._ensure_output_dir()
        result_metadata = self._result_metadata(events)
        result_metadata.setdefault("runtime", "langgraph")
        return {
            "final_answer": final_answer,
            "output_dir": output_dir,
            "metadata": result_metadata,
        }

    async def _collect_events(
        self,
        bus: StreamBus,
        events: list[StreamEvent],
    ) -> None:
        async for event in bus.subscribe():
            events.append(event)
            self._forward_progress(event)
            await self._forward_trace(event)

    def _forward_progress(self, event: StreamEvent) -> None:
        if event.type != StreamEventType.PROGRESS or self._send_progress_update is None:
            return
        try:
            self._send_progress_update(
                event.stage,
                {
                    "message": event.content,
                    **dict(event.metadata or {}),
                },
            )
        except Exception:
            self.logger.debug("Failed to forward solve progress", exc_info=True)

    async def _forward_trace(self, event: StreamEvent) -> None:
        callback = self._trace_callback
        if callback is None:
            return
        try:
            result = callback(stream_event_to_trace_payload(event))
            if isawaitable(result):
                await result
        except Exception:
            self.logger.debug("Failed to forward solve trace", exc_info=True)

    def _effective_tools(self) -> list[str]:
        tools = list(self.enabled_tools)
        if self.disable_planner_retrieve:
            tools = [tool for tool in tools if tool != "rag"]
        if "rag" in tools and not self.kb_name:
            tools = [tool for tool in tools if tool != "rag"]
        return tools

    def _ensure_output_dir(self) -> str:
        if not self.output_base_dir:
            return ""
        path = Path(self.output_base_dir) / f"ng_solve_{int(time.time() * 1000)}"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @staticmethod
    def _result_metadata(events: list[StreamEvent]) -> dict[str, Any]:
        for event in reversed(events):
            if event.type == StreamEventType.RESULT:
                return dict(event.metadata)
        return {}


__all__ = [
    "CapabilityManifest",
    "DeepSolveCapability",
    "MainSolver",
    "SolverSessionManager",
]

