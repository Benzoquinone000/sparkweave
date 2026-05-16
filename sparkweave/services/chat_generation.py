"""Legacy-shaped chat facade backed by the NG ChatGraph."""

from __future__ import annotations

import asyncio
from inspect import isawaitable
import time
from typing import Any, AsyncGenerator
import uuid

from sparkweave.core.contracts import StreamBus, StreamEvent, StreamEventType, UnifiedContext
from sparkweave.core.trace_bridge import stream_event_to_trace_payload
from sparkweave.graphs.chat import ChatGraph


class SessionManager:
    """Small in-memory fallback for sessions that predate the shared store."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(self, title: str = "New Chat", settings: dict[str, Any] | None = None) -> str:
        session_id = f"chat_{uuid.uuid4().hex[:12]}"
        now = time.time()
        self._sessions[session_id] = {
            "session_id": session_id,
            "title": title,
            "messages": [],
            "settings": dict(settings or {}),
            "created_at": now,
            "updated_at": now,
        }
        return session_id

    def add_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        sources: dict[str, Any] | None = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        message: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        if sources:
            message["sources"] = sources
        session.setdefault("messages", []).append(message)
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
            {key: value for key, value in session.items() if key != "messages"}
            for session in sessions
        ]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        return dict(session) if session is not None else None

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None


class ChatAgent:
    """Compatibility wrapper exposing the legacy chat-agent streaming API."""

    def __init__(
        self,
        *,
        language: str = "en",
        config: dict[str, Any] | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
    ) -> None:
        self.language = language
        self.config = dict(config or {})
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self._trace_callback = None

    def set_trace_callback(self, callback: Any) -> None:
        """Register a callback that receives structured trace events."""
        self._trace_callback = callback

    async def process(
        self,
        *,
        message: str,
        history: list[dict[str, Any]] | None = None,
        kb_name: str = "",
        enable_rag: bool = False,
        enable_web_search: bool = False,
        stream: bool = True,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Return a legacy-style async stream of chat chunks."""
        return self._stream_response(
            message=message,
            history=history or [],
            kb_name=kb_name,
            enable_rag=enable_rag,
            enable_web_search=enable_web_search,
            stream=stream,
        )

    async def _stream_response(
        self,
        *,
        message: str,
        history: list[dict[str, Any]],
        kb_name: str,
        enable_rag: bool,
        enable_web_search: bool,
        stream: bool,
    ) -> AsyncGenerator[dict[str, Any], None]:
        bus = StreamBus()
        rag_context, prefetched_rag_sources = await self._prefetch_rag_context(
            message=message,
            kb_name=kb_name,
            enabled=enable_rag,
        )
        sources = {"rag": list(prefetched_rag_sources), "web": []}
        full_response = ""
        memory_context = ""
        if rag_context:
            memory_context = (
                f"Retrieved knowledge base context from `{kb_name}`. "
                "Use it as grounded evidence when answering:\n\n"
                f"{rag_context}"
            )

        context = UnifiedContext(
            user_message=message,
            conversation_history=history,
            enabled_tools=self._enabled_tools(
                kb_name=kb_name,
                enable_rag=enable_rag,
                enable_web_search=enable_web_search,
            ),
            active_capability="chat",
            knowledge_bases=[kb_name] if enable_rag and kb_name else [],
            language=self.language,
            metadata={
                "api_key": self.api_key,
                "base_url": self.base_url,
                "api_version": self.api_version,
                "stream": stream,
                "prefetched_rag": bool(rag_context),
            },
            memory_context=memory_context,
        )

        async def _run_graph() -> None:
            try:
                await ChatGraph().run(context, bus)
            finally:
                await bus.close()

        task = asyncio.create_task(_run_graph())
        try:
            async for event in bus.subscribe():
                await self._forward_trace(event)
                if event.type == StreamEventType.CONTENT:
                    content = event.content
                    full_response += content
                    yield {"type": "chunk", "content": content}
                elif event.type == StreamEventType.SOURCES:
                    sources = self._merge_sources(
                        sources,
                        self._categorize_sources(event.metadata.get("sources", [])),
                    )
                elif event.type == StreamEventType.RESULT:
                    response = str(event.metadata.get("response") or "")
                    if response:
                        full_response = response
            await task
        except Exception:
            task.cancel()
            raise

        yield {
            "type": "complete",
            "response": full_response,
            "sources": self._dedupe_sources(sources),
        }

    async def _prefetch_rag_context(
        self,
        *,
        message: str,
        kb_name: str,
        enabled: bool,
    ) -> tuple[str, list[dict[str, Any]]]:
        if not enabled or not kb_name:
            return "", []
        try:
            from sparkweave.services.rag import rag_search

            result = await rag_search(query=message, kb_name=kb_name)
        except Exception:
            return "", []
        content = str(result.get("content") or result.get("answer") or "").strip()
        sources = self._normalize_rag_sources(
            result.get("sources"),
            kb_name=kb_name,
            query=message,
        )
        return content, sources

    async def _forward_trace(self, event: StreamEvent) -> None:
        if self._trace_callback is None:
            return
        try:
            result = self._trace_callback(stream_event_to_trace_payload(event))
            if isawaitable(result):
                await result
        except Exception:
            return

    @staticmethod
    def _enabled_tools(
        *,
        kb_name: str,
        enable_rag: bool,
        enable_web_search: bool,
    ) -> list[str]:
        tools: list[str] = []
        if enable_rag and kb_name:
            tools.append("rag")
        if enable_web_search:
            tools.append("web_search")
        return tools

    @staticmethod
    def _categorize_sources(raw_sources: Any) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {"rag": [], "web": []}
        if not isinstance(raw_sources, list):
            return grouped
        for source in raw_sources:
            if not isinstance(source, dict):
                continue
            source_type = str(source.get("type") or "").lower()
            if source_type == "web":
                grouped["web"].append(source)
            elif source_type == "rag":
                grouped["rag"].append(source)
            else:
                grouped["rag"].append({"type": "rag", **source})
        return grouped

    @staticmethod
    def _normalize_rag_sources(
        raw_sources: Any,
        *,
        kb_name: str,
        query: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_sources, list):
            return []
        normalized: list[dict[str, Any]] = []
        for source in raw_sources:
            if not isinstance(source, dict):
                continue
            normalized.append(
                {
                    "type": "rag",
                    "kb_name": kb_name,
                    "query": query,
                    **source,
                }
            )
        return normalized

    @classmethod
    def _merge_sources(
        cls,
        current: dict[str, list[dict[str, Any]]],
        incoming: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "rag": [*current.get("rag", []), *incoming.get("rag", [])],
            "web": [*current.get("web", []), *incoming.get("web", [])],
        }

    @classmethod
    def _dedupe_sources(cls, grouped: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        return {
            "rag": cls._dedupe_source_list(grouped.get("rag", [])),
            "web": cls._dedupe_source_list(grouped.get("web", [])),
        }

    @staticmethod
    def _dedupe_source_list(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for source in sources:
            key = str(
                source.get("chunk_id")
                or source.get("url")
                or source.get("source")
                or source.get("title")
                or source
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(source)
        return unique


__all__ = ["ChatAgent", "SessionManager"]

