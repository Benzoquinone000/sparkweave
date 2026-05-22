"""Minimal LangGraph chat workflow with SparkWeave tool support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
import json
import re
from typing import Any

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.core.dependencies import dependency_error
from sparkweave.core.state import TutorState, context_to_state, message_text
from sparkweave.graphs._answer_now import (
    answer_now_metadata,
    answer_now_parts,
    answer_now_progress_metadata,
    answer_now_user_prompt,
    extract_answer_now_payload,
)
from sparkweave.graphs.rag_overrides import apply_rag_overrides
from sparkweave.llm import ainvoke_json, chat_messages, create_chat_model
from sparkweave.runtime.capability_router import (
    DELEGABLE_CAPABILITIES,
    PROFILE_GUIDED_TERMS,
    SOLVE_TERMS,
    SPECIALIST_LABELS,
    CoordinatorDecision,
    LearningCapabilityRouter,
)
from sparkweave.runtime.tool_execution import GraphToolExecutor
from sparkweave.tools import LangChainToolRegistry

MAX_PARALLEL_TOOL_CALLS = 8


class ChatGraph:
    """LangGraph implementation of the default chat capability."""

    source = "chat"

    def __init__(
        self,
        *,
        model: Any | None = None,
        coordinator_model: Any | None = None,
        tool_registry: LangChainToolRegistry | None = None,
        max_tool_rounds: int = 3,
        coordinator_enabled: bool = True,
        capability_router: LearningCapabilityRouter | None = None,
        specialist_runner: Callable[[str, UnifiedContext, StreamBus], Awaitable[TutorState]] | None = None,
    ) -> None:
        self.model = model
        self.coordinator_model = coordinator_model
        self.tool_registry = tool_registry or LangChainToolRegistry()
        self.max_tool_rounds = max_tool_rounds
        self.coordinator_enabled = coordinator_enabled
        self.capability_router = capability_router or LearningCapabilityRouter()
        self.tool_executor = GraphToolExecutor(
            self.tool_registry,
            source=self.source,
            stage="acting",
            arg_augmenter=self._augment_tool_args,
            retrieve_metadata_builder=self._retrieve_metadata,
            result_metadata_tools={"rag", "canvas"},
        )
        self.specialist_runner = specialist_runner
        self._compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        payload = extract_answer_now_payload(context)
        if payload is not None:
            state = context_to_state(context, stream=stream)
            return await self._run_answer_now(state, payload)

        decision = await self._coordinate(context, stream)
        if decision.direct_tool in {"external_video_search", "external_image_search"}:
            return await self._run_direct_media_tool(context, stream, decision)
        if decision.delegates:
            return await self._run_specialist(context, stream, decision)

        context = self._context_with_chat_decision_tools(context, decision)
        context, prefetched_rag = await self._prefetch_rag_context(context, stream)
        state = context_to_state(context, stream=stream)
        if prefetched_rag is not None:
            state["tool_results"] = [prefetched_rag]
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
        builder.add_node("agent", self._agent_node)
        builder.add_node("tools", self._tools_node)
        builder.add_node("respond", self._respond_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent",
            self._route_after_agent,
            {"tools": "tools", "respond": "respond"},
        )
        builder.add_edge("tools", "agent")
        builder.add_edge("respond", END)
        self._compiled = builder.compile()
        return self._compiled

    async def _agent_node(self, state: TutorState) -> dict[str, Any]:
        stream = state.get("stream")
        enabled_tools = self._enabled_tools(state)
        if "rag" in (state.get("enabled_tools") or []) and not state.get("knowledge_bases"):
            await stream.progress(
                "RAG was enabled, but no knowledge base is attached; skipping RAG for this turn.",
                source=self.source,
                stage="thinking",
                metadata={"trace_kind": "warning", "reason": "rag_without_kb"},
            )
        model = self.model or create_chat_model(temperature=0.2)
        tools = self.tool_registry.get_tools(enabled_tools) if enabled_tools else []
        if tools and hasattr(model, "bind_tools"):
            model = model.bind_tools(tools)

        async with stream.stage("thinking", source=self.source):
            await stream.progress(
                "Thinking...",
                source=self.source,
                stage="thinking",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await model.ainvoke(state["messages"])
            await stream.progress(
                "",
                source=self.source,
                stage="thinking",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )

        return {"messages": [*state["messages"], response]}

    async def _tools_node(self, state: TutorState) -> dict[str, Any]:
        try:
            from langchain_core.messages import ToolMessage
        except ImportError as exc:
            raise dependency_error("langchain-core") from exc

        stream = state.get("stream")
        context = state.get("context")
        calls = self._extract_tool_calls(state["messages"][-1])
        if not calls:
            return {"messages": state["messages"]}
        enabled_tool_names = set(self._enabled_tools(state))
        selected_calls = calls
        overflow_calls: list[dict[str, Any]] = []
        allowed_calls, blocked_calls = self._partition_authorized_tool_calls(calls, enabled_tool_names)
        if len(calls) > MAX_PARALLEL_TOOL_CALLS:
            await stream.progress(
                f"Model requested {len(calls)} tool calls; only {MAX_PARALLEL_TOOL_CALLS} can run in parallel.",
                source=self.source,
                stage="acting",
                metadata={"trace_kind": "progress", "reason": "too_many_tool_calls"},
            )
            selected_calls = calls[:MAX_PARALLEL_TOOL_CALLS]
            overflow_calls = calls[MAX_PARALLEL_TOOL_CALLS:]
            allowed_calls, blocked_calls = self._partition_authorized_tool_calls(
                selected_calls,
                enabled_tool_names,
            )

        async with stream.stage("acting", source=self.source):
            for call in overflow_calls:
                await stream.progress(
                    f"Skipped extra tool `{call['name']}` because this turn reached the parallel tool limit.",
                    source=self.source,
                    stage="acting",
                    metadata={
                        "trace_kind": "warning",
                        "reason": "too_many_tool_calls",
                        "tool_call_id": call["id"],
                        "tool_name": call["name"],
                        "max_parallel_tool_calls": MAX_PARALLEL_TOOL_CALLS,
                    },
                )
            for call in blocked_calls:
                await stream.progress(
                    f"Skipped disabled tool `{call['name']}` for this turn.",
                    source=self.source,
                    stage="acting",
                    metadata={
                        "trace_kind": "warning",
                        "reason": "disabled_tool_call",
                        "tool_call_id": call["id"],
                        "tool_name": call["name"],
                    },
                )
            tasks = [
                self._execute_tool_call(call, context, stream, tool_index=index)
                for index, call in enumerate(allowed_calls)
            ]
            records = await asyncio.gather(*tasks) if tasks else []

        records_by_id = {record["id"]: record for record in records}
        blocked_ids = {call["id"] for call in blocked_calls}
        overflow_ids = {call["id"] for call in overflow_calls}
        tool_messages = []
        for call in calls:
            if call["id"] in overflow_ids:
                tool_messages.append(
                    ToolMessage(
                        content=(
                            "This tool call was skipped because the turn reached "
                            f"the {MAX_PARALLEL_TOOL_CALLS}-tool parallel limit. "
                            "Continue with the tool results already available."
                        ),
                        tool_call_id=call["id"],
                        name=call["name"],
                    )
                )
                continue
            if call["id"] in blocked_ids:
                tool_messages.append(
                    ToolMessage(
                        content=(
                            f"Tool `{call['name']}` is not enabled for this turn. "
                            "Continue without using it."
                        ),
                        tool_call_id=call["id"],
                        name=call["name"],
                    )
                )
                continue
            record = records_by_id.get(call["id"])
            if record is None:
                continue
            tool_messages.append(
                ToolMessage(
                    content=record["result"],
                    tool_call_id=record["id"],
                    name=record["name"],
                )
            )
        previous_results = list(state.get("tool_results", []))
        previous_results.extend(records)
        return {
            "messages": [*state["messages"], *tool_messages],
            "tool_results": previous_results,
            "loop_count": int(state.get("loop_count", 0)) + 1,
        }

    async def _respond_node(self, state: TutorState) -> dict[str, Any]:
        stream = state.get("stream")
        final_answer = message_text(state["messages"][-1]).strip()
        if not final_answer:
            final_answer = "I could not produce a final answer from the current graph state."

        sources = self._collect_sources(state.get("tool_results", []))
        async with stream.stage("responding", source=self.source):
            if sources:
                await stream.sources(sources, source=self.source, stage="responding")
            await stream.content(final_answer, source=self.source, stage="responding")
            await stream.result(
                {
                    "response": final_answer,
                    "tool_traces": state.get("tool_results", []),
                    "runtime": "langgraph",
                },
                source=self.source,
            )
        return {"final_answer": final_answer}

    async def _run_answer_now(
        self,
        state: TutorState,
        payload: dict[str, Any],
    ) -> TutorState:
        stream = state["stream"]
        original, partial, trace_summary = answer_now_parts(state, payload)
        model = self.model or create_chat_model(temperature=0.2)

        async with stream.stage("responding", source=self.source):
            await stream.progress(
                "Synthesizing answer now from the partial trace...",
                source=self.source,
                stage="responding",
                metadata=answer_now_progress_metadata("running"),
            )
            response = await model.ainvoke(
                chat_messages(
                    system=(
                        "You are SparkWeave. The user asked to answer now. "
                        "Use the original request, the current draft, and the "
                        "partial trace to produce the best final user-facing "
                        "answer. Do not call tools."
                    ),
                    user=answer_now_user_prompt(
                        original=original,
                        partial=partial,
                        trace_summary=trace_summary,
                    ),
                )
            )
            final_answer = message_text(response).strip() or partial
            await stream.content(final_answer, source=self.source, stage="responding")
            await stream.progress(
                "",
                source=self.source,
                stage="responding",
                metadata=answer_now_progress_metadata("complete"),
            )
            await stream.result(
                {
                    "response": final_answer,
                    "tool_traces": [],
                    "metadata": answer_now_metadata(),
                    "runtime": "langgraph",
                },
                source=self.source,
            )

        state["user_message"] = original
        state["final_answer"] = final_answer
        return state

    def _route_after_agent(self, state: TutorState) -> str:
        if int(state.get("loop_count", 0)) >= self.max_tool_rounds:
            return "respond"
        calls = self._extract_tool_calls(state["messages"][-1])
        return "tools" if calls else "respond"

    async def _execute_tool_call(
        self,
        call: dict[str, Any],
        context: UnifiedContext | None,
        stream: StreamBus,
        *,
        tool_index: int,
    ) -> dict[str, Any]:
        return await self.tool_executor.execute(call, context, stream, tool_index=tool_index)

    async def _run_external_video_tool(
        self,
        context: UnifiedContext,
        stream: StreamBus,
        decision: CoordinatorDecision,
    ) -> TutorState:
        if decision.direct_tool != "external_video_search":
            decision = replace(
                decision,
                config={**dict(decision.config or {}), "_direct_tool": "external_video_search"},
            )
        return await self._run_direct_media_tool(context, stream, decision)

    async def _run_external_image_tool(
        self,
        context: UnifiedContext,
        stream: StreamBus,
        decision: CoordinatorDecision,
    ) -> TutorState:
        if decision.direct_tool != "external_image_search":
            decision = replace(
                decision,
                config={**dict(decision.config or {}), "_direct_tool": "external_image_search"},
            )
        return await self._run_direct_media_tool(context, stream, decision)

    async def _run_direct_media_tool(
        self,
        context: UnifiedContext,
        stream: StreamBus,
        decision: CoordinatorDecision,
    ) -> TutorState:
        tool_name = decision.direct_tool or "external_video_search"
        if tool_name not in {"external_video_search", "external_image_search"}:
            tool_name = "external_video_search"
        is_image = tool_name == "external_image_search"
        config = dict(decision.config or {})
        try:
            max_results = int(config.get("max_results") or (4 if is_image else 3))
        except (TypeError, ValueError):
            max_results = 4 if is_image else 3
        try:
            search_depth = int(config.get("search_depth") or 8)
        except (TypeError, ValueError):
            search_depth = 8
        learner_hints = config.get("learner_hints") or (
            self._external_image_config(context) if is_image else self._external_video_config(context)
        )
        tool_args = {
            "topic": str(config.get("topic") or context.user_message).strip(),
            "prompt": str(config.get("prompt") or context.user_message).strip(),
            "language": context.language or "zh",
            "max_results": max_results,
            "search_depth": max(4, min(search_depth, 12)),
            "learner_hints": learner_hints,
        }
        collaboration_metadata = self._collaboration_metadata(
            decision,
            context,
            profile_hints=self._learner_profile_hints(context),
            rewritten_prompt=str(config.get("_coordinator_user_message") or "").strip(),
        )
        orchestration_metadata = {
            "selected_route": tool_name,
            "orchestration_mode": "direct_tool",
            "direct_tool": tool_name,
            "delegated": False,
            **collaboration_metadata,
        }
        async with stream.stage(
            "acting",
            source=self.source,
            metadata={
                "trace_kind": "tool_work",
                "tool_name": tool_name,
                "capability": "chat",
                **orchestration_metadata,
            },
        ):
            record = await self._execute_tool_call(
                {
                    "id": tool_name.replace("_", "-"),
                    "name": tool_name,
                    "args": tool_args,
                },
                context,
                stream,
                tool_index=0,
            )

        metadata = dict(record.get("metadata") or {})
        response = str(record.get("result") or metadata.get("response") or "").strip()
        if not response:
            response = "我为你筛选了几张适合当前任务的学习图片。" if is_image else "我为你筛选了几条适合当前任务的视频。"
        final_result = {
            **metadata,
            **orchestration_metadata,
            "response": response,
            "runtime": "langgraph",
            "capability": "chat",
            "tool_name": tool_name,
            "tool_traces": [record],
        }
        async with stream.stage("responding", source=self.source):
            if record.get("sources"):
                await stream.sources(record["sources"], source=self.source, stage="responding")
            await stream.content(response, source=self.source, stage="responding")
            await stream.result(final_result, source=self.source)
        return {
            "final_answer": response,
            "tool_results": [record],
            ("external_image_result" if is_image else "external_video_result"): final_result,
        }

    async def _prefetch_rag_context(
        self,
        context: UnifiedContext,
        stream: StreamBus,
    ) -> tuple[UnifiedContext, dict[str, Any] | None]:
        if not self._should_prefetch_rag(context):
            return context, None

        kb_name = str(context.knowledge_bases[0] or "").strip()
        query = str(context.user_message or "").strip()
        if not kb_name or not query:
            return context, None

        args: dict[str, Any] = {"query": query, "kb_name": kb_name}
        self._apply_rag_overrides(args, context)
        tool_call_id = "rag-prefetch"
        retrieve_meta = {
            **(
                self._retrieve_metadata(
                    name="rag",
                    args=args,
                    tool_call_id=tool_call_id,
                    tool_index=0,
                    context=context,
                )
                or {}
            ),
            "prefetch": True,
        }

        async with stream.stage(
            "acting",
            source=self.source,
            metadata={
                "trace_kind": "tool_work",
                "tool_name": "rag",
                "prefetch": True,
            },
        ):
            await stream.tool_call(
                tool_name="rag",
                args=args,
                source=self.source,
                stage="acting",
                metadata={
                    "trace_kind": "tool_call",
                    "tool_call_id": tool_call_id,
                    "tool_name": "rag",
                    "prefetch": True,
                },
            )
            await stream.progress(
                f"Query: {query}",
                source=self.source,
                stage="acting",
                metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "running"},
            )

            async def _event_sink(
                event_type: str,
                message: str = "",
                metadata: dict[str, Any] | None = None,
            ) -> None:
                if not message:
                    return
                await stream.progress(
                    message,
                    source=self.source,
                    stage="acting",
                    metadata={
                        **retrieve_meta,
                        "trace_kind": str(event_type or "tool_log"),
                        **(metadata or {}),
                    },
                )

            try:
                from sparkweave.services.rag import rag_search

                result = await rag_search(**args, event_sink=_event_sink)
                content = str(result.get("content") or result.get("answer") or "").strip()
                content = self._clip_prefetched_rag_context(content, context)
                sources = self._normalize_rag_sources(
                    result.get("sources"),
                    kb_name=kb_name,
                    query=query,
                )
                success = bool(result.get("success", True)) and bool(content or sources)
                await stream.progress(
                    f"Retrieve complete ({len(content)} chars)",
                    source=self.source,
                    stage="acting",
                    metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "complete"},
                )
            except Exception as exc:
                result = {"error": str(exc), "prefetch": True}
                content = ""
                sources = []
                success = False
                await stream.error(
                    f"RAG prefetch failed: {exc}",
                    source=self.source,
                    stage="acting",
                    metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "error"},
                )

            await stream.tool_result(
                tool_name="rag",
                result=content or "(empty RAG prefetch result)",
                source=self.source,
                stage="acting",
                metadata={
                    "trace_kind": "tool_result",
                    "tool_call_id": tool_call_id,
                    "tool_name": "rag",
                    "success": success,
                    "sources": sources,
                    "prefetch": True,
                    "result_metadata": {
                        **dict(result or {}),
                        "prefetch": True,
                        "kb_name": kb_name,
                        "query": query,
                    },
                },
            )
            if sources:
                await stream.sources(
                    sources,
                    source=self.source,
                    stage="acting",
                    metadata={"prefetch": True, "tool_name": "rag"},
                )

        if not content:
            return context, None

        rag_context = self._format_prefetched_rag_context(
            kb_name=kb_name,
            content=content,
        )
        memory_context = "\n\n".join(
            part.strip()
            for part in (context.memory_context, rag_context)
            if str(part or "").strip()
        )
        metadata = {
            **dict(context.metadata or {}),
            "prefetched_rag": True,
            "prefetched_rag_kb": kb_name,
            "prefetched_rag_source_count": len(sources),
        }
        record = {
            "id": tool_call_id,
            "name": "rag",
            "arguments": args,
            "result": content,
            "success": success,
            "sources": sources,
            "metadata": {
                **dict(result or {}),
                "prefetch": True,
                "kb_name": kb_name,
                "query": query,
            },
        }
        return replace(context, memory_context=memory_context, metadata=metadata), record

    @staticmethod
    def _should_prefetch_rag(context: UnifiedContext) -> bool:
        overrides = dict(context.config_overrides or {})
        if not ChatGraph._truthy(overrides.get("prefetch_rag")):
            return False
        prefetched = context.metadata.get("prefetched_rag")
        if prefetched is not None and ChatGraph._truthy(prefetched):
            return False
        if not context.knowledge_bases:
            return False
        enabled = set(context.enabled_tools or [])
        if "rag" not in enabled:
            return False
        memory_context = str(context.memory_context or "")
        return "Retrieved knowledge base context from `" not in memory_context

    @staticmethod
    def _format_prefetched_rag_context(*, kb_name: str, content: str) -> str:
        return (
            f"Retrieved knowledge base context from `{kb_name}`. "
            "Use it as grounded evidence when answering. If the evidence is "
            "insufficient, say what is missing instead of inventing details.\n\n"
            f"{content.strip()}"
        )

    @staticmethod
    def _clip_prefetched_rag_context(content: str, context: UnifiedContext) -> str:
        overrides = dict(context.config_overrides or {})
        try:
            limit = int(overrides.get("max_context_chars") or 12000)
        except (TypeError, ValueError):
            limit = 12000
        limit = max(500, min(limit, 30000))
        if len(content) <= limit:
            return content
        return content[:limit].rstrip() + "\n...[truncated]"

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

    @staticmethod
    def _retrieve_metadata(
        *,
        name: str,
        args: dict[str, Any],
        tool_call_id: str,
        tool_index: int,
        context: UnifiedContext | None,
    ) -> dict[str, Any] | None:
        if name != "rag":
            return None
        return {
            "trace_role": "retrieve",
            "trace_group": "retrieve",
            "tool_call_id": tool_call_id,
            "tool_name": name,
            "tool_index": tool_index,
            "session_id": context.session_id if context else "",
            "turn_id": str(context.metadata.get("turn_id", "")) if context else "",
            "query": str(args.get("query") or ""),
        }

    def _enabled_tools(self, state: TutorState) -> list[str]:
        enabled = list(state.get("enabled_tools") or [])
        if not enabled:
            return []
        known = set(self.tool_registry.names())
        if "rag" in enabled and not state.get("knowledge_bases"):
            enabled = [name for name in enabled if name != "rag"]
        return [name for name in enabled if name in known]

    @staticmethod
    def _partition_authorized_tool_calls(
        calls: list[dict[str, Any]],
        enabled_tool_names: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        allowed: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for call in calls:
            name = str(call.get("name") or "").strip()
            if name in enabled_tool_names:
                allowed.append(call)
            else:
                blocked.append(call)
        return allowed, blocked

    @staticmethod
    def _extract_tool_calls(message: Any) -> list[dict[str, Any]]:
        calls = getattr(message, "tool_calls", None) or []
        normalized: list[dict[str, Any]] = []
        for index, call in enumerate(calls):
            if isinstance(call, dict):
                normalized.append(
                    {
                        "id": call.get("id") or f"tool-call-{index}",
                        "name": call.get("name"),
                        "args": call.get("args") or {},
                    }
                )
                continue
            function = getattr(call, "function", None)
            arguments = getattr(function, "arguments", {}) if function else {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            normalized.append(
                {
                    "id": getattr(call, "id", f"tool-call-{index}"),
                    "name": getattr(function, "name", ""),
                    "args": arguments or {},
                }
            )
        return [call for call in normalized if call.get("name")]

    @staticmethod
    def _augment_tool_args(
        name: str,
        args: dict[str, Any],
        context: UnifiedContext | None,
    ) -> dict[str, Any]:
        if context is None:
            return args
        augmented = dict(args)
        if name == "rag" and context.knowledge_bases:
            augmented.setdefault("kb_name", context.knowledge_bases[0])
            ChatGraph._apply_rag_overrides(augmented, context)
        if name == "web_search":
            augmented.setdefault("query", context.user_message)
        if name == "external_video_search":
            augmented.setdefault("topic", context.user_message)
            augmented.setdefault("prompt", context.user_message)
            augmented.setdefault("language", context.language or "zh")
            augmented.setdefault("learner_hints", ChatGraph._external_video_config(context))
        if name == "external_image_search":
            augmented.setdefault("topic", context.user_message)
            augmented.setdefault("prompt", context.user_message)
            augmented.setdefault("language", context.language or "zh")
            augmented.setdefault("learner_hints", ChatGraph._external_image_config(context))
        if name == "code_execution":
            augmented.setdefault("intent", context.user_message)
            augmented.setdefault("session_id", context.session_id)
            augmented.setdefault("turn_id", str(context.metadata.get("turn_id", "") or ""))
            augmented.setdefault("feature", "chat")
        if name in {"reason", "brainstorm"}:
            augmented.setdefault("context", context.user_message)
        return augmented

    @staticmethod
    def _apply_rag_overrides(args: dict[str, Any], context: UnifiedContext) -> None:
        apply_rag_overrides(args, context.config_overrides)

    async def _coordinate(
        self,
        context: UnifiedContext,
        stream: StreamBus,
    ) -> CoordinatorDecision:
        if not self.coordinator_enabled:
            return CoordinatorDecision(reason="Coordinator disabled for this graph instance.")
        decision = await self._refine_decision_with_llm(context, self._decide_specialist(context))
        profile_hints = self._learner_profile_hints(context)
        decision_config = dict(decision.config or {})
        rewritten_prompt = str(decision_config.get("_coordinator_user_message") or "").strip()
        metadata = {
            "trace_kind": "coordinator_decision",
            "capability": decision.capability,
            "selected_route": decision.direct_tool or decision.capability,
            "orchestration_mode": (
                "direct_tool"
                if decision.direct_tool
                else "delegate"
                if decision.delegates
                else "chat"
            ),
            "direct_tool": decision.direct_tool,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "delegated": decision.delegates,
            "profile_hints_applied": bool(profile_hints),
            "profile_hint_keys": sorted(key for key in profile_hints.keys() if key != "profile_context"),
            "profile_guided": bool(decision_config.get("profile_guided")),
            "rewritten_prompt": rewritten_prompt[:260],
            "agent_cluster": SPECIALIST_LABELS.get(
                decision.direct_tool or decision.capability,
                "Dialogue Coordinator Agent",
            ),
            **self.capability_router.collaboration_metadata(
                decision,
                context,
                profile_hints=profile_hints,
                rewritten_prompt=rewritten_prompt,
            ),
        }
        async with stream.stage("coordinating", source="dialogue_coordinator", metadata=metadata):
            if decision.delegates:
                await stream.progress(
                    f"Delegating to {SPECIALIST_LABELS.get(decision.capability, decision.capability)}.",
                    source="dialogue_coordinator",
                    stage="coordinating",
                    metadata=metadata,
                )
            else:
                progress_message = (
                    f"Calling {SPECIALIST_LABELS.get(decision.direct_tool, decision.direct_tool)}."
                    if decision.direct_tool
                    else "Keeping this turn in the default chat agent."
                )
                await stream.progress(
                    progress_message,
                    source="dialogue_coordinator",
                    stage="coordinating",
                    metadata=metadata,
                )
        return decision

    async def _refine_decision_with_llm(
        self,
        context: UnifiedContext,
        prior: CoordinatorDecision,
    ) -> CoordinatorDecision:
        auto_allowed = self.coordinator_model is not None or self.model is None
        if not self.capability_router.should_consult_llm(
            context,
            prior,
            auto_allowed=auto_allowed,
        ):
            return prior

        model = self.coordinator_model
        if model is None:
            if self.model is not None:
                model = self.model
            else:
                model = create_chat_model(temperature=0.0)

        system, user = self.capability_router.build_llm_classifier_prompt(context, prior)
        try:
            payload = await ainvoke_json(model, system=system, user=user)
        except Exception:
            return prior
        if not payload:
            return prior
        return self.capability_router.decision_from_llm_payload(context, payload, prior)

    @staticmethod
    def _collaboration_metadata(
        decision: CoordinatorDecision,
        context: UnifiedContext,
        *,
        profile_hints: dict[str, Any] | None = None,
        rewritten_prompt: str = "",
    ) -> dict[str, Any]:
        return LearningCapabilityRouter.collaboration_metadata(
            decision,
            context,
            profile_hints=profile_hints,
            rewritten_prompt=rewritten_prompt,
        )

    @staticmethod
    def _collaboration_route(capability: str, profile_aware: bool) -> list[dict[str, str]]:
        return LearningCapabilityRouter.collaboration_route(capability, profile_aware)

    def _decide_specialist(self, context: UnifiedContext) -> CoordinatorDecision:
        return self.capability_router.decide(context)

    @staticmethod
    def _context_with_chat_decision_tools(
        context: UnifiedContext,
        decision: CoordinatorDecision,
    ) -> UnifiedContext:
        if decision.delegates or decision.direct_tool or decision.tools is None:
            return context
        tools = list(dict.fromkeys(decision.tools))
        return replace(context, enabled_tools=tools)

    async def _run_specialist(
        self,
        context: UnifiedContext,
        stream: StreamBus,
        decision: CoordinatorDecision,
    ) -> TutorState:
        delegated_context = self._delegated_context(context, decision)
        profile_hints = self._learner_profile_hints(context)
        decision_config = dict(decision.config or {})
        rewritten_prompt = str(decision_config.get("_coordinator_user_message") or "").strip()
        collaboration_metadata = self._collaboration_metadata(
            decision,
            context,
            profile_hints=profile_hints,
            rewritten_prompt=rewritten_prompt,
        )
        await stream.progress(
            f"Awakened {SPECIALIST_LABELS.get(decision.capability, decision.capability)}.",
            source="dialogue_coordinator",
            stage="coordinating",
            metadata={
                "trace_kind": "agent_handoff",
                "target_capability": decision.capability,
                "target_agent": SPECIALIST_LABELS.get(decision.capability, decision.capability),
                "confidence": decision.confidence,
                "reason": decision.reason,
                "profile_hints_applied": bool(profile_hints),
                "profile_hint_keys": sorted(key for key in profile_hints.keys() if key != "profile_context"),
                "profile_guided": bool(decision_config.get("profile_guided")),
                "rewritten_prompt": rewritten_prompt[:260],
                **collaboration_metadata,
            },
        )
        if self.specialist_runner is not None:
            return await self.specialist_runner(decision.capability, delegated_context, stream)
        return await self._run_builtin_specialist(decision.capability, delegated_context, stream)

    @staticmethod
    async def _run_builtin_specialist(
        capability: str,
        context: UnifiedContext,
        stream: StreamBus,
    ) -> TutorState:
        if capability == "deep_solve":
            from sparkweave.graphs.deep_solve import DeepSolveGraph

            return await DeepSolveGraph().run(context, stream)
        if capability == "deep_question":
            from sparkweave.graphs.deep_question import DeepQuestionGraph

            return await DeepQuestionGraph().run(context, stream)
        if capability == "deep_research":
            from sparkweave.graphs.deep_research import DeepResearchGraph

            return await DeepResearchGraph().run(context, stream)
        if capability == "visualize":
            from sparkweave.graphs.visualize import VisualizeGraph

            return await VisualizeGraph().run(context, stream)
        if capability == "math_animator":
            from sparkweave.graphs.math_animator import MathAnimatorGraph

            return await MathAnimatorGraph().run(context, stream)
        raise RuntimeError(f"Unsupported specialist capability: {capability}")

    @staticmethod
    def _delegated_context(
        context: UnifiedContext,
        decision: CoordinatorDecision,
    ) -> UnifiedContext:
        return LearningCapabilityRouter.delegated_context(context, decision)

    @staticmethod
    def _forced_decision(value: str) -> CoordinatorDecision:
        capability = value.strip().lower()
        if capability in {"none", "off", "chat", "default"}:
            return CoordinatorDecision(reason="Forced to stay in chat.")
        if capability not in DELEGABLE_CAPABILITIES:
            return CoordinatorDecision(
                confidence=0.0,
                reason=f"Requested delegate capability `{value}` is not available.",
            )
        return CoordinatorDecision(
            capability=capability,
            confidence=1.0,
            reason="The request explicitly forced this specialist capability.",
        )

    @staticmethod
    def _normalized_text(context: UnifiedContext) -> str:
        text = context.user_message or ""
        if context.attachments:
            text += " attached_media"
        return text.strip().lower()

    @staticmethod
    def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term.lower() in text for term in terms)

    @staticmethod
    def _has_visual_action(text: str) -> bool:
        action_terms = (
            "画",
            "生成",
            "做一个",
            "展示",
            "呈现",
            "可视化",
            "图解",
            "diagram",
            "visualize",
            "draw",
            "generate",
            "create",
            "show",
        )
        return ChatGraph._contains_any(text, action_terms)

    @staticmethod
    def _looks_like_external_video_request(text: str) -> bool:
        return LearningCapabilityRouter.looks_like_external_video_request(text)

    @staticmethod
    def _looks_like_external_image_request(text: str) -> bool:
        return LearningCapabilityRouter.looks_like_external_image_request(text)

    @staticmethod
    def _looks_like_solve_request(text: str) -> bool:
        if not ChatGraph._contains_any(text, SOLVE_TERMS):
            return False
        math_markers = (
            "=",
            "\\frac",
            "\\lim",
            "\\int",
            "\\sum",
            "^",
            "x",
            "函数",
            "极限",
            "导数",
            "积分",
            "矩阵",
            "概率",
            "方程",
        )
        return ChatGraph._contains_any(text, math_markers)

    @staticmethod
    def _profile_guided_decision(
        context: UnifiedContext,
        text: str,
    ) -> CoordinatorDecision | None:
        if not ChatGraph._looks_like_profile_guided_request(text):
            return None
        hints = ChatGraph._learner_profile_hints(context)
        if not hints:
            return None
        capability = ChatGraph._capability_from_profile_hints(hints)
        if not capability:
            return None

        target_prompt = ChatGraph._profile_guided_prompt(hints, context.user_message)
        if not target_prompt or target_prompt.strip().lower() == text.strip().lower():
            focus = ChatGraph._hint_text(hints.get("current_focus"))
            if focus:
                target_prompt = f"围绕「{focus}」安排下一步学习材料和验证任务。"
        if not target_prompt:
            return None

        config = ChatGraph._profile_guided_config(context, capability, target_prompt)
        preferred = ChatGraph._hint_text(hints.get("preferred_resource")) or "current learner profile"
        if capability in {"external_video_search", "external_image_search"}:
            return CoordinatorDecision(
                capability="chat",
                confidence=0.72,
                reason=f"The learner asked for a next step; the learner profile prefers {preferred}.",
                tools=[capability],
                config=config,
            )
        return CoordinatorDecision(
            capability=capability,
            confidence=0.72,
            reason=f"The learner asked for a next step; the learner profile prefers {preferred}.",
            config=config,
        )

    @staticmethod
    def _looks_like_profile_guided_request(text: str) -> bool:
        normalized = text.strip().lower()
        if not normalized:
            return False
        if ChatGraph._contains_any(normalized, PROFILE_GUIDED_TERMS):
            return True
        return bool(re.fullmatch(r"(go|start|continue|next|继续|开始|下一步)[\s。.!！?？]*", normalized))

    @staticmethod
    def _capability_from_profile_hints(hints: dict[str, Any]) -> str:
        action = hints.get("next_action") if isinstance(hints.get("next_action"), dict) else {}
        preferred = ChatGraph._capability_from_resource_text(ChatGraph._hint_text(hints.get("preferred_resource")).lower())
        if preferred:
            return preferred
        candidates: list[Any] = [
            *(hints.get("preferences") or []),
            action.get("kind"),
            action.get("title"),
            action.get("summary"),
            action.get("suggested_prompt"),
        ]
        joined = " ".join(ChatGraph._hint_text(item, limit=260).lower() for item in candidates if item)
        if not joined:
            return ""
        return ChatGraph._capability_from_resource_text(joined)

    @staticmethod
    def _capability_from_resource_text(joined: str) -> str:
        if any(term in joined for term in ("curated_public_video", "external_video", "public_video", "公开视频", "公开课", "bilibili", "youtube")):
            return "external_video_search"
        if any(term in joined for term in ("external_image", "public_image", "image_resource", "picture_reference", "diagram_reference", "illustration_reference", "图片", "配图", "参考图", "图片素材", "示意图素材")):
            return "external_image_search"
        if any(term in joined for term in ("interactive_practice", "practice", "quiz", "question", "练习", "题", "复测", "测试")):
            return "deep_question"
        if any(term in joined for term in ("visual_explanation", "visual", "diagram", "图解", "可视化", "关系图")):
            return "visualize"
        if any(term in joined for term in ("short_video", "video", "animation", "manim", "短视频", "动画", "视频讲解")):
            return "math_animator"
        return ""

    @staticmethod
    def _profile_guided_prompt(hints: dict[str, Any], fallback: str) -> str:
        action = hints.get("next_action") if isinstance(hints.get("next_action"), dict) else {}
        for value in (
            action.get("suggested_prompt"),
            action.get("summary"),
            action.get("title"),
            hints.get("current_focus"),
            hints.get("summary"),
            fallback,
        ):
            text = ChatGraph._hint_text(value, limit=360)
            if text:
                return text
        return ""

    @staticmethod
    def _profile_guided_config(
        context: UnifiedContext,
        capability: str,
        prompt: str,
    ) -> dict[str, Any]:
        if capability == "external_video_search":
            config = ChatGraph._external_video_tool_config(context, prompt)
        elif capability == "external_image_search":
            config = ChatGraph._external_image_tool_config(context, prompt)
        elif capability == "deep_question":
            config = ChatGraph._question_config(context, prompt, "生成 3 道练习题")
        elif capability == "visualize":
            config = ChatGraph._visualize_config(context, "生成图解 visual diagram")
        elif capability == "math_animator":
            config = ChatGraph._math_animator_config(context, "生成短视频 animation video")
        else:
            config = {}
        config["_coordinator_user_message"] = prompt
        config["profile_guided"] = True
        return config

    @staticmethod
    def _visualize_config(context: UnifiedContext, text: str) -> dict[str, Any]:
        config: dict[str, Any]
        if ChatGraph._contains_any(text, ("流程图", "关系图", "思维导图", "mermaid", "flowchart", "diagram")):
            config = {"render_mode": "mermaid"}
        elif ChatGraph._contains_any(text, ("图表", "柱状图", "折线图", "饼图", "chart", "bar", "line", "pie", "trend")):
            config = {"render_mode": "chartjs"}
        else:
            config = {"render_mode": "auto"}
        hints = ChatGraph._learner_profile_hints(context)
        guidance = ChatGraph._learner_profile_guidance(context)
        if guidance:
            config["style_hint"] = guidance
        if hints:
            config["learner_profile_hints"] = hints
        return config

    @staticmethod
    def _math_animator_config(context: UnifiedContext, text: str) -> dict[str, Any]:
        output_mode = "video"
        if ChatGraph._contains_any(text, ("分镜", "插图", "图片", "image", "storyboard")):
            output_mode = "image"
        config = {"output_mode": output_mode, "quality": "medium"}
        hints = ChatGraph._learner_profile_hints(context)
        guidance = ChatGraph._learner_profile_guidance(context)
        if guidance:
            config["style_hint"] = guidance
        if hints:
            config["learner_profile_hints"] = hints
        return config

    @staticmethod
    def _question_config(context: UnifiedContext, original: str, text: str) -> dict[str, Any]:
        preference = "Generate interactive practice questions for the learner."
        guidance = ChatGraph._learner_profile_guidance(context)
        if guidance:
            preference = f"{preference} Personalize with: {guidance}"
        return {
            "mode": "custom",
            "topic": original.strip(),
            "num_questions": ChatGraph._extract_question_count(text),
            "difficulty": "",
            "question_type": ChatGraph._infer_question_type(text),
            "preference": preference,
        }

    @staticmethod
    def _research_config(context: UnifiedContext, text: str) -> dict[str, Any]:
        mode = "learning_path" if ChatGraph._contains_any(text, ("学习路径", "学习路线", "学习计划", "study plan", "learning path")) else "report"
        sources: list[str] = []
        enabled = set(context.enabled_tools or [])
        if context.knowledge_bases and (not enabled or "rag" in enabled):
            sources.append("kb")
        if not enabled or "web_search" in enabled:
            sources.append("web")
        if "paper_search" in enabled:
            sources.append("papers")
        config: dict[str, Any] = {
            "mode": mode,
            "depth": "standard",
            "sources": sources or ["web"],
        }
        hints = ChatGraph._learner_profile_hints(context)
        if hints:
            config["learner_profile_hints"] = hints
        return config

    @staticmethod
    def _research_tools(context: UnifiedContext) -> list[str] | None:
        tools = list(dict.fromkeys(context.enabled_tools or []))
        if context.knowledge_bases and "rag" not in tools:
            tools.insert(0, "rag")
        if "web_search" not in tools:
            tools.append("web_search")
        return tools

    @staticmethod
    async def _run_external_video_search(
        context: UnifiedContext,
        stream: StreamBus,
    ) -> TutorState:
        graph = ChatGraph()
        decision = CoordinatorDecision(
            capability="chat",
            confidence=0.9,
            reason="Run curated video search as a tool.",
            tools=["external_video_search"],
            config=ChatGraph._external_video_tool_config(context, context.user_message),
        )
        return await graph._run_external_video_tool(context, stream, decision)

    @staticmethod
    async def _run_external_image_search(
        context: UnifiedContext,
        stream: StreamBus,
    ) -> TutorState:
        graph = ChatGraph()
        decision = CoordinatorDecision(
            capability="chat",
            confidence=0.9,
            reason="Run curated image search as a tool.",
            tools=["external_image_search"],
            config=ChatGraph._external_image_tool_config(context, context.user_message),
        )
        return await graph._run_external_image_tool(context, stream, decision)

    @staticmethod
    def _external_video_config(context: UnifiedContext) -> dict[str, Any]:
        profile_text = "\n".join(
            item
            for item in (
                context.memory_context,
                context.history_context,
                context.notebook_context,
            )
            if item
        )
        hints: dict[str, Any] = {
            **ChatGraph._learner_profile_hints(context),
            "max_results": 3,
        }
        hints.setdefault("preferences", [])
        hints.setdefault("weak_points", [])
        if profile_text and not hints.get("profile_context"):
            hints["profile_context"] = profile_text[:1200]
        if context.knowledge_bases:
            hints["knowledge_bases"] = list(context.knowledge_bases)
        return hints

    @staticmethod
    def _external_video_tool_config(context: UnifiedContext, prompt: str) -> dict[str, Any]:
        hints = ChatGraph._external_video_config(context)
        try:
            max_results = int(hints.get("max_results") or 3)
        except (TypeError, ValueError):
            max_results = 3
        try:
            search_depth = int(hints.get("search_depth") or 8)
        except (TypeError, ValueError):
            search_depth = 8
        return {
            "_direct_tool": "external_video_search",
            "topic": prompt.strip() or context.user_message,
            "prompt": prompt.strip() or context.user_message,
            "language": context.language or "zh",
            "max_results": max_results,
            "search_depth": max(4, min(search_depth, 12)),
            "learner_hints": hints,
        }

    @staticmethod
    def _external_image_config(context: UnifiedContext) -> dict[str, Any]:
        profile_text = "\n".join(
            item
            for item in (
                context.memory_context,
                context.history_context,
                context.notebook_context,
            )
            if item
        )
        hints: dict[str, Any] = {
            **ChatGraph._learner_profile_hints(context),
            "max_results": 4,
        }
        hints.setdefault("preferences", [])
        hints.setdefault("weak_points", [])
        if profile_text and not hints.get("profile_context"):
            hints["profile_context"] = profile_text[:1200]
        if context.knowledge_bases:
            hints["knowledge_bases"] = list(context.knowledge_bases)
        return hints

    @staticmethod
    def _external_image_tool_config(context: UnifiedContext, prompt: str) -> dict[str, Any]:
        hints = ChatGraph._external_image_config(context)
        try:
            max_results = int(hints.get("max_results") or 4)
        except (TypeError, ValueError):
            max_results = 4
        try:
            search_depth = int(hints.get("search_depth") or 8)
        except (TypeError, ValueError):
            search_depth = 8
        return {
            "_direct_tool": "external_image_search",
            "topic": prompt.strip() or context.user_message,
            "prompt": prompt.strip() or context.user_message,
            "language": context.language or "zh",
            "max_results": max_results,
            "search_depth": max(4, min(search_depth, 12)),
            "learner_hints": hints,
        }

    @staticmethod
    def _learner_profile_hints(context: UnifiedContext) -> dict[str, Any]:
        profile = context.metadata.get("learner_profile_context")
        if not isinstance(profile, dict):
            return {}
        raw_hints = profile.get("hints")
        if not isinstance(raw_hints, dict):
            raw_hints = {}

        hints: dict[str, Any] = {}
        for key in ("current_focus", "summary", "level", "preferred_resource"):
            value = ChatGraph._hint_text(raw_hints.get(key), limit=220)
            if value:
                hints[key] = value
        time_budget = raw_hints.get("time_budget_minutes")
        if isinstance(time_budget, (int, float)) and int(time_budget) > 0:
            hints["time_budget_minutes"] = int(time_budget)

        for key in ("goals", "preferences", "strengths", "weak_points", "mastery_needs_attention"):
            values = ChatGraph._hint_strings(raw_hints.get(key), limit=4)
            if values:
                hints[key] = values

        progress_style = raw_hints.get("progress_style")
        if isinstance(progress_style, dict):
            style = {
                "label": ChatGraph._hint_text(progress_style.get("label")),
                "strategy": ChatGraph._hint_text(progress_style.get("strategy"), limit=260),
                "preferred_resource": ChatGraph._hint_text(progress_style.get("preferred_resource")),
            }
            style = {key: value for key, value in style.items() if value}
            if style:
                hints["progress_style"] = style

        next_action = raw_hints.get("next_action")
        if isinstance(next_action, dict):
            action = {
                "kind": ChatGraph._hint_text(next_action.get("kind")),
                "title": ChatGraph._hint_text(next_action.get("title")),
                "summary": ChatGraph._hint_text(next_action.get("summary"), limit=260),
                "suggested_prompt": ChatGraph._hint_text(next_action.get("suggested_prompt"), limit=360),
                "source_type": ChatGraph._hint_text(next_action.get("source_type")),
                "source_label": ChatGraph._hint_text(next_action.get("source_label")),
                "estimated_minutes": next_action.get("estimated_minutes"),
                "priority": next_action.get("priority"),
            }
            action = {key: value for key, value in action.items() if value}
            if action:
                hints["next_action"] = action

        decision_scores = raw_hints.get("decision_scores")
        if isinstance(decision_scores, dict):
            scores = {
                key: decision_scores.get(key)
                for key in ("profile_confidence", "evidence", "weakness", "mastery", "preference", "next_action_priority")
                if decision_scores.get(key) is not None
            }
            if scores:
                hints["decision_scores"] = scores

        concepts = ChatGraph._merge_hint_strings(
            [
                hints.get("current_focus"),
                *(hints.get("weak_points") or []),
                *(hints.get("mastery_needs_attention") or []),
            ],
            limit=6,
        )
        if concepts:
            hints["concepts"] = concepts

        profile_text = ChatGraph._hint_text(profile.get("text"), limit=1200)
        if profile_text:
            hints["profile_context"] = profile_text
        return hints

    @staticmethod
    def _learner_profile_guidance(context: UnifiedContext) -> str:
        hints = ChatGraph._learner_profile_hints(context)
        if not hints:
            return ""
        parts: list[str] = []
        level = hints.get("level")
        if level:
            parts.append(f"level={level}")
        weak_points = hints.get("weak_points") or hints.get("mastery_needs_attention")
        if weak_points:
            parts.append(f"focus weak points: {', '.join(ChatGraph._hint_strings(weak_points, limit=3))}")
        preferences = hints.get("preferences")
        if preferences:
            parts.append(f"respect preferences: {', '.join(ChatGraph._hint_strings(preferences, limit=3))}")
        preferred_resource = hints.get("preferred_resource")
        if preferred_resource:
            parts.append(f"preferred resource: {preferred_resource}")
        progress_style = hints.get("progress_style")
        if isinstance(progress_style, dict) and progress_style.get("label"):
            parts.append(f"progress style: {progress_style['label']}")
        time_budget = hints.get("time_budget_minutes")
        if time_budget:
            parts.append(f"fit within about {time_budget} minutes")
        action = hints.get("next_action")
        if isinstance(action, dict) and action.get("title"):
            parts.append(f"align with next action: {action['title']}")
        return "; ".join(part for part in parts if part)[:500]

    @staticmethod
    def _hint_text(value: Any, *, limit: int = 180) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    @staticmethod
    def _hint_strings(value: Any, *, limit: int = 4) -> list[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        items: list[str] = []
        for item in raw_items:
            text = ChatGraph._hint_text(item)
            if text and text not in items:
                items.append(text)
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _merge_hint_strings(values: list[Any], *, limit: int) -> list[str]:
        merged: list[str] = []
        for value in values:
            for item in ChatGraph._hint_strings(value, limit=limit):
                if item not in merged:
                    merged.append(item)
                if len(merged) >= limit:
                    return merged
        return merged

    @staticmethod
    def _extract_question_count(text: str) -> int:
        match = re.search(r"(\d{1,2})\s*(?:道|个|题|questions?)", text)
        if not match:
            return 5 if ChatGraph._contains_any(text, ("一组", "几道", "练习题", "题目")) else 3
        return min(max(int(match.group(1)), 1), 20)

    @staticmethod
    def _infer_question_type(text: str) -> str:
        if ChatGraph._contains_any(text, ("选择题", "单选", "multiple choice", "choice")):
            return "choice"
        if ChatGraph._contains_any(text, ("判断题", "true false", "true/false")):
            return "true_false"
        if ChatGraph._contains_any(text, ("填空题", "fill blank", "fill-in")):
            return "fill_blank"
        if ChatGraph._contains_any(text, ("编程题", "coding")):
            return "coding"
        return ""

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
        return bool(value)

    @staticmethod
    def _collect_sources(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for result in tool_results:
            raw_sources = result.get("sources", [])
            if isinstance(raw_sources, list):
                sources.extend(item for item in raw_sources if isinstance(item, dict))
        return sources

