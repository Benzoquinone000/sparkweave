"""NG research pipeline facade backed by ``DeepResearchGraph``."""

from __future__ import annotations

import asyncio
from datetime import datetime
import inspect
import json
from pathlib import Path
from typing import Any, Callable

from sparkweave.core.contracts import StreamBus, StreamEvent, StreamEventType, UnifiedContext
from sparkweave.graphs.deep_research import DeepResearchGraph
from sparkweave.tools.registry import get_tool_registry


class ResearchPipeline:
    """Compatibility facade for the older research-pipeline surface."""

    def __init__(
        self,
        config: dict[str, Any],
        api_key: str = "",
        base_url: str = "",
        api_version: str | None = None,
        research_id: str | None = None,
        kb_name: str | None = None,
        progress_callback: Callable[[dict[str, Any]], Any] | None = None,
        trace_callback: Callable[[dict[str, Any]], Any] | None = None,
        pre_confirmed_outline: list[dict[str, str]] | None = None,
    ) -> None:
        self.config = config
        if kb_name is not None:
            self.config.setdefault("rag", {})["kb_name"] = kb_name
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version or config.get("llm", {}).get("api_version")
        self.progress_callback = progress_callback
        self.trace_callback = trace_callback
        self.pre_confirmed_outline = pre_confirmed_outline
        self.input_topic: str | None = None
        self.optimized_topic: str | None = None
        self.research_id = research_id or f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        system_config = config.get("system", {}) or {}
        self.cache_dir = Path(
            system_config.get(
                "output_base_dir",
                "./data/user/workspace/chat/deep_research",
            )
        ) / self.research_id
        self.reports_dir = Path(
            system_config.get(
                "reports_dir",
                "./data/user/workspace/chat/deep_research/reports",
            )
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._stage_events: dict[str, list[dict[str, Any]]] = {
            "planning": [],
            "researching": [],
            "reporting": [],
        }

    async def run(self, topic: str) -> dict[str, Any]:
        """Run deep research through the NG LangGraph implementation."""
        self.input_topic = topic
        bus = StreamBus()
        events: list[StreamEvent] = []
        context = self._build_context(topic)

        collector = asyncio.create_task(self._collect_events(bus, events))
        try:
            state = await DeepResearchGraph().run(context, bus)
        finally:
            await bus.close()
            await collector

        report = self._extract_report(events, state)
        report_file = self.reports_dir / f"{self.research_id}.md"
        report_file.write_text(report, encoding="utf-8")
        metadata = self._result_metadata(events, state)
        metadata.setdefault("research_id", self.research_id)
        metadata.setdefault("topic", topic)
        metadata.setdefault("runtime", "langgraph")
        metadata.setdefault("completed_at", datetime.now().isoformat())
        metadata_file = self.reports_dir / f"{self.research_id}_metadata.json"
        metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "research_id": self.research_id,
            "topic": topic,
            "report": report,
            "final_report_path": str(report_file),
            "metadata": metadata,
        }

    def _build_context(self, topic: str) -> UnifiedContext:
        intent = self.config.get("intent", {}) or {}
        reporting = self.config.get("reporting", {}) or {}
        planning = self.config.get("planning", {}) or {}
        decompose = planning.get("decompose", {}) if isinstance(planning, dict) else {}
        kb_name = str((self.config.get("rag", {}) or {}).get("kb_name") or "").strip()
        overrides: dict[str, Any] = {
            "topic": topic,
            "mode": intent.get("mode") or reporting.get("mode") or reporting.get("style") or "report",
            "depth": intent.get("depth") or reporting.get("depth") or "standard",
            "sources": list(intent.get("sources") or []),
        }
        if decompose.get("initial_subtopics") is not None:
            overrides["manual_subtopics"] = decompose.get("initial_subtopics")
        if self.pre_confirmed_outline:
            overrides["confirmed_outline"] = self.pre_confirmed_outline

        return UnifiedContext(
            session_id=self.research_id,
            user_message=topic,
            active_capability="deep_research",
            enabled_tools=self._enabled_tools(),
            knowledge_bases=[kb_name] if kb_name else [],
            language=str((self.config.get("system", {}) or {}).get("language") or "en"),
            config_overrides=overrides,
            metadata={
                "api_key": self.api_key,
                "base_url": self.base_url,
                "api_version": self.api_version,
            },
        )

    def _enabled_tools(self) -> list[str]:
        researching = self.config.get("researching", {}) or {}
        configured = researching.get("enabled_tools")
        if isinstance(configured, list):
            return [str(tool) for tool in configured if str(tool).strip()]
        tools: list[str] = []
        if researching.get("enable_rag") or researching.get("enable_rag_hybrid"):
            tools.append("rag")
        if researching.get("enable_web_search"):
            tools.append("web_search")
        if researching.get("enable_paper_search"):
            tools.append("paper_search")
        if researching.get("enable_run_code"):
            tools.append("code_execution")
        return tools

    async def _collect_events(
        self,
        bus: StreamBus,
        events: list[StreamEvent],
    ) -> None:
        async for event in bus.subscribe():
            events.append(event)
            await self._forward_callback(self.progress_callback, self._progress_payload(event))
            await self._forward_callback(self.trace_callback, self._trace_payload(event))

    def _progress_payload(self, event: StreamEvent) -> dict[str, Any]:
        payload = event.to_dict()
        payload["research_id"] = self.research_id
        return payload

    def _trace_payload(self, event: StreamEvent) -> dict[str, Any]:
        payload = event.to_dict()
        payload["research_id"] = self.research_id
        payload["event"] = payload["type"]
        return payload

    @staticmethod
    async def _forward_callback(
        callback: Callable[[dict[str, Any]], Any] | None,
        payload: dict[str, Any],
    ) -> None:
        if callback is None:
            return
        result = callback(payload)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _extract_report(events: list[StreamEvent], state: dict[str, Any]) -> str:
        for event in reversed(events):
            if event.type == StreamEventType.RESULT:
                response = str(event.metadata.get("response") or event.metadata.get("report") or "")
                if response:
                    return response
        for key in ("report", "final_answer"):
            value = str(state.get(key) or "")
            if value:
                return value
        for event in reversed(events):
            if event.type == StreamEventType.CONTENT and event.content:
                return event.content
        return ""

    @staticmethod
    def _result_metadata(events: list[StreamEvent], state: dict[str, Any]) -> dict[str, Any]:
        for event in reversed(events):
            if event.type == StreamEventType.RESULT:
                nested = event.metadata.get("metadata")
                if isinstance(nested, dict):
                    return dict(nested)
                return dict(event.metadata)
        artifacts = state.get("artifacts")
        if isinstance(artifacts, dict) and isinstance(artifacts.get("research"), dict):
            return dict(artifacts["research"])
        return {}

    async def _call_tool(self, tool_type: str, query: str) -> str:
        """Call a research tool and return a JSON string result."""
        config = getattr(self, "config", {}) or {}
        if tool_type == "rag":
            kb_name = (config.get("rag", {}) or {}).get("kb_name")
            if not kb_name:
                return json.dumps(
                    {
                        "status": "skipped",
                        "reason": "no_kb_selected",
                        "tool": "rag",
                        "query": query,
                    },
                    ensure_ascii=False,
                )

        registry = get_tool_registry()
        if registry.get(tool_type) is None:
            return json.dumps(
                {
                    "status": "failed",
                    "reason": "unknown_tool",
                    "tool": tool_type,
                    "query": query,
                },
                ensure_ascii=False,
            )

        try:
            if tool_type == "rag":
                result = await registry.execute(
                    tool_type,
                    query=query,
                    kb_name=(config.get("rag", {}) or {}).get("kb_name"),
                )
            else:
                result = await registry.execute(tool_type, query=query)
            return json.dumps(
                {
                    "status": "success" if result.success else "failed",
                    "tool": tool_type,
                    "query": query,
                    "answer": result.content,
                    "metadata": result.metadata,
                    "sources": result.sources,
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {
                    "status": "failed",
                    "reason": "tool_error",
                    "tool": tool_type,
                    "query": query,
                    "error": str(exc),
                },
                ensure_ascii=False,
            )


__all__ = ["ResearchPipeline"]

