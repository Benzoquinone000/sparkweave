"""LangGraph implementation of SparkWeave's deep-solve capability."""

from __future__ import annotations

import json
import re
from typing import Any

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.core.dependencies import dependency_error
from sparkweave.core.json import parse_json_response
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
from sparkweave.llm import chat_messages, create_chat_model
from sparkweave.tools import LangChainToolRegistry

SOLVE_SYSTEM_PROMPT = """\
You are SparkWeave's problem-solving graph. Solve learning problems carefully,
ground claims in available tool results, verify the reasoning, and then write a
clear final answer for the learner.
"""


class DeepSolveGraph:
    """Explicit LangGraph flow for planning, tools, solving, verification, writing."""

    source = "deep_solve"

    def __init__(
        self,
        *,
        model: Any | None = None,
        tool_registry: LangChainToolRegistry | None = None,
        max_tool_calls: int = 3,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry or LangChainToolRegistry()
        self.max_tool_calls = max_tool_calls
        self._compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        state = context_to_state(
            context,
            stream=stream,
            system_prompt=SOLVE_SYSTEM_PROMPT,
        )
        payload = extract_answer_now_payload(context)
        if payload is not None:
            return await self._run_answer_now(state, payload)

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
        builder.add_node("plan", self._plan_node)
        builder.add_node("select_tools", self._select_tools_node)
        builder.add_node("execute_tools", self._execute_tools_node)
        builder.add_node("solve", self._solve_node)
        builder.add_node("verify", self._verify_node)
        builder.add_node("write", self._write_node)

        builder.add_edge(START, "plan")
        builder.add_edge("plan", "select_tools")
        builder.add_conditional_edges(
            "select_tools",
            self._route_after_tool_selection,
            {"tools": "execute_tools", "solve": "solve"},
        )
        builder.add_edge("execute_tools", "solve")
        builder.add_edge("solve", "verify")
        builder.add_edge("verify", "write")
        builder.add_edge("write", END)
        self._compiled = builder.compile()
        return self._compiled

    async def _plan_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        async with stream.stage("planning", source=self.source):
            await stream.progress(
                "Planning solution steps...",
                source=self.source,
                stage="planning",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=(
                    "Create a compact, sufficient plan for solving the problem. "
                    'Return strict JSON: {"analysis": str, "steps": '
                    '[{"id": "S1", "goal": str}]}.'
                ),
                user=self._question_block(state),
            )
            raw = message_text(response)
            plan = self._parse_plan(raw, state["user_message"])
            await stream.thinking(
                self._format_plan(plan),
                source=self.source,
                stage="planning",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="planning",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"plan": plan}

    async def _select_tools_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        enabled_tools = self._enabled_tools(state)
        if "rag" in enabled_tools and not state.get("knowledge_bases"):
            await stream.progress(
                "RAG was enabled, but no knowledge base is attached; skipping RAG for this turn.",
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "warning", "reason": "rag_without_kb"},
            )
            enabled_tools = [name for name in enabled_tools if name != "rag"]
        if not enabled_tools:
            return {"pending_tool_calls": []}

        async with stream.stage("reasoning", source=self.source):
            model = self._get_model()
            tools = self.tool_registry.get_tools(enabled_tools)
            if tools and hasattr(model, "bind_tools"):
                model = model.bind_tools(tools)
                await stream.progress(
                    "Choosing helpful tools...",
                    source=self.source,
                    stage="reasoning",
                    metadata={"trace_kind": "call_status", "call_state": "running"},
                )
                response = await model.ainvoke(
                    chat_messages(
                        system=(
                            "Decide whether external tools are needed before solving. "
                            "Call at most three tools. If the plan can be solved "
                            "directly, answer with a short note and no tool calls."
                        ),
                        user=(
                            f"{self._question_block(state)}\n\n"
                            f"Plan:\n{self._format_plan(state.get('plan', {}))}"
                        ),
                    )
                )
                calls = self._extract_tool_calls(response)[: self.max_tool_calls]
                note = message_text(response).strip()
                if note:
                    await stream.thinking(
                        note,
                        source=self.source,
                        stage="reasoning",
                        metadata={"trace_kind": "llm_output"},
                    )
                await stream.progress(
                    "",
                    source=self.source,
                    stage="reasoning",
                    metadata={"trace_kind": "call_status", "call_state": "complete"},
                )
                return {"pending_tool_calls": calls}

            fallback_calls = self._fallback_tool_calls(state, enabled_tools)
            return {"pending_tool_calls": fallback_calls[: self.max_tool_calls]}

    async def _execute_tools_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        context = state.get("context")
        calls = list(state.get("pending_tool_calls", []))[: self.max_tool_calls]
        if not calls:
            return {"tool_results": state.get("tool_results", [])}

        records: list[dict[str, Any]] = []
        async with stream.stage("reasoning", source=self.source):
            for call in calls:
                records.append(await self._execute_tool_call(call, context, stream))

        previous = list(state.get("tool_results", []))
        previous.extend(records)
        return {"tool_results": previous, "pending_tool_calls": []}

    async def _solve_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        async with stream.stage("reasoning", source=self.source):
            await stream.progress(
                "Solving from the plan and observations...",
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=(
                    "Work through the solution. Use the plan and any tool "
                    "observations. Be rigorous, but this is still a draft; do "
                    "not write polished final prose yet."
                ),
                user=self._solve_context(state),
            )
            draft = message_text(response).strip()
            await stream.thinking(
                draft,
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"draft_answer": draft}

    async def _verify_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        async with stream.stage("reasoning", source=self.source):
            await stream.progress(
                "Checking the solution...",
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=(
                    "Review the draft solution for correctness, missing cases, "
                    "unsupported claims, and calculation errors. Return concise "
                    "verification notes."
                ),
                user=(
                    f"{self._solve_context(state)}\n\n"
                    f"Draft solution:\n{state.get('draft_answer', '')}"
                ),
            )
            verification = message_text(response).strip()
            await stream.observation(
                verification,
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "verification"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="reasoning",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"verification": verification}

    async def _write_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        async with stream.stage("writing", source=self.source):
            response = await self._ainvoke(
                system=(
                    "Write the final answer for the learner. Use clear structure, "
                    "include necessary reasoning, and do not mention internal graph "
                    "nodes. If tool evidence was used, integrate it naturally."
                ),
                user=(
                    f"{self._solve_context(state)}\n\n"
                    f"Draft solution:\n{state.get('draft_answer', '')}\n\n"
                    f"Verification notes:\n{state.get('verification', '')}"
                ),
            )
            final_answer = message_text(response).strip()
            if not final_answer:
                final_answer = state.get("draft_answer", "") or "No solution was generated."
            sources = self._collect_sources(state.get("tool_results", []))
            if sources:
                await stream.sources(sources, source=self.source, stage="writing")
            await stream.content(final_answer, source=self.source, stage="writing")
            await stream.result(
                {
                    "response": final_answer,
                    "plan": state.get("plan", {}),
                    "verification": state.get("verification", ""),
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
        notice = skip_notice(
            capability=self.source,
            stages_skipped=["planning", "reasoning"],
        )

        async with stream.stage("writing", source=self.source):
            await stream.progress(
                "Synthesizing final answer from the partial trace...",
                source=self.source,
                stage="writing",
                metadata=answer_now_progress_metadata("running"),
            )
            response = await self._ainvoke(
                system=(
                    "You are the writer component of SparkWeave. The user is "
                    "already waiting, so produce the final user-facing answer "
                    "now using only the partial trace provided. Do not plan "
                    "further, do not call tools, and do not mention internal "
                    "graph nodes. If something is uncertain, say so briefly."
                ),
                user=answer_now_user_prompt(
                    original=original,
                    partial=partial,
                    trace_summary=trace_summary,
                    final_instruction=(
                        "Produce the final user-facing answer using only this context."
                    ),
                ),
            )
            final_answer = message_text(response).strip()
            if not final_answer:
                final_answer = partial or "I could not synthesize a final answer from the partial trace."
            body = answer_now_body(final_answer, notice=notice)
            await stream.content(body, source=self.source, stage="writing")
            await stream.progress(
                "",
                source=self.source,
                stage="writing",
                metadata=answer_now_progress_metadata("complete"),
            )
            await stream.result(
                {
                    "response": body,
                    "output_dir": "",
                    "metadata": answer_now_metadata(runtime="langgraph"),
                    "runtime": "langgraph",
                },
                source=self.source,
            )
        state["user_message"] = original
        state["final_answer"] = body
        state["artifacts"] = {
            **dict(state.get("artifacts", {}) or {}),
            "deep_solve": {"answer_now": True, "runtime": "langgraph"},
        }
        return state

    def _route_after_tool_selection(self, state: TutorState) -> str:
        return "tools" if state.get("pending_tool_calls") else "solve"

    async def _ainvoke(self, *, system: str, user: str) -> Any:
        return await self._get_model().ainvoke(chat_messages(system=system, user=user))

    def _get_model(self) -> Any:
        if self.model is not None:
            return self.model
        self.model = create_chat_model(temperature=0.1)
        return self.model

    async def _execute_tool_call(
        self,
        call: dict[str, Any],
        context: UnifiedContext | None,
        stream: StreamBus,
    ) -> dict[str, Any]:
        name = str(call.get("name") or "").strip()
        args = self._augment_tool_args(name, dict(call.get("args") or {}), context)
        tool_call_id = str(call.get("id") or name or "solve-tool-call")

        await stream.tool_call(
            tool_name=name,
            args=args,
            source=self.source,
            stage="reasoning",
            metadata={
                "trace_kind": "tool_call",
                "tool_call_id": tool_call_id,
                "tool_name": name,
            },
        )
        try:
            result = await self.tool_registry.execute(name, **args)
            result_text = result.content or "(empty tool result)"
            success = result.success
            sources = result.sources
            metadata = result.metadata
        except Exception as exc:
            result_text = f"Error executing {name}: {exc}"
            success = False
            sources = []
            metadata = {"error": str(exc)}

        await stream.tool_result(
            tool_name=name,
            result=result_text,
            source=self.source,
            stage="reasoning",
            metadata={
                "trace_kind": "tool_result",
                "tool_call_id": tool_call_id,
                "tool_name": name,
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

    def _enabled_tools(self, state: TutorState) -> list[str]:
        enabled = list(state.get("enabled_tools") or [])
        if not enabled:
            return []
        known = set(self.tool_registry.names())
        return [name for name in enabled if name in known]

    @staticmethod
    def _extract_tool_calls(message: Any) -> list[dict[str, Any]]:
        calls = getattr(message, "tool_calls", None) or []
        normalized: list[dict[str, Any]] = []
        for index, call in enumerate(calls):
            if isinstance(call, dict):
                normalized.append(
                    {
                        "id": call.get("id") or f"solve-tool-{index}",
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
                    "id": getattr(call, "id", f"solve-tool-{index}"),
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
        if name in {"rag", "web_search", "paper_search"}:
            augmented.setdefault("query", context.user_message)
        if name == "code_execution":
            augmented.setdefault("intent", context.user_message)
            augmented.setdefault("timeout", 30)
            augmented.setdefault("session_id", context.session_id)
            augmented.setdefault("turn_id", str(context.metadata.get("turn_id", "") or ""))
            augmented.setdefault("feature", "deep_solve")
        if name in {"reason", "brainstorm"}:
            augmented.setdefault("query", context.user_message)
            augmented.setdefault("context", context.metadata.get("conversation_context_text", ""))
        return augmented

    def _fallback_tool_calls(
        self,
        state: TutorState,
        enabled_tools: list[str],
    ) -> list[dict[str, Any]]:
        context = state.get("context")
        if "rag" in enabled_tools and state.get("knowledge_bases"):
            return [
                {
                    "id": "fallback-rag",
                    "name": "rag",
                    "args": {
                        "query": state["user_message"],
                        "kb_name": state["knowledge_bases"][0],
                    },
                }
            ]
        if "web_search" in enabled_tools:
            return [
                {
                    "id": "fallback-web-search",
                    "name": "web_search",
                    "args": {"query": state["user_message"]},
                }
            ]
        if "code_execution" in enabled_tools and self._looks_computational(state["user_message"]):
            return [
                {
                    "id": "fallback-code",
                    "name": "code_execution",
                    "args": {
                        "intent": context.user_message if context else state["user_message"],
                    },
                }
            ]
        return []

    @staticmethod
    def _parse_plan(raw: str, question: str) -> dict[str, Any]:
        parsed = parse_json_response(raw, fallback={})
        if not isinstance(parsed, dict):
            parsed = {}
        steps = parsed.get("steps")
        if not isinstance(steps, list) or not steps:
            steps = [{"id": "S1", "goal": f"Solve the problem: {question}"}]
        cleaned_steps = []
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            goal = str(step.get("goal") or "").strip()
            if not goal:
                continue
            cleaned_steps.append(
                {
                    "id": str(step.get("id") or f"S{index}").strip() or f"S{index}",
                    "goal": goal,
                }
            )
        if not cleaned_steps:
            cleaned_steps = [{"id": "S1", "goal": f"Solve the problem: {question}"}]
        return {
            "analysis": str(parsed.get("analysis") or "Plan the solution.").strip(),
            "steps": cleaned_steps,
        }

    @staticmethod
    def _format_plan(plan: dict[str, Any]) -> str:
        if not plan:
            return "(no plan)"
        lines = [str(plan.get("analysis") or "").strip()]
        steps = plan.get("steps") or []
        for step in steps:
            if isinstance(step, dict):
                lines.append(f"- {step.get('id', '')}: {step.get('goal', '')}")
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _question_block(state: TutorState) -> str:
        return f"Question:\n{state['user_message']}\n\nLanguage: {state.get('language', 'en')}"

    def _solve_context(self, state: TutorState) -> str:
        return "\n\n".join(
            [
                self._question_block(state),
                f"Plan:\n{self._format_plan(state.get('plan', {}))}",
                f"Tool observations:\n{self._format_tool_results(state.get('tool_results', []))}",
            ]
        )

    @staticmethod
    def _format_tool_results(tool_results: list[dict[str, Any]]) -> str:
        if not tool_results:
            return "(none)"
        blocks: list[str] = []
        for index, result in enumerate(tool_results, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"{index}. {result.get('name', 'tool')}",
                        f"arguments: {json.dumps(result.get('arguments', {}), ensure_ascii=False)}",
                        f"success: {result.get('success')}",
                        f"result: {str(result.get('result', '')).strip()[:3000]}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _collect_sources(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for result in tool_results:
            raw_sources = result.get("sources", [])
            if isinstance(raw_sources, list):
                sources.extend(item for item in raw_sources if isinstance(item, dict))
        return sources

    @staticmethod
    def _looks_computational(text: str) -> bool:
        return bool(
            re.search(
                r"\b(calculate|compute|solve|integral|derivative|matrix|equation|simulate|plot)\b",
                text,
                flags=re.IGNORECASE,
            )
        )

