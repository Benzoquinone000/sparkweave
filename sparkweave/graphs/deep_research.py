"""LangGraph implementation of SparkWeave's deep-research capability."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.core.dependencies import dependency_error
from sparkweave.core.state import TutorState, context_to_state, message_text
from sparkweave.graphs._answer_now import (
    answer_now_body,
    answer_now_metadata,
    answer_now_parts,
    answer_now_progress_metadata,
    answer_now_user_prompt,
    extract_answer_now_payload,
    skip_notice,
)
from sparkweave.llm import ainvoke_json as llm_ainvoke_json
from sparkweave.llm import chat_messages, create_chat_model
from sparkweave.services.paths import get_research_checkpoint_db_path
from sparkweave.tools import LangChainToolRegistry

RESEARCH_SYSTEM_PROMPT = """\
You are SparkWeave's research graph. Turn a learner's topic into a clear
research question, gather useful evidence from selected tools, and write a
grounded report. Be explicit about uncertainty when evidence is thin.
"""

SOURCE_TO_TOOL = {
    "kb": "rag",
    "web": "web_search",
    "papers": "paper_search",
}


class ResearchSubtopicPayload(BaseModel):
    title: str = Field(description="Short subtopic title.")
    overview: str = Field(default="", description="Why this subtopic matters.")
    queries: list[str] = Field(default_factory=list, description="Search queries.")


class ResearchDecomposePayload(BaseModel):
    subtopics: list[ResearchSubtopicPayload]


class DeepResearchGraph:
    """Explicit graph for rephrasing, decomposition, evidence, and reporting."""

    source = "deep_research"
    _runtime_refs: dict[str, dict[str, Any]] = {}

    def __init__(
        self,
        *,
        model: Any | None = None,
        tool_registry: LangChainToolRegistry | None = None,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry or LangChainToolRegistry()
        self._compiled: Any | None = None
        self._checkpointed_compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        state = context_to_state(
            context,
            stream=stream,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
        )
        payload = extract_answer_now_payload(context)
        if payload is not None:
            return await self._run_answer_now(state, payload)

        config = self._config(state)
        if self._is_checkpoint_resume(config):
            return await self._resume_from_checkpoint(state, config)
        if config["requires_outline_confirmation"]:
            return await self._run_checkpointed_outline_preview(state, config)

        graph = self.compile()
        return await graph.ainvoke(state)

    def compile(self) -> Any:
        if self._compiled is not None:
            return self._compiled
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise dependency_error("langgraph") from exc

        builder = StateGraph(TutorState)
        builder.add_node("rephrase", self._rephrase_node)
        builder.add_node("decompose", self._decompose_node)
        builder.add_node("preview_outline", self._preview_outline_node)
        builder.add_node("research", self._research_node)
        builder.add_node("report", self._report_node)

        builder.add_edge(START, "rephrase")
        builder.add_edge("rephrase", "decompose")
        builder.add_conditional_edges(
            "decompose",
            self._route_after_decompose,
            {"preview": "preview_outline", "research": "research"},
        )
        builder.add_edge("preview_outline", END)
        builder.add_edge("research", "report")
        builder.add_edge("report", END)
        self._compiled = builder.compile()
        return self._compiled

    def compile_checkpointed(self, checkpointer: Any) -> Any:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise dependency_error("langgraph checkpointing") from exc

        builder = StateGraph(TutorState)
        builder.add_node("rephrase", self._rephrase_node)
        builder.add_node("decompose", self._decompose_node)
        builder.add_node("preview_outline", self._preview_outline_node)
        builder.add_node("research", self._research_node)
        builder.add_node("report", self._report_node)

        builder.add_edge(START, "rephrase")
        builder.add_edge("rephrase", "decompose")
        builder.add_conditional_edges(
            "decompose",
            self._route_after_decompose,
            {"preview": "preview_outline", "research": "research"},
        )
        builder.add_edge("preview_outline", END)
        builder.add_edge("research", "report")
        builder.add_edge("report", END)
        return builder.compile(checkpointer=checkpointer)

    @asynccontextmanager
    async def _open_checkpointed_graph(self):
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError as exc:
            raise dependency_error("langgraph-checkpoint-sqlite") from exc

        db_path = self._checkpoint_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            yield self.compile_checkpointed(checkpointer)

    @staticmethod
    def _checkpoint_db_path():
        return get_research_checkpoint_db_path()

    @classmethod
    def _register_runtime(cls, runtime_key: str, state: TutorState) -> None:
        cls._runtime_refs[runtime_key] = {
            "context": state.get("context"),
            "stream": state.get("stream"),
        }

    @classmethod
    def _runtime_key(cls, checkpoint_id: str) -> str:
        return f"deep_research_runtime:{checkpoint_id}"

    @classmethod
    def _stream(cls, state: TutorState) -> StreamBus:
        stream = state.get("stream")
        if stream is not None:
            return stream
        runtime_key = str(state.get("runtime_key") or "")
        runtime = cls._runtime_refs.get(runtime_key, {})
        stream = runtime.get("stream")
        if stream is None:
            raise RuntimeError("Deep research runtime stream is not available.")
        return stream

    @classmethod
    def _context(cls, state: TutorState) -> UnifiedContext | None:
        context = state.get("context")
        if context is not None:
            return context
        runtime_key = str(state.get("runtime_key") or "")
        runtime = cls._runtime_refs.get(runtime_key, {})
        value = runtime.get("context")
        return value if hasattr(value, "config_overrides") else None

    @staticmethod
    def _checkpoint_state(state: TutorState, *, runtime_key: str) -> TutorState:
        checkpoint_state = dict(state)
        checkpoint_state.pop("stream", None)
        checkpoint_state.pop("context", None)
        checkpoint_state["runtime_key"] = runtime_key
        return checkpoint_state

    async def _rephrase_node(self, state: TutorState) -> dict[str, Any]:
        stream = self._stream(state)
        config = self._config(state)
        topic = config["topic"]
        async with stream.stage("rephrasing", source=self.source):
            await stream.progress(
                "Clarifying the research question...",
                source=self.source,
                stage="rephrasing",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=(
                    "Rewrite the learner's topic as one focused research question. "
                    "Keep it concise, neutral, and answerable."
                ),
                user=(
                    f"Topic: {topic}\n"
                    f"Mode: {config['mode']}\n"
                    f"Depth: {config['depth']}\n"
                    f"Language: {state.get('language', 'en')}"
                ),
            )
            refined = message_text(response).strip() or topic
            refined = self._strip_heading(refined) or topic
            await stream.thinking(
                refined,
                source=self.source,
                stage="rephrasing",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="rephrasing",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"research_topic": refined}

    async def _decompose_node(self, state: TutorState) -> dict[str, Any]:
        stream = self._stream(state)
        config = self._config(state)
        topic = state.get("research_topic") or config["topic"]

        async with stream.stage("decomposing", source=self.source):
            outline = self._outline_from_config(config, topic)
            if outline:
                await stream.thinking(
                    self._format_subtopics(outline),
                    source=self.source,
                    stage="decomposing",
                    metadata={"trace_kind": "outline", "outline_source": "config"},
                )
                return {"subtopics": outline}

            await stream.progress(
                "Breaking the topic into research subtopics...",
                source=self.source,
                stage="decomposing",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            count = config["subtopic_count"]
            payload = await self._ainvoke_json(
                system=(
                    "Decompose the research question into focused subtopics. "
                    "Return JSON only. Each subtopic needs a title, overview, "
                    "and 1-3 practical search queries."
                ),
                user=(
                    f"Research question: {topic}\n"
                    f"Number of subtopics: {count}\n"
                    f"Mode: {config['mode']}\n"
                    f"Sources: {', '.join(config['sources']) or 'none'}\n\n"
                    'Return JSON: {"subtopics": [{"title": "...", '
                    '"overview": "...", "queries": ["..."]}]}'
                ),
                schema=ResearchDecomposePayload,
            )
            subtopics = self._normalize_subtopics(
                payload.get("subtopics", []),
                topic=topic,
                count=count,
            )
            await stream.thinking(
                self._format_subtopics(subtopics),
                source=self.source,
                stage="decomposing",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="decomposing",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"subtopics": subtopics}

    async def _preview_outline_node(self, state: TutorState) -> dict[str, Any]:
        stream = self._stream(state)
        config = self._config(state)
        topic = state.get("research_topic") or config["topic"]
        subtopics = state.get("subtopics", []) or []

        async with stream.stage("decomposing", source=self.source):
            return await self._emit_outline_preview(
                state,
                config,
                topic=topic,
                subtopics=subtopics,
            )

    async def _run_checkpointed_outline_preview(
        self,
        state: TutorState,
        config: dict[str, Any],
    ) -> TutorState:
        checkpoint_id = self._checkpoint_id(state, config)
        runtime_key = self._runtime_key(checkpoint_id)
        self._register_runtime(runtime_key, state)
        checkpoint_state = self._checkpoint_state(state, runtime_key=runtime_key)
        thread_config = self._thread_config(checkpoint_id)
        checkpoint_state["artifacts"] = {
            **dict(checkpoint_state.get("artifacts", {}) or {}),
            "deep_research_checkpoint": {
                "checkpoint_id": checkpoint_id,
                "status": "pending_outline_confirmation",
            },
        }

        async with self._open_checkpointed_graph() as graph:
            await graph.ainvoke(
                checkpoint_state,
                config=thread_config,
                interrupt_after=["decompose"],
            )
            snapshot = await graph.aget_state(thread_config)
        values = dict(snapshot.values or {})
        topic = str(values.get("research_topic") or config["topic"])
        subtopics = list(values.get("subtopics", []) or [])

        async with self._stream(values).stage("decomposing", source=self.source):
            updates = await self._emit_outline_preview(
                values,
                config,
                topic=topic,
                subtopics=subtopics,
                checkpoint_id=checkpoint_id,
            )
        values.update(updates)
        return values

    async def _resume_from_checkpoint(
        self,
        state: TutorState,
        config: dict[str, Any],
    ) -> TutorState:
        checkpoint_id = str(config.get("checkpoint_id") or "").strip()
        self._register_runtime(self._runtime_key(checkpoint_id), state)
        thread_config = self._thread_config(checkpoint_id)
        async with self._open_checkpointed_graph() as graph:
            snapshot = await graph.aget_state(thread_config)
            if not snapshot.values:
                await self._stream(state).error(
                    f"Deep research checkpoint not found: {checkpoint_id}",
                    source=self.source,
                    stage="researching",
                )
                state["errors"] = [f"checkpoint_not_found:{checkpoint_id}"]
                return state

            saved = dict(snapshot.values or {})
            topic = str(saved.get("research_topic") or config["topic"])
            confirmed_subtopics = self._outline_from_config(config, topic)
            if not confirmed_subtopics:
                await self._stream(state).error(
                    "A confirmed_outline is required to resume deep research from a checkpoint.",
                    source=self.source,
                    stage="researching",
                )
                state["errors"] = ["confirmed_outline_required"]
                return state

            await graph.aupdate_state(
                thread_config,
                {
                    "runtime_key": self._runtime_key(checkpoint_id),
                    "session_id": state.get("session_id", ""),
                    "turn_id": state.get("turn_id", ""),
                    "language": state.get("language", "en"),
                    "enabled_tools": list(state.get("enabled_tools") or []),
                    "knowledge_bases": list(state.get("knowledge_bases") or []),
                    "subtopics": confirmed_subtopics,
                    "artifacts": {
                        **dict(saved.get("artifacts", {}) or {}),
                        "deep_research_checkpoint": {
                            "checkpoint_id": checkpoint_id,
                            "status": "resumed",
                        },
                    },
                },
                as_node="decompose",
            )
            resumed = await graph.ainvoke(None, config=thread_config)
        return dict(resumed or {})

    async def _emit_outline_preview(
        self,
        state: TutorState,
        config: dict[str, Any],
        *,
        topic: str,
        subtopics: list[dict[str, Any]],
        checkpoint_id: str = "",
    ) -> dict[str, Any]:
        stream = self._stream(state)
        outline_md = self._outline_to_markdown(topic, subtopics)
        payload: dict[str, Any] = {
            "outline_preview": True,
            "sub_topics": self._preview_subtopics(subtopics),
            "topic": topic,
            "research_config": self._research_config_payload(config),
            "runtime": "langgraph",
        }
        if checkpoint_id:
            payload.update(
                {
                    "checkpoint_id": checkpoint_id,
                    "checkpoint": {
                        "id": checkpoint_id,
                        "thread_id": checkpoint_id,
                        "resume_config_key": "checkpoint_id",
                        "next": "researching",
                    },
                }
            )
        await stream.content(outline_md, source=self.source, stage="decomposing")
        await stream.result(payload, source=self.source)
        return {
            "final_answer": outline_md,
            "artifacts": {
                "research": {
                    "outline_preview": True,
                    "subtopics": subtopics,
                    "topic": topic,
                    "runtime": "langgraph",
                    **({"checkpoint_id": checkpoint_id} if checkpoint_id else {}),
                }
            },
        }

    async def _research_node(self, state: TutorState) -> dict[str, Any]:
        stream = self._stream(state)
        config = self._config(state)
        enabled_tools = self._enabled_tool_names(state)
        available_sources = self._available_sources(config, enabled_tools, state)
        evidence: list[dict[str, Any]] = []

        async with stream.stage("researching", source=self.source):
            if "kb" in config["sources"] and "kb" not in available_sources:
                await stream.progress(
                    "Knowledge base source was selected, but no knowledge base is attached or RAG is disabled.",
                    source=self.source,
                    stage="researching",
                    metadata={"trace_kind": "warning", "reason": "kb_unavailable"},
                )
            if not available_sources:
                await stream.progress(
                    "No external research source is available; drafting from the model's internal knowledge.",
                    source=self.source,
                    stage="researching",
                    metadata={"trace_kind": "warning", "reason": "no_sources"},
                )
                return {"evidence": evidence}

            subtopics = state.get("subtopics", []) or []
            total = max(1, len(subtopics) * len(available_sources))
            current = 0
            for subtopic in subtopics:
                title = str(subtopic.get("title") or state.get("research_topic") or "").strip()
                queries = self._queries_for_subtopic(subtopic, config)
                for source in available_sources:
                    current += 1
                    tool_name = SOURCE_TO_TOOL[source]
                    query = self._query_for_source(queries, source, title)
                    await stream.progress(
                        f"Searching {source}: {title}",
                        current=current,
                        total=total,
                        source=self.source,
                        stage="researching",
                        metadata={
                            "trace_kind": "call_status",
                            "call_state": "running",
                            "research_source": source,
                            "subtopic": title,
                        },
                    )
                    record = await self._execute_source_tool(
                        tool_name=tool_name,
                        source=source,
                        query=query,
                        subtopic=title,
                        call_index=current,
                        state=state,
                        stream=stream,
                    )
                    evidence.append(record)

            if self._should_run_code(config, enabled_tools):
                record = await self._execute_code_tool(state, stream)
                evidence.append(record)
        return {"evidence": evidence}

    async def _report_node(self, state: TutorState) -> dict[str, Any]:
        stream = self._stream(state)
        config = self._config(state)
        topic = state.get("research_topic") or config["topic"]
        async with stream.stage("reporting", source=self.source):
            await stream.progress(
                "Drafting the research report...",
                source=self.source,
                stage="reporting",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=(
                    "Write the final research output for the learner. Use Markdown. "
                    "Ground claims in the evidence when it exists. If evidence is "
                    "missing or weak, say so directly. Do not mention internal graph "
                    "nodes or implementation details."
                ),
                user=(
                    f"Research question:\n{topic}\n\n"
                    f"Mode: {config['mode']}\n"
                    f"Depth: {config['depth']}\n"
                    f"Subtopics:\n{self._format_subtopics(state.get('subtopics', []))}\n\n"
                    f"Evidence:\n{self._format_evidence(state.get('evidence', []))}"
                ),
            )
            report = message_text(response).strip()
            if not report:
                report = self._fallback_report(
                    topic, state.get("subtopics", []), state.get("evidence", [])
                )
            sources = self._collect_sources(state.get("evidence", []))
            if sources:
                await stream.sources(sources, source=self.source, stage="reporting")
            await stream.content(report, source=self.source, stage="reporting")
            await stream.progress(
                "",
                source=self.source,
                stage="reporting",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )

            metadata = {
                "topic": topic,
                "mode": config["mode"],
                "depth": config["depth"],
                "sources": config["sources"],
                "subtopics": state.get("subtopics", []),
                "evidence": state.get("evidence", []),
                "runtime": "langgraph",
                "outline_preview": False,
            }
            if config.get("checkpoint_id"):
                metadata["checkpoint_id"] = config["checkpoint_id"]
            await stream.result(
                {
                    "response": report,
                    "report": report,
                    "metadata": metadata,
                    "runtime": "langgraph",
                },
                source=self.source,
            )
        return {
            "final_answer": report,
            "report": report,
            "artifacts": {"research": metadata},
        }

    async def _run_answer_now(
        self,
        state: TutorState,
        payload: dict[str, Any],
    ) -> TutorState:
        stream = self._stream(state)
        config = self._config(state)
        original, partial, trace_summary = answer_now_parts(state, payload)
        notice = skip_notice(
            capability=self.source,
            stages_skipped=["rephrasing", "decomposing", "researching"],
        )

        async with stream.stage("reporting", source=self.source):
            await stream.progress(
                "Writing report from the partial research trace...",
                source=self.source,
                stage="reporting",
                metadata=answer_now_progress_metadata("running"),
            )
            response = await self._ainvoke(
                system=(
                    "You are SparkWeave's research-report writer. The user is "
                    "waiting, so produce a structured Markdown report right now "
                    "from the evidence and notes already present in the partial "
                    "trace. Do not retrieve more evidence and do not call tools. "
                    "If coverage is thin, say so explicitly."
                ),
                user=answer_now_user_prompt(
                    original=original or config["topic"],
                    original_label="Research topic",
                    partial=partial,
                    trace_summary=trace_summary,
                    trace_label="Research Trace",
                    extra_context=(
                        f"Mode: {config['mode']}\n"
                        f"Depth: {config['depth']}\n"
                        f"Sources requested: {', '.join(config['sources']) or 'none'}"
                    ),
                    final_instruction=(
                        "Produce the final research report from this material now."
                    ),
                ),
            )
            report = message_text(response).strip()
            if not report:
                report = partial or self._fallback_report(original, [], [])
            body = answer_now_body(report, notice=notice)
            await stream.content(body, source=self.source, stage="reporting")
            await stream.progress(
                "",
                source=self.source,
                stage="reporting",
                metadata=answer_now_progress_metadata("complete"),
            )
            metadata = answer_now_metadata(
                topic=original or config["topic"],
                mode=config["mode"],
                depth=config["depth"],
                sources=config["sources"],
                runtime="langgraph",
                outline_preview=False,
            )
            await stream.result(
                {
                    "response": body,
                    "report": body,
                    "metadata": metadata,
                    "runtime": "langgraph",
                },
                source=self.source,
            )

        state["user_message"] = original
        state["research_topic"] = original or config["topic"]
        state["report"] = body
        state["final_answer"] = body
        state["artifacts"] = {"research": metadata}
        return state

    async def _ainvoke(self, *, system: str, user: str) -> Any:
        return await self._get_model().ainvoke(chat_messages(system=system, user=user))

    async def _ainvoke_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        return await llm_ainvoke_json(
            self._get_model(),
            system=system,
            user=user,
            schema=schema,
        )

    def _get_model(self) -> Any:
        if self.model is not None:
            return self.model
        self.model = create_chat_model(temperature=0.2)
        return self.model

    def _config(self, state: TutorState) -> dict[str, Any]:
        context = self._context(state)
        overrides = dict(getattr(context, "config_overrides", {}) or {})
        overrides.pop("_runtime", None)
        topic = str(overrides.get("topic") or state.get("user_message") or "").strip()
        mode = self._normalize_choice(
            overrides.get("mode", "report"),
            allowed={"notes", "report", "comparison", "learning_path"},
            default="report",
        )
        depth = self._normalize_choice(
            overrides.get("depth", "standard"),
            allowed={"quick", "standard", "deep", "manual"},
            default="standard",
        )
        manual_subtopics = self._coerce_int(overrides.get("manual_subtopics"))
        if manual_subtopics is None:
            manual_subtopics = self._coerce_int(overrides.get("num_subtopics"))
        subtopic_count = self._subtopic_count(depth, manual_subtopics)
        return {
            "topic": topic,
            "mode": mode,
            "depth": depth,
            "sources": self._normalize_sources(overrides.get("sources"), state),
            "manual_subtopics": manual_subtopics,
            "manual_max_iterations": self._coerce_int(overrides.get("manual_max_iterations")),
            "confirmed_outline": overrides.get("confirmed_outline"),
            "subtopics_override": overrides.get("subtopics"),
            "subtopic_count": subtopic_count,
            "use_code": bool(overrides.get("use_code", False)),
            "requires_outline_confirmation": self._requires_outline_confirmation(overrides),
            "checkpoint_id": str(
                overrides.get("checkpoint_id")
                or overrides.get("checkpoint_thread_id")
                or ""
            ).strip(),
        }

    @staticmethod
    def _is_checkpoint_resume(config: dict[str, Any]) -> bool:
        return bool(config.get("checkpoint_id") and config.get("confirmed_outline"))

    @staticmethod
    def _thread_config(checkpoint_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": checkpoint_id}}

    @staticmethod
    def _checkpoint_id(state: TutorState, config: dict[str, Any]) -> str:
        existing = str(config.get("checkpoint_id") or "").strip()
        if existing:
            return existing
        turn_id = str(state.get("turn_id") or "").strip()
        session_id = str(state.get("session_id") or "").strip()
        if session_id and turn_id:
            return f"deep_research:{session_id}:{turn_id}"
        if session_id:
            return f"deep_research:{session_id}:{uuid.uuid4().hex}"
        return f"deep_research:{uuid.uuid4().hex}"

    def _route_after_decompose(self, state: TutorState) -> str:
        config = self._config(state)
        return "preview" if config["requires_outline_confirmation"] else "research"

    def _normalize_sources(self, raw_sources: Any, state: TutorState) -> list[str]:
        if isinstance(raw_sources, str):
            raw = [item.strip() for item in raw_sources.split(",")]
        elif isinstance(raw_sources, list):
            raw = [str(item).strip() for item in raw_sources]
        else:
            raw = self._default_sources(state)

        normalized: list[str] = []
        for item in raw:
            lowered = item.lower()
            if lowered in {"paper", "academic", "arxiv"}:
                lowered = "papers"
            if lowered in SOURCE_TO_TOOL and lowered not in normalized:
                normalized.append(lowered)
        return normalized

    def _default_sources(self, state: TutorState) -> list[str]:
        enabled_tools = set(self._enabled_tool_names(state))
        sources: list[str] = []
        if "rag" in enabled_tools and state.get("knowledge_bases"):
            sources.append("kb")
        if "web_search" in enabled_tools:
            sources.append("web")
        if "paper_search" in enabled_tools:
            sources.append("papers")
        return sources

    def _enabled_tool_names(self, state: TutorState) -> list[str]:
        known = set(self.tool_registry.names())
        context = self._context(state)
        if context is not None and context.enabled_tools is None:
            requested = {"rag", "web_search", "paper_search", "code_execution"}
        else:
            requested = set(state.get("enabled_tools") or [])
        return sorted(name for name in requested if name in known)

    @staticmethod
    def _available_sources(
        config: dict[str, Any],
        enabled_tools: list[str],
        state: TutorState,
    ) -> list[str]:
        enabled = set(enabled_tools)
        available: list[str] = []
        for source in config["sources"]:
            tool_name = SOURCE_TO_TOOL[source]
            if tool_name not in enabled:
                continue
            if source == "kb" and not state.get("knowledge_bases"):
                continue
            available.append(source)
        return available

    @staticmethod
    def _outline_from_config(
        config: dict[str, Any],
        topic: str,
    ) -> list[dict[str, Any]]:
        raw = config.get("confirmed_outline") or config.get("subtopics_override")
        if not raw:
            return []
        if isinstance(raw, str):
            raw_items = [item.strip() for item in raw.splitlines() if item.strip()]
            raw = [{"title": item, "overview": ""} for item in raw_items]
        if not isinstance(raw, list):
            return []
        return DeepResearchGraph._normalize_subtopics(
            raw,
            topic=topic,
            count=max(1, len(raw)),
        )

    @staticmethod
    def _normalize_subtopics(
        raw_subtopics: Any,
        *,
        topic: str,
        count: int,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_subtopics, list):
            raw_subtopics = []
        subtopics: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_subtopics:
            if isinstance(item, BaseModel):
                item = item.model_dump()
            if isinstance(item, str):
                item = {"title": item, "overview": "", "queries": [item]}
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("sub_topic") or "").strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            overview = str(item.get("overview") or item.get("description") or "").strip()
            queries = item.get("queries") or item.get("search_queries") or []
            if isinstance(queries, str):
                queries = [queries]
            clean_queries = [str(query).strip() for query in queries if str(query).strip()]
            if not clean_queries:
                clean_queries = [f"{topic} {title}".strip()]
            subtopics.append(
                {
                    "title": title,
                    "overview": overview,
                    "queries": clean_queries[:3],
                }
            )
            if len(subtopics) >= count:
                break

        while len(subtopics) < count:
            index = len(subtopics) + 1
            title = f"{topic} - aspect {index}".strip(" -")
            subtopics.append(
                {
                    "title": title,
                    "overview": "Fallback subtopic generated by LangGraph runtime.",
                    "queries": [topic],
                }
            )
        return subtopics

    async def _execute_source_tool(
        self,
        *,
        tool_name: str,
        source: str,
        query: str,
        subtopic: str,
        call_index: int,
        state: TutorState,
        stream: StreamBus,
    ) -> dict[str, Any]:
        args = self._tool_args(tool_name, query, state)
        call_id = f"research-{source}-{call_index}"
        await stream.tool_call(
            tool_name=tool_name,
            args=args,
            source=self.source,
            stage="researching",
            metadata={
                "trace_kind": "tool_call",
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "research_source": source,
                "subtopic": subtopic,
            },
        )
        try:
            result = await self.tool_registry.execute(tool_name, **args)
            content = result.content or "(empty tool result)"
            success = result.success
            sources = result.sources
            metadata = result.metadata
        except Exception as exc:
            content = f"Error executing {tool_name}: {exc}"
            success = False
            sources = []
            metadata = {"error": str(exc)}

        await stream.tool_result(
            tool_name=tool_name,
            result=content,
            source=self.source,
            stage="researching",
            metadata={
                "trace_kind": "tool_result",
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "research_source": source,
                "subtopic": subtopic,
                "success": success,
                "sources": sources,
            },
        )
        return {
            "id": call_id,
            "source": source,
            "tool": tool_name,
            "subtopic": subtopic,
            "query": query,
            "arguments": args,
            "result": content,
            "success": success,
            "sources": sources,
            "metadata": metadata,
        }

    async def _execute_code_tool(
        self,
        state: TutorState,
        stream: StreamBus,
    ) -> dict[str, Any]:
        topic = state.get("research_topic") or state.get("user_message", "")
        intent = (
            "Compute or verify any quantitative comparison that would materially "
            f"improve this research report: {topic}"
        )
        args = {
            "intent": intent,
            "timeout": 30,
            "session_id": state.get("session_id", ""),
            "turn_id": state.get("turn_id", ""),
            "feature": "deep_research",
        }
        call_id = "research-code-1"
        await stream.tool_call(
            tool_name="code_execution",
            args=args,
            source=self.source,
            stage="researching",
            metadata={"trace_kind": "tool_call", "tool_call_id": call_id},
        )
        try:
            result = await self.tool_registry.execute("code_execution", **args)
            content = result.content or "(empty tool result)"
            success = result.success
            sources = result.sources
            metadata = result.metadata
        except Exception as exc:
            content = f"Error executing code_execution: {exc}"
            success = False
            sources = []
            metadata = {"error": str(exc)}
        await stream.tool_result(
            tool_name="code_execution",
            result=content,
            source=self.source,
            stage="researching",
            metadata={
                "trace_kind": "tool_result",
                "tool_call_id": call_id,
                "success": success,
                "sources": sources,
            },
        )
        return {
            "id": call_id,
            "source": "code",
            "tool": "code_execution",
            "subtopic": "quantitative verification",
            "query": intent,
            "arguments": args,
            "result": content,
            "success": success,
            "sources": sources,
            "metadata": metadata,
        }

    @staticmethod
    def _tool_args(tool_name: str, query: str, state: TutorState) -> dict[str, Any]:
        if tool_name == "rag":
            knowledge_bases = state.get("knowledge_bases", [])
            kb_name = knowledge_bases[0] if knowledge_bases else ""
            return {"query": query, "kb_name": kb_name}
        if tool_name == "paper_search":
            return {"query": query, "max_results": 3, "sort_by": "relevance"}
        return {"query": query}

    @staticmethod
    def _queries_for_subtopic(
        subtopic: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        queries = subtopic.get("queries") or []
        if isinstance(queries, str):
            queries = [queries]
        clean = [str(query).strip() for query in queries if str(query).strip()]
        limit = 1 if config["depth"] == "quick" else 2 if config["depth"] == "standard" else 3
        return clean[:limit] or [str(subtopic.get("title") or config["topic"])]

    @staticmethod
    def _query_for_source(queries: list[str], source: str, title: str) -> str:
        if not queries:
            return title
        if source == "papers" and len(queries) > 1:
            return queries[-1]
        return queries[0]

    @staticmethod
    def _should_run_code(config: dict[str, Any], enabled_tools: list[str]) -> bool:
        return "code_execution" in enabled_tools and (
            config["use_code"] or (config["mode"] == "comparison" and config["depth"] == "deep")
        )

    @staticmethod
    def _format_subtopics(subtopics: list[dict[str, Any]]) -> str:
        if not subtopics:
            return "(none)"
        lines: list[str] = []
        for index, item in enumerate(subtopics, 1):
            title = str(item.get("title") or "").strip()
            overview = str(item.get("overview") or "").strip()
            lines.append(f"{index}. {title}")
            if overview:
                lines.append(f"   {overview}")
        return "\n".join(lines)

    @staticmethod
    def _outline_to_markdown(topic: str, subtopics: list[dict[str, Any]]) -> str:
        lines = [f"**Research Outline - {topic}**", ""]
        for index, item in enumerate(subtopics, 1):
            title = str(item.get("title") or "").strip()
            overview = str(item.get("overview") or "").strip()
            lines.append(f"{index}. **{title}**")
            if overview:
                lines.append(f"   {overview}")
        return "\n".join(lines).strip()

    @staticmethod
    def _preview_subtopics(subtopics: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "title": str(item.get("title") or "").strip(),
                "overview": str(item.get("overview") or "").strip(),
            }
            for item in subtopics
            if str(item.get("title") or "").strip()
        ]

    @staticmethod
    def _research_config_payload(config: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": config["mode"],
            "depth": config["depth"],
            "sources": list(config["sources"]),
        }
        if config.get("manual_subtopics") is not None:
            payload["manual_subtopics"] = config["manual_subtopics"]
        if config.get("manual_max_iterations") is not None:
            payload["manual_max_iterations"] = config["manual_max_iterations"]
        return payload

    @staticmethod
    def _format_evidence(evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            return "(none)"
        blocks: list[str] = []
        for index, item in enumerate(evidence, 1):
            result = str(item.get("result", "") or "").strip()
            blocks.append(
                "\n".join(
                    [
                        f"{index}. {item.get('source', 'source')} / {item.get('subtopic', '')}",
                        f"query: {item.get('query', '')}",
                        f"success: {item.get('success')}",
                        f"result: {result[:2500]}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _fallback_report(
        topic: str,
        subtopics: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> str:
        lines = [f"# {topic}", ""]
        if not evidence:
            lines.append("No external evidence was available for this run.")
        for item in subtopics:
            lines.append(f"## {item.get('title', 'Subtopic')}")
            overview = str(item.get("overview") or "").strip()
            if overview:
                lines.append(overview)
            matches = [ev for ev in evidence if ev.get("subtopic") == item.get("title")]
            for record in matches:
                lines.append(
                    f"- {record.get('source')}: {str(record.get('result', '')).strip()[:500]}"
                )
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _collect_sources(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in evidence:
            for source in item.get("sources", []):
                if not isinstance(source, dict):
                    continue
                key = json.dumps(source, sort_keys=True, ensure_ascii=False)
                if key in seen:
                    continue
                seen.add(key)
                sources.append(source)
        return sources

    @staticmethod
    def _subtopic_count(
        depth: Literal["quick", "standard", "deep", "manual"], manual: int | None
    ) -> int:
        if depth == "quick":
            return 2
        if depth == "deep":
            return 5
        if depth == "manual":
            return max(1, min(manual or 3, 10))
        return 3

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_choice(value: Any, *, allowed: set[str], default: str) -> str:
        normalized = str(value or default).strip().lower()
        return normalized if normalized in allowed else default

    @staticmethod
    def _requires_outline_confirmation(overrides: dict[str, Any]) -> bool:
        requested = overrides.get("outline_preview")
        if isinstance(requested, bool):
            return requested and not overrides.get("confirmed_outline")
        if overrides.get("confirmed_outline") is not None:
            return False
        return any(
            key in overrides
            for key in {
                "mode",
                "depth",
                "sources",
                "manual_subtopics",
                "manual_max_iterations",
            }
        )

    @staticmethod
    def _strip_heading(text: str) -> str:
        stripped = text.strip()
        if stripped.lower().startswith("research question:"):
            return stripped.split(":", 1)[1].strip()
        return stripped

