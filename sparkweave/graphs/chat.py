"""Minimal LangGraph chat workflow with SparkWeave tool support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
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
from sparkweave.llm import chat_messages, create_chat_model
from sparkweave.tools import LangChainToolRegistry

MAX_PARALLEL_TOOL_CALLS = 8

DELEGABLE_CAPABILITIES = {
    "deep_question",
    "deep_research",
    "deep_solve",
    "external_video_search",
    "math_animator",
    "visualize",
}

SPECIALIST_LABELS = {
    "deep_question": "Question Generation Agent",
    "deep_research": "Research and Learning Path Agent",
    "deep_solve": "Deep Solve Agent",
    "external_video_search": "Learning Video Search Agent",
    "math_animator": "Math Animation Agent",
    "visualize": "Knowledge Visualization Agent",
}

VISUALIZE_TERMS = (
    "可视化",
    "图示",
    "图解",
    "画图",
    "画一个",
    "生成图",
    "流程图",
    "结构图",
    "关系图",
    "思维导图",
    "知识图谱",
    "mermaid",
    "flowchart",
    "diagram",
    "visualize",
    "chart",
    "graph",
)
ANIMATION_TERMS = (
    "动画",
    "动态演示",
    "视频讲解",
    "短视频",
    "manim",
    "animation",
    "animate",
    "video",
)
VIDEO_SEARCH_TERMS = (
    "\u627e\u89c6\u9891",
    "\u63a8\u8350\u89c6\u9891",
    "\u89c6\u9891\u63a8\u8350",
    "\u89c6\u9891\u8bb2\u89e3",
    "\u5b66\u4e60\u89c6\u9891",
    "\u8bfe\u7a0b\u89c6\u9891",
    "\u89c6\u9891\u8d44\u6e90",
    "\u7cbe\u9009\u89c6\u9891",
    "\u516c\u5f00\u89c6\u9891",
    "\u516c\u5f00\u8bfe\u89c6\u9891",
    "\u516c\u5f00\u8bfe",
    "\u7f51\u8bfe",
    "\u7f51\u8bfe\u89c6\u9891",
    "\u8bb2\u89e3\u89c6\u9891",
    "\u6559\u5b66\u89c6\u9891",
    "b\u7ad9",
    "\u54d4\u54e9\u54d4\u54e9",
    "bilibili",
    "youtube",
    "external video",
    "find video",
    "recommend video",
    "learning video",
    "lecture video",
    "video resource",
)
QUESTION_TERMS = (
    "出题",
    "生成题",
    "题目生成",
    "练习题",
    "测试题",
    "选择题",
    "判断题",
    "填空题",
    "quiz",
    "question set",
    "generate questions",
)
RESEARCH_TERMS = (
    "调研",
    "研究报告",
    "综述",
    "学习路径",
    "学习路线",
    "学习计划",
    "资源推荐",
    "规划",
    "research",
    "report",
    "learning path",
    "study plan",
)
SOLVE_TERMS = (
    "求解",
    "解题",
    "证明",
    "推导",
    "计算",
    "求极限",
    "求导",
    "积分",
    "答案是",
    "怎么做",
    "solve",
    "prove",
    "derive",
    "calculate",
)
NO_DELEGATE_TERMS = (
    "不用调用",
    "不要调用",
    "不要画图",
    "不用画图",
    "只回答",
    "直接回答",
    "just answer",
    "no diagram",
    "no tools",
)
PROFILE_GUIDED_TERMS = (
    "继续",
    "开始学习",
    "继续学习",
    "下一步",
    "下一步学什么",
    "我该学什么",
    "我该做什么",
    "按画像",
    "根据画像",
    "按我的画像",
    "帮我安排",
    "开始今天",
    "继续今天",
    "start learning",
    "continue learning",
    "next step",
    "what should i learn",
    "what should i do next",
)


@dataclass(frozen=True)
class CoordinatorDecision:
    capability: str = "chat"
    confidence: float = 0.0
    reason: str = "Use the default chat agent."
    config: dict[str, Any] | None = None
    tools: list[str] | None = None

    @property
    def delegates(self) -> bool:
        return self.capability in DELEGABLE_CAPABILITIES


class ChatGraph:
    """LangGraph implementation of the default chat capability."""

    source = "chat"

    def __init__(
        self,
        *,
        model: Any | None = None,
        tool_registry: LangChainToolRegistry | None = None,
        max_tool_rounds: int = 3,
        coordinator_enabled: bool = True,
        specialist_runner: Callable[[str, UnifiedContext, StreamBus], Awaitable[TutorState]] | None = None,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry or LangChainToolRegistry()
        self.max_tool_rounds = max_tool_rounds
        self.coordinator_enabled = coordinator_enabled
        self.specialist_runner = specialist_runner
        self._compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        payload = extract_answer_now_payload(context)
        if payload is not None:
            state = context_to_state(context, stream=stream)
            return await self._run_answer_now(state, payload)

        decision = await self._coordinate(context, stream)
        if decision.delegates:
            return await self._run_specialist(context, stream, decision)

        state = context_to_state(context, stream=stream)
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
        if len(calls) > MAX_PARALLEL_TOOL_CALLS:
            await stream.progress(
                f"Model requested {len(calls)} tool calls; only {MAX_PARALLEL_TOOL_CALLS} can run in parallel.",
                source=self.source,
                stage="acting",
                metadata={"trace_kind": "progress", "reason": "too_many_tool_calls"},
            )
            calls = calls[:MAX_PARALLEL_TOOL_CALLS]

        async with stream.stage("acting", source=self.source):
            tasks = [
                self._execute_tool_call(call, context, stream, tool_index=index)
                for index, call in enumerate(calls)
            ]
            records = await asyncio.gather(*tasks)

        tool_messages = [
            ToolMessage(
                content=record["result"],
                tool_call_id=record["id"],
                name=record["name"],
            )
            for record in records
        ]
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
        name = str(call.get("name") or "").strip()
        args = dict(call.get("args") or {})
        tool_call_id = str(call.get("id") or name or "tool-call")
        args = self._augment_tool_args(name, args, context)
        retrieve_meta = self._retrieve_metadata(
            name=name,
            args=args,
            tool_call_id=tool_call_id,
            tool_index=tool_index,
            context=context,
        )

        await stream.tool_call(
            tool_name=name,
            args=args,
            source=self.source,
            stage="acting",
            metadata={
                "trace_kind": "tool_call",
                "tool_call_id": tool_call_id,
                "tool_name": name,
                "tool_index": tool_index,
            },
        )
        try:
            execute_args = dict(args)
            if retrieve_meta is not None:
                await stream.progress(
                    f"Query: {retrieve_meta.get('query')}"
                    if retrieve_meta.get("query")
                    else "Retrieving from the knowledge base...",
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

                execute_args["event_sink"] = _event_sink

            result = await self.tool_registry.execute(name, **execute_args)
            result_text = result.content or "(empty tool result)"
            success = result.success
            sources = result.sources
            metadata = result.metadata
            if retrieve_meta is not None:
                await stream.progress(
                    f"Retrieve complete ({len(result_text)} chars)",
                    source=self.source,
                    stage="acting",
                    metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "complete"},
                )
        except Exception as exc:
            result_text = f"Error executing {name}: {exc}"
            success = False
            sources = []
            metadata = {"error": str(exc)}
            if retrieve_meta is not None:
                await stream.error(
                    f"Retrieve failed: {exc}",
                    source=self.source,
                    stage="acting",
                    metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "error"},
                )

        await stream.tool_result(
            tool_name=name,
            result=result_text,
            source=self.source,
            stage="acting",
            metadata={
                "trace_kind": "tool_result",
                "tool_call_id": tool_call_id,
                "tool_name": name,
                "tool_index": tool_index,
                "success": success,
                "sources": sources,
            },
        )
        return {
            "id": tool_call_id,
            "name": name,
            "arguments": args,
            "result": result_text,
            "success": success,
            "sources": sources,
            "metadata": metadata,
        }

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
        if name == "web_search":
            augmented.setdefault("query", context.user_message)
        if name == "code_execution":
            augmented.setdefault("intent", context.user_message)
            augmented.setdefault("session_id", context.session_id)
            augmented.setdefault("turn_id", str(context.metadata.get("turn_id", "") or ""))
            augmented.setdefault("feature", "chat")
        if name in {"reason", "brainstorm"}:
            augmented.setdefault("context", context.user_message)
        return augmented

    async def _coordinate(
        self,
        context: UnifiedContext,
        stream: StreamBus,
    ) -> CoordinatorDecision:
        if not self.coordinator_enabled:
            return CoordinatorDecision(reason="Coordinator disabled for this graph instance.")
        decision = self._decide_specialist(context)
        metadata = {
            "trace_kind": "coordinator_decision",
            "capability": decision.capability,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "delegated": decision.delegates,
            "agent_cluster": SPECIALIST_LABELS.get(decision.capability, "Dialogue Coordinator Agent"),
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
                await stream.progress(
                    "Keeping this turn in the default chat agent.",
                    source="dialogue_coordinator",
                    stage="coordinating",
                    metadata=metadata,
                )
        return decision

    def _decide_specialist(self, context: UnifiedContext) -> CoordinatorDecision:
        overrides = dict(context.config_overrides or {})
        if not self._truthy(overrides.get("auto_delegate", True)):
            return CoordinatorDecision(reason="Automatic specialist delegation is disabled.")

        if context.metadata.get("delegated_by_coordinator"):
            return CoordinatorDecision(reason="This turn has already been delegated once.")

        forced = str(
            overrides.get("delegate_capability")
            or overrides.get("coordinator_capability")
            or ""
        ).strip()
        if forced:
            return self._forced_decision(forced)

        text = self._normalized_text(context)
        if not text:
            return CoordinatorDecision(reason="Empty user request.")
        if self._contains_any(text, NO_DELEGATE_TERMS):
            return CoordinatorDecision(reason="The learner asked for a direct answer.")

        if self._looks_like_external_video_request(text):
            return CoordinatorDecision(
                capability="external_video_search",
                confidence=0.9,
                reason="The learner asked to find or recommend public learning videos.",
                config=self._external_video_config(context),
            )

        if self._contains_any(text, ANIMATION_TERMS):
            return CoordinatorDecision(
                capability="math_animator",
                confidence=0.92,
                reason="The learner asked for an animation or video-style explanation.",
                config=self._math_animator_config(context, text),
            )

        if self._contains_any(text, QUESTION_TERMS):
            return CoordinatorDecision(
                capability="deep_question",
                confidence=0.9,
                reason="The learner asked to generate interactive practice questions.",
                config=self._question_config(context, context.user_message, text),
            )

        if self._contains_any(text, VISUALIZE_TERMS) and self._has_visual_action(text):
            return CoordinatorDecision(
                capability="visualize",
                confidence=0.88,
                reason="The learner asked for a diagram or knowledge visualization.",
                config=self._visualize_config(context, text),
            )

        if self._contains_any(text, RESEARCH_TERMS):
            return CoordinatorDecision(
                capability="deep_research",
                confidence=0.82,
                reason="The learner asked for research, planning, or resource organization.",
                config=self._research_config(context, text),
                tools=self._research_tools(context),
            )

        if self._looks_like_solve_request(text):
            return CoordinatorDecision(
                capability="deep_solve",
                confidence=0.8,
                reason="The learner asked for a problem-solving or derivation workflow.",
                config={"detailed_answer": True},
            )

        profile_guided = self._profile_guided_decision(context, text)
        if profile_guided is not None:
            return profile_guided

        return CoordinatorDecision()

    async def _run_specialist(
        self,
        context: UnifiedContext,
        stream: StreamBus,
        decision: CoordinatorDecision,
    ) -> TutorState:
        delegated_context = self._delegated_context(context, decision)
        profile_hints = self._learner_profile_hints(context)
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
        if capability == "external_video_search":
            return await ChatGraph._run_external_video_search(context, stream)
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
        config = {
            **dict(context.config_overrides or {}),
            **dict(decision.config or {}),
        }
        rewritten_user_message = str(config.pop("_coordinator_user_message", "") or "").strip()
        config.pop("auto_delegate", None)
        config.pop("delegate_capability", None)
        config.pop("coordinator_capability", None)
        tools = decision.tools if decision.tools is not None else context.enabled_tools
        return replace(
            context,
            user_message=rewritten_user_message or context.user_message,
            active_capability=decision.capability,
            enabled_tools=list(tools) if tools is not None else None,
            config_overrides=config,
            metadata={
                **dict(context.metadata or {}),
                "delegated_by_coordinator": "chat",
                "coordinator_decision": {
                    "capability": decision.capability,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                },
                "coordinator_rewritten_prompt": rewritten_user_message,
            },
        )

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
        video_search_pattern = re.search(
            r"(找|推荐|检索|搜|公开|资源|链接|b站|哔哩哔哩|youtube).{0,12}(视频|网课|公开课)"
            r"|(?:视频|网课|公开课).{0,12}(找|推荐|检索|搜|资源|链接|公开)",
            text,
            flags=re.IGNORECASE,
        )
        if not ChatGraph._contains_any(text, VIDEO_SEARCH_TERMS) and not video_search_pattern:
            return False
        generate_markers = (
            "\u751f\u6210\u89c6\u9891",
            "\u751f\u6210\u4e00\u4e2a\u89c6\u9891",
            "\u751f\u6210\u4e2a\u89c6\u9891",
            "\u5236\u4f5c\u89c6\u9891",
            "\u505a\u4e00\u4e2a\u89c6\u9891",
            "\u505a\u4e2a\u89c6\u9891",
            "\u751f\u6210\u77ed\u89c6\u9891",
            "\u52a8\u753b",
            "manim",
            "generate video",
            "create video",
            "make video",
            "animation",
            "animate",
        )
        find_markers = (
            "\u627e",
            "\u63a8\u8350",
            "\u68c0\u7d22",
            "\u641c",
            "\u516c\u5f00",
            "\u8d44\u6e90",
            "\u94fe\u63a5",
            "find",
            "recommend",
            "search",
            "link",
            "resource",
        )
        generate_pattern = re.search(r"(生成|制作|做).{0,8}(视频|短视频|动画)", text, flags=re.IGNORECASE)
        if (ChatGraph._contains_any(text, generate_markers) or generate_pattern) and not (
            ChatGraph._contains_any(text, find_markers) or video_search_pattern
        ):
            return False
        return True

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
            config = ChatGraph._external_video_config(context)
            config.update({"topic": prompt, "prompt": prompt})
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
        from sparkweave.services.video_search import recommend_learning_videos

        hints = ChatGraph._external_video_config(context)
        progress_tasks: list[asyncio.Task[None]] = []

        def _event_sink(event_type: str, payload: dict[str, Any]) -> None:
            message = str(payload.get("message") or "")
            stage = str(payload.get("stage") or event_type or "searching")
            progress_tasks.append(
                asyncio.create_task(
                    stream.progress(
                        message,
                        source="external_video_search",
                        stage=stage,
                        metadata={
                            "trace_kind": str(event_type or "video_search"),
                            "capability": "external_video_search",
                            **payload,
                        },
                    )
                )
            )

        async with stream.stage(
            "searching",
            source="external_video_search",
            metadata={
                "trace_kind": "agent_work",
                "capability": "external_video_search",
                "agent_cluster": SPECIALIST_LABELS["external_video_search"],
            },
        ):
            overrides = dict(context.config_overrides or {})
            topic = str(overrides.get("topic") or overrides.get("prompt") or context.user_message).strip()
            prompt = str(overrides.get("prompt") or topic or context.user_message).strip()
            result = await recommend_learning_videos(
                topic=topic or context.user_message,
                learner_hints=hints,
                prompt=prompt or context.user_message,
                language=context.language or "zh",
                max_results=int(hints.get("max_results") or 3),
                event_sink=_event_sink,
            )
            if progress_tasks:
                await asyncio.gather(*progress_tasks)

        response = str(result.get("response") or "")
        async with stream.stage("responding", source="external_video_search"):
            if response:
                await stream.content(response, source="external_video_search", stage="responding")
            await stream.result(
                {
                    **result,
                    "runtime": "langgraph",
                    "capability": "external_video_search",
                },
                source="external_video_search",
            )
        return {
            "final_answer": response,
            "external_video_result": result,
        }

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
            }
            action = {key: value for key, value in action.items() if value}
            if action:
                hints["next_action"] = action

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

