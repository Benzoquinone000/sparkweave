"""Compatibility facade for question generation on top of the NG graph."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from pathlib import Path
from typing import Any

from sparkweave.core.contracts import StreamBus, StreamEvent, StreamEventType, UnifiedContext
from sparkweave.core.trace_bridge import stream_event_to_trace_payload
from sparkweave.graphs.deep_question import DeepQuestionGraph
from sparkweave.logging import get_logger
from sparkweave.services.config import PROJECT_ROOT, load_config_with_main

WsCallback = Callable[..., Any]


class _LoggerAdapter:
    """Expose ``.logger`` for legacy routers while using an NG logger."""

    def __init__(self, name: str) -> None:
        config = load_config_with_main("main.yaml", PROJECT_ROOT)
        log_dir = config.get("paths", {}).get("user_log_dir") or config.get(
            "logging", {}
        ).get("log_dir")
        self.logger = get_logger(name, log_dir=log_dir)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.logger, name)


class AgentCoordinator:
    """Drop-in coordinator facade backed by ``DeepQuestionGraph``."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        kb_name: str | None = None,
        output_dir: str | None = None,
        language: str = "en",
        tool_flags_override: dict[str, bool] | None = None,
        enable_idea_rag: bool = True,
    ) -> None:
        self.kb_name = kb_name
        self.output_dir = output_dir
        self.language = language
        self._api_key = api_key
        self._base_url = base_url
        self._api_version = api_version
        self.tool_flags = tool_flags_override or {}
        self.enable_idea_rag = enable_idea_rag
        self.logger = _LoggerAdapter("QuestionCoordinator")
        self._ws_callback: WsCallback | None = None
        self._trace_callback: WsCallback | None = None

    def set_ws_callback(self, callback: WsCallback) -> None:
        self._ws_callback = callback

    def set_trace_callback(self, callback: WsCallback | None) -> None:
        self._trace_callback = callback

    async def generate_from_topic(
        self,
        user_topic: str,
        preference: str,
        num_questions: int,
        difficulty: str = "",
        question_type: str = "",
        history_context: str = "",
    ) -> dict[str, Any]:
        """Generate questions from a topic through the NG deep-question graph."""
        return await self._run_graph(
            user_message=user_topic,
            history_context=history_context,
            config_overrides={
                "mode": "custom",
                "topic": user_topic,
                "preference": preference,
                "num_questions": num_questions,
                "difficulty": difficulty,
                "question_type": question_type,
                "output_dir": self.output_dir,
            },
        )

    async def generate_from_exam(
        self,
        exam_paper_path: str,
        max_questions: int = 10,
        paper_mode: str = "parsed",
    ) -> dict[str, Any]:
        """Generate mimic questions from a parsed exam directory, JSON, or PDF."""
        return await self._run_graph(
            user_message=f"Mimic questions from {Path(exam_paper_path).name}",
            config_overrides={
                "mode": "mimic",
                "paper_path": exam_paper_path,
                "max_questions": max_questions,
                "paper_mode": paper_mode,
                "output_dir": self.output_dir,
            },
        )

    async def _run_graph(
        self,
        *,
        user_message: str,
        config_overrides: dict[str, Any],
        history_context: str = "",
    ) -> dict[str, Any]:
        bus = StreamBus()
        events: list[StreamEvent] = []
        forward_task = asyncio.create_task(self._forward_events(bus, events))

        context = UnifiedContext(
            session_id="question_generation",
            user_message=user_message,
            active_capability="deep_question",
            knowledge_bases=[self.kb_name] if self.kb_name else [],
            enabled_tools=["rag"] if self.kb_name and self.enable_idea_rag else [],
            config_overrides=config_overrides,
            language=self.language,
            history_context=history_context,
            metadata={
                "api_key": self._api_key,
                "base_url": self._base_url,
                "api_version": self._api_version,
                "question_output_dir": self.output_dir,
            },
        )

        try:
            await DeepQuestionGraph().run(context, bus)
        finally:
            await bus.close()
            await forward_task

        summary = self._summary_from_events(events)
        if summary is not None:
            return summary
        return {
            "success": False,
            "source": config_overrides.get("mode", "custom"),
            "requested": config_overrides.get("num_questions")
            or config_overrides.get("max_questions")
            or 0,
            "template_count": 0,
            "completed": 0,
            "failed": 0,
            "results": [],
            "errors": ["Question graph did not return a summary."],
            "runtime": "langgraph",
        }

    async def _forward_events(
        self,
        bus: StreamBus,
        events: list[StreamEvent],
    ) -> None:
        async for event in bus.subscribe():
            events.append(event)
            await self._send_callback(self._ws_callback, self._event_to_update(event))
            await self._send_callback(self._trace_callback, stream_event_to_trace_payload(event))

    async def _send_callback(
        self,
        callback: WsCallback | None,
        update: dict[str, Any],
    ) -> None:
        if callback is None:
            return
        try:
            result = callback(update)
            if isawaitable(result):
                await result
        except Exception as exc:
            self.logger.debug("Question generation callback failed: %s", exc)

    @staticmethod
    def _event_to_update(event: StreamEvent) -> dict[str, Any]:
        event_type = event.type.value if isinstance(event.type, StreamEventType) else str(event.type)
        update: dict[str, Any] = {
            "type": event_type,
            "stage": event.stage,
            "source": event.source,
            "content": event.content,
            "metadata": event.metadata,
        }
        update.update(event.metadata)
        return update

    @staticmethod
    def _summary_from_events(events: list[StreamEvent]) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.type == StreamEventType.RESULT:
                summary = event.metadata.get("summary")
                if isinstance(summary, dict):
                    return summary
        return None


async def mimic_exam_questions(
    pdf_path: str | None = None,
    paper_dir: str | None = None,
    kb_name: str | None = None,
    output_dir: str | None = None,
    max_questions: int | None = None,
    ws_callback: Callable[[str, dict[str, Any]], Awaitable[Any] | Any] | None = None,
) -> dict[str, Any]:
    """Legacy-compatible mimic entrypoint backed by the NG graph."""
    if not pdf_path and not paper_dir:
        return {"success": False, "error": "Either pdf_path or paper_dir must be provided."}
    if pdf_path and paper_dir:
        return {"success": False, "error": "pdf_path and paper_dir cannot be used together."}

    coordinator = AgentCoordinator(kb_name=kb_name, output_dir=output_dir)
    if ws_callback is not None:

        async def _forward(update: dict[str, Any]) -> None:
            event_type = str(update.get("type") or "progress")
            result = ws_callback(event_type, update)
            if isawaitable(result):
                await result

        coordinator.set_ws_callback(_forward)

    summary = await coordinator.generate_from_exam(
        exam_paper_path=pdf_path or paper_dir or "",
        max_questions=max_questions or 10,
        paper_mode="upload" if pdf_path else "parsed",
    )

    results = summary.get("results", []) if isinstance(summary, dict) else []
    generated = [
        item.get("qa_pair", {})
        for item in results
        if isinstance(item, dict) and item.get("success", True)
    ]
    failed = [item for item in results if isinstance(item, dict) and not item.get("success", True)]
    return {
        "success": bool(summary.get("success", False)),
        "summary": summary,
        "generated_questions": generated,
        "failed_questions": failed,
        "total_reference_questions": summary.get("template_count", 0),
    }


__all__ = ["AgentCoordinator", "mimic_exam_questions"]

