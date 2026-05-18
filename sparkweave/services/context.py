"""Context enrichment services owned by the NG runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
import re
from typing import Any

from sparkweave.core.contracts import StreamEvent, StreamEventType
from sparkweave.core.json import parse_json_response
from sparkweave.core.trace import (
    build_trace_metadata,
    derive_trace_metadata,
    merge_trace_metadata,
    new_call_id,
)
from sparkweave.services.llm import (
    get_llm_config,
    get_token_limit_kwargs,
)
from sparkweave.services.llm import (
    stream as llm_stream,
)
from sparkweave.services.session_store import SQLiteSessionStore

logger = logging.getLogger(__name__)

EventSink = Callable[[StreamEvent], Awaitable[None]]


def count_tokens(text: str) -> int:
    """Estimate token count with tiktoken when available."""
    if not text:
        return 0
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def clip_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def clean_thinking_tags(text: str) -> str:
    """Remove common model thinking tags from streamed outputs."""
    return re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL).strip()


def format_messages_as_transcript(messages: list[dict[str, Any]]) -> str:
    role_map = {"user": "User", "assistant": "Assistant", "system": "System"}
    lines: list[str] = []
    for item in messages:
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        role = role_map.get(str(item.get("role", "user")), "User")
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def build_history_text(history: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in history:
        role = str(item.get("role", "user"))
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        if role == "system":
            lines.append(f"Conversation summary:\n{content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"User: {content}")
    return "\n\n".join(lines)


@dataclass
class ContextBuildResult:
    conversation_history: list[dict[str, Any]]
    conversation_summary: str
    context_text: str
    events: list[StreamEvent]
    token_count: int
    budget: int


class ContextBuilder:
    """Construct bounded conversation history plus optional summary trace."""

    def __init__(
        self,
        store: SQLiteSessionStore,
        history_budget_ratio: float = 0.35,
        summary_target_ratio: float = 0.40,
    ) -> None:
        self.store = store
        self.history_budget_ratio = history_budget_ratio
        self.summary_target_ratio = summary_target_ratio

    def _history_budget(self, llm_config: Any) -> int:
        configured = int(getattr(llm_config, "max_tokens", 4096) or 4096)
        return max(256, int(configured * self.history_budget_ratio))

    def _summary_budget(self, budget: int) -> int:
        return max(96, int(budget * self.summary_target_ratio))

    def _recent_budget(self, budget: int) -> int:
        return max(128, budget - self._summary_budget(budget))

    def _build_history(self, summary: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        if summary.strip():
            history.append({"role": "system", "content": summary.strip()})
        history.extend(
            {"role": item.get("role", "user"), "content": str(item.get("content", "") or "")}
            for item in messages
            if item.get("role") in {"user", "assistant"}
            and str(item.get("content", "") or "").strip()
        )
        return history

    def _select_recent_messages(
        self,
        messages: list[dict[str, Any]],
        recent_budget: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        selected: list[dict[str, Any]] = []
        total = 0
        for item in reversed(messages):
            tokens = count_tokens(str(item.get("content", "") or ""))
            if selected and total + tokens > recent_budget:
                break
            selected.insert(0, item)
            total += tokens
        cutoff = len(messages) - len(selected)
        return messages[:cutoff], selected

    async def _append_event(
        self,
        events: list[StreamEvent],
        event: StreamEvent,
        on_event: EventSink | None,
    ) -> None:
        events.append(event)
        if on_event is not None:
            await on_event(event)

    async def _summarize(
        self,
        *,
        session_id: str,
        language: str,
        source_text: str,
        summary_budget: int,
        on_event: EventSink | None = None,
    ) -> tuple[str, list[StreamEvent]]:
        events: list[StreamEvent] = []
        if not source_text.strip():
            return "", events

        trace_meta = build_trace_metadata(
            call_id=new_call_id("context-summary"),
            phase="summarize_context",
            label="Summarize context",
            call_kind="llm_summarization",
            trace_id=session_id,
        )
        await self._append_event(
            events,
            StreamEvent(
                type=StreamEventType.STAGE_START,
                source="context_builder",
                stage="summarize_context",
                metadata=trace_meta,
            ),
            on_event,
        )

        system_prompt = (
            "Compress conversation history for future turns. Preserve factual context, "
            "user goals, constraints, decisions, unresolved questions, and capability switches. "
            "Keep the summary concise and faithful."
        )
        if language.lower().startswith("zh"):
            system_prompt = (
                "Compress the conversation history into concise Chinese context for future turns. "
                "Preserve user goals, constraints, decisions, unresolved questions, and key facts."
            )
        user_prompt = (
            f"Compress the following conversation history into <= {summary_budget} tokens.\n\n"
            f"{source_text}"
        )

        config = get_llm_config()
        chunks: list[str] = []
        try:
            async for chunk in llm_stream(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=getattr(config, "model", None),
                api_key=getattr(config, "api_key", None),
                base_url=getattr(config, "base_url", None),
                api_version=getattr(config, "api_version", None),
                binding=getattr(config, "binding", None),
                temperature=0.2,
                **get_token_limit_kwargs(getattr(config, "model", ""), summary_budget),
            ):
                chunks.append(chunk)
                await self._append_event(
                    events,
                    StreamEvent(
                        type=StreamEventType.CONTENT,
                        source="context_builder",
                        stage="summarize_context",
                        content=chunk,
                        metadata=merge_trace_metadata(trace_meta, {"trace_kind": "llm_chunk"}),
                    ),
                    on_event,
                )
            return clean_thinking_tags("".join(chunks)), events
        finally:
            await self._append_event(
                events,
                StreamEvent(
                    type=StreamEventType.STAGE_END,
                    source="context_builder",
                    stage="summarize_context",
                    metadata=trace_meta,
                ),
                on_event,
            )

    async def build(
        self,
        *,
        session_id: str,
        llm_config: Any,
        language: str = "en",
        on_event: EventSink | None = None,
    ) -> ContextBuildResult:
        session = await self.store.get_session(session_id)
        messages = await self.store.get_messages_for_context(session_id)
        budget = self._history_budget(llm_config)
        if session is None:
            return ContextBuildResult([], "", "", [], 0, budget)

        stored_summary = str(session.get("compressed_summary", "") or "").strip()
        summary_up_to_msg_id = int(session.get("summary_up_to_msg_id", 0) or 0)
        unsummarized = [
            item for item in messages if int(item.get("id", 0) or 0) > summary_up_to_msg_id
        ]

        current_history = self._build_history(stored_summary, unsummarized)
        current_text = build_history_text(current_history)
        current_tokens = count_tokens(current_text)
        if current_tokens <= budget:
            return ContextBuildResult(
                conversation_history=current_history,
                conversation_summary=stored_summary,
                context_text=current_text,
                events=[],
                token_count=current_tokens,
                budget=budget,
            )

        older, recent = self._select_recent_messages(unsummarized, self._recent_budget(budget))
        merge_parts: list[str] = []
        if stored_summary:
            merge_parts.append(f"Existing summary:\n{stored_summary}")
        older_text = format_messages_as_transcript(older)
        if older_text:
            merge_parts.append(f"Older turns to fold in:\n{older_text}")

        try:
            new_summary, events = await self._summarize(
                session_id=session_id,
                language=language,
                source_text="\n\n".join(merge_parts),
                summary_budget=self._summary_budget(budget),
                on_event=on_event,
            )
        except Exception:
            logger.exception("Context summarization failed")
            new_summary, events = stored_summary, []

        up_to_msg_id = summary_up_to_msg_id
        if older:
            up_to_msg_id = int(older[-1].get("id", 0) or 0)
        if new_summary:
            await self.store.update_summary(session_id, new_summary, up_to_msg_id)
            stored_summary = new_summary

        final_history = self._build_history(stored_summary, recent)
        while len(final_history) > 1 and count_tokens(build_history_text(final_history)) > budget:
            summary_prefix = 1 if final_history[0].get("role") == "system" else 0
            if len(final_history) <= summary_prefix + 1:
                break
            final_history.pop(summary_prefix)

        final_text = build_history_text(final_history)
        return ContextBuildResult(
            conversation_history=final_history,
            conversation_summary=stored_summary,
            context_text=final_text,
            events=events,
            token_count=count_tokens(final_text),
            budget=budget,
        )


class NotebookAnalysisAgent:
    """Analyze selected notebook/history records before the main capability runs."""

    def __init__(self, language: str = "en") -> None:
        self.language = "zh" if str(language or "en").lower().startswith("zh") else "en"
        self.llm_config = get_llm_config()
        self.model = getattr(self.llm_config, "model", None)
        self.api_key = getattr(self.llm_config, "api_key", None)
        self.base_url = getattr(self.llm_config, "base_url", None)
        self.api_version = getattr(self.llm_config, "api_version", None)
        self.binding = getattr(self.llm_config, "binding", None) or "openai"

    async def analyze(
        self,
        *,
        user_question: str,
        records: list[dict[str, Any]],
        emit: EventSink | None = None,
    ) -> str:
        if not records:
            return ""
        thinking = await self._stage_thinking(user_question, records, emit)
        selected = await self._stage_acting(user_question, thinking, records, emit)
        observation = await self._stage_observing(user_question, thinking, selected, emit)
        if emit is not None:
            await emit(
                StreamEvent(
                    type=StreamEventType.RESULT,
                    source="notebook_analysis",
                    metadata={
                        "observation": observation,
                        "selected_record_ids": [record.get("id", "") for record in selected],
                    },
                )
            )
        return observation

    async def _stream_text(
        self,
        *,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        emit: EventSink | None,
        event_type: StreamEventType,
        stage: str,
        trace_meta: dict[str, Any],
    ) -> str:
        chunks: list[str] = []
        async for chunk in llm_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            binding=self.binding,
            temperature=temperature,
            **self._token_kwargs(max_tokens),
        ):
            if not chunk:
                continue
            chunks.append(chunk)
            if emit is not None:
                await emit(
                    StreamEvent(
                        type=event_type,
                        source="notebook_analysis",
                        stage=stage,
                        content=chunk,
                        metadata=derive_trace_metadata(trace_meta, trace_kind="llm_chunk"),
                    )
                )
        return clean_thinking_tags("".join(chunks))

    async def _emit_stage(self, stage: str, metadata: dict[str, Any], emit: EventSink | None, *, start: bool) -> None:
        if emit is None:
            return
        await emit(
            StreamEvent(
                type=StreamEventType.STAGE_START if start else StreamEventType.STAGE_END,
                source="notebook_analysis",
                stage=stage,
                metadata=metadata,
            )
        )

    async def _stage_thinking(
        self,
        user_question: str,
        records: list[dict[str, Any]],
        emit: EventSink | None,
    ) -> str:
        trace_meta = build_trace_metadata(
            call_id=new_call_id("notebook-thinking"),
            phase="thinking",
            label="Notebook reasoning",
            call_kind="llm_reasoning",
            trace_id="notebook-thinking",
            trace_role="thought",
            trace_group="stage",
        )
        stage = "notebook_thinking"
        await self._emit_stage(stage, trace_meta, emit, start=True)
        try:
            return await self._stream_text(
                prompt=(
                    f"User question:\n{user_question.strip() or '(empty)'}\n\n"
                    f"Available notebook summaries:\n{self._summary_catalog(records)}\n\n"
                    "Reason about which saved records matter most."
                ),
                system_prompt=(
                    "Review the user question and notebook summaries. "
                    "Output internal reasoning only, not the final answer."
                ),
                max_tokens=900,
                temperature=0.2,
                emit=emit,
                event_type=StreamEventType.THINKING,
                stage=stage,
                trace_meta=trace_meta,
            )
        finally:
            await self._emit_stage(stage, trace_meta, emit, start=False)

    async def _stage_acting(
        self,
        user_question: str,
        thinking_text: str,
        records: list[dict[str, Any]],
        emit: EventSink | None,
    ) -> list[dict[str, Any]]:
        trace_meta = build_trace_metadata(
            call_id=new_call_id("notebook-acting"),
            phase="acting",
            label="Notebook selection",
            call_kind="tool_planning",
            trace_id="notebook-acting",
            trace_role="tool",
            trace_group="tool_call",
        )
        stage = "notebook_acting"
        await self._emit_stage(stage, trace_meta, emit, start=True)
        try:
            raw = await self._stream_text(
                prompt=(
                    f"User question:\n{user_question.strip() or '(empty)'}\n\n"
                    f"[Thinking]\n{thinking_text or '(empty)'}\n\n"
                    f"Available records:\n{self._summary_catalog(records)}\n\n"
                    "Return JSON only with selected_record_ids, up to 5 ids."
                ),
                system_prompt='Output JSON only: {"selected_record_ids": [up to 5 ids]}.',
                max_tokens=500,
                temperature=0.1,
                emit=None,
                event_type=StreamEventType.CONTENT,
                stage=stage,
                trace_meta=trace_meta,
            )
            payload = parse_json_response(raw, logger_instance=logger, fallback={})
            selected_ids = payload.get("selected_record_ids") if isinstance(payload, dict) else []
            if not isinstance(selected_ids, list):
                selected_ids = []
            record_map = {str(record.get("id", "")): record for record in records}
            selected: list[dict[str, Any]] = []
            seen: set[str] = set()
            for record_id in selected_ids:
                key = str(record_id or "").strip()
                if key and key in record_map and key not in seen:
                    selected.append(record_map[key])
                    seen.add(key)
                if len(selected) >= 5:
                    break
            if not selected:
                selected = records[: min(5, len(records))]
            if emit is not None:
                await emit(
                    StreamEvent(
                        type=StreamEventType.TOOL_CALL,
                        source="notebook_analysis",
                        stage=stage,
                        content="notebook_lookup",
                        metadata=derive_trace_metadata(
                            trace_meta,
                            trace_kind="tool_call",
                            args={"selected_record_ids": [r.get("id", "") for r in selected]},
                        ),
                    )
                )
                await emit(
                    StreamEvent(
                        type=StreamEventType.TOOL_RESULT,
                        source="notebook_analysis",
                        stage=stage,
                        content=self._tool_result_text(selected),
                        metadata=derive_trace_metadata(
                            trace_meta,
                            trace_kind="tool_result",
                            tool="notebook_lookup",
                        ),
                    )
                )
            return selected
        finally:
            await self._emit_stage(stage, trace_meta, emit, start=False)

    async def _stage_observing(
        self,
        user_question: str,
        thinking_text: str,
        selected_records: list[dict[str, Any]],
        emit: EventSink | None,
    ) -> str:
        trace_meta = build_trace_metadata(
            call_id=new_call_id("notebook-observing"),
            phase="observing",
            label="Notebook observation",
            call_kind="llm_observation",
            trace_id="notebook-observing",
            trace_role="observe",
            trace_group="stage",
        )
        stage = "notebook_observing"
        await self._emit_stage(stage, trace_meta, emit, start=True)
        try:
            return await self._stream_text(
                prompt=(
                    f"User question:\n{user_question.strip() or '(empty)'}\n\n"
                    f"[Thinking]\n{thinking_text or '(empty)'}\n\n"
                    f"[Detailed Records]\n{self._detailed_records(selected_records)}\n\n"
                    "Produce compact context for the main capability. Include relevant "
                    "history, reusable conclusions or drafts, and caveats."
                ),
                system_prompt=(
                    "Synthesize selected notebook records into a compact context note "
                    "for the main capability."
                ),
                max_tokens=1200,
                temperature=0.2,
                emit=emit,
                event_type=StreamEventType.OBSERVATION,
                stage=stage,
                trace_meta=trace_meta,
            )
        finally:
            await self._emit_stage(stage, trace_meta, emit, start=False)

    def _summary_catalog(self, records: list[dict[str, Any]]) -> str:
        lines = []
        for record in records:
            lines.append(
                " | ".join(
                    [
                        f"id={record.get('id', '')}",
                        f"notebook={record.get('notebook_name', '')}",
                        f"type={record.get('type', '')}",
                        f"title={clip_text(record.get('title', ''), 80)}",
                        f"summary={clip_text(record.get('summary', '') or record.get('title', ''), 240)}",
                    ]
                )
            )
        return "\n".join(lines) if lines else "(none)"

    def _detailed_records(self, records: list[dict[str, Any]]) -> str:
        blocks = []
        for record in records:
            blocks.append(
                "\n".join(
                    [
                        f"Record ID: {record.get('id', '')}",
                        f"Notebook: {record.get('notebook_name', '')}",
                        f"Title: {record.get('title', '')}",
                        f"Summary: {record.get('summary', '')}",
                        f"Content:\n{clip_text(record.get('output', ''), 2500)}",
                    ]
                )
            )
        return "\n\n".join(blocks) if blocks else "(none)"

    def _tool_result_text(self, records: list[dict[str, Any]]) -> str:
        blocks = []
        for record in records:
            blocks.append(
                "\n".join(
                    [
                        f"- {record.get('id', '')} | {record.get('notebook_name', '')} | {record.get('title', '')}",
                        clip_text(record.get("output", ""), 400),
                    ]
                )
            )
        return "\n\n".join(blocks) if blocks else "(none)"

    def _token_kwargs(self, max_tokens: int) -> dict[str, Any]:
        if not self.model:
            return {}
        return get_token_limit_kwargs(self.model, max_tokens)


__all__ = [
    "ContextBuildResult",
    "ContextBuilder",
    "NotebookAnalysisAgent",
    "build_history_text",
    "clean_thinking_tags",
    "count_tokens",
    "format_messages_as_transcript",
]

