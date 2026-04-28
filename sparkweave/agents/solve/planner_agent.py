"""Planner agent for NG deep-solve."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sparkweave.agents.base_agent import BaseAgent
from sparkweave.agents.solve.tool_runtime import SolveToolRuntime
from sparkweave.core.json import parse_json_response

logger = logging.getLogger(__name__)

_MAX_CHARS_PER_RETRIEVAL = 2000
_MAX_AGGREGATE_INPUT_CHARS = 6000
_NUM_QUERIES = 3


def _build_multimodal_messages(
    system_prompt: str,
    user_prompt: str,
    image_url: str,
) -> list[dict[str, Any]]:
    """Build OpenAI-compatible multimodal messages with an image."""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


class PlannerAgent(BaseAgent):
    """Generates high-level solve plans and optional pre-retrieval context."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        api_version: str | None = None,
        token_tracker: Any | None = None,
        language: str = "en",
        tool_runtime: SolveToolRuntime | None = None,
        enable_pre_retrieve: bool = True,
    ) -> None:
        super().__init__(
            module_name="solve",
            agent_name="planner_agent",
            api_key=api_key,
            base_url=base_url,
            model=model,
            api_version=api_version,
            config=config or {},
            token_tracker=token_tracker,
            language=language,
        )
        self._tool_runtime = tool_runtime or SolveToolRuntime([], language=language)
        self._enable_pre_retrieve = enable_pre_retrieve

    async def process(
        self,
        question: str,
        scratchpad: Any | None = None,
        kb_name: str = "",
        replan: bool = False,
        memory_context: str = "",
        image_url: str | None = None,
    ) -> dict[str, Any]:
        """Generate or revise a solving plan.

        NG returns a plain dictionary rather than the legacy ``Plan`` dataclass
        so callers can serialize it directly and run without importing the old
        ``sparkweave`` package.
        """
        trace_root = "replan" if replan else "plan"
        retrieved_context = (
            await self._pre_retrieve(question, kb_name, trace_root=trace_root)
            if self._enable_pre_retrieve
            else "(retrieval disabled)"
        )
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question=question,
            scratchpad=scratchpad,
            kb_name=kb_name,
            replan=replan,
            memory_context=memory_context,
            retrieved_context=retrieved_context,
        )
        messages = (
            _build_multimodal_messages(system_prompt, user_prompt, image_url)
            if image_url
            else None
        )
        response = await self.call_llm(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            messages=messages,
            response_format={"type": "json_object"},
        )
        plan = self._parse_plan(response, question)
        plan["metadata"] = {
            "replan": replan,
            "kb_name": kb_name,
            "retrieval": retrieved_context,
            "has_image": bool(image_url),
        }
        return plan

    async def _pre_retrieve(
        self,
        question: str,
        kb_name: str,
        trace_root: str = "plan",
    ) -> str:
        """Run pre-retrieval only when RAG is enabled and a KB is selected."""
        if not kb_name or not self._tool_runtime.has_tool("rag"):
            return "(no knowledge base available)"
        try:
            queries = await self._generate_search_queries(question, trace_root=trace_root)
            retrievals = await self._parallel_retrieve(queries, kb_name, trace_root=trace_root)
            if not any(item.get("answer") for item in retrievals):
                return "(no relevant knowledge retrieved)"
            return await self._aggregate_retrieval_results(retrievals, trace_root=trace_root)
        except Exception as exc:
            logger.warning("Pre-retrieval pipeline failed: %s", exc)
            return "(knowledge retrieval failed)"

    async def _generate_search_queries(
        self,
        question: str,
        num_queries: int = _NUM_QUERIES,
        trace_root: str = "plan",
    ) -> list[str]:
        del trace_root
        template = self.get_prompt("generate_queries") if self.has_prompts() else None
        if not template:
            template = (
                "Generate {num_queries} concise and diverse knowledge-base search "
                "queries for the following question. Each query should target a "
                "different aspect.\n\n"
                "Question: {question}\n\n"
                'Return strict JSON: {{"queries": ["query1", "query2", "query3"]}}'
            )
        try:
            response = await self.call_llm(
                user_prompt=template.format(question=question, num_queries=num_queries),
                system_prompt="",
                response_format={"type": "json_object"},
            )
            payload = parse_json_response(response, logger_instance=self.logger, fallback={})
            queries = payload.get("queries", []) if isinstance(payload, dict) else []
            clean = [str(query).strip() for query in queries if str(query).strip()]
            return clean[:num_queries] or [question]
        except Exception as exc:
            logger.warning("Query generation failed, falling back to raw question: %s", exc)
            return [question]

    async def _parallel_retrieve(
        self,
        queries: list[str],
        kb_name: str,
        trace_root: str = "plan",
    ) -> list[dict[str, Any]]:
        del trace_root

        async def _single_search(query: str) -> dict[str, Any]:
            try:
                result = await self._tool_runtime.execute("rag", query, kb_name=kb_name)
                return {"query": query, "answer": result.content, "metadata": result.metadata}
            except Exception as exc:
                logger.warning("Retrieval failed for query %r: %s", query[:80], exc)
                return {"query": query, "answer": "", "metadata": {"error": str(exc)}}

        return list(await asyncio.gather(*[_single_search(query) for query in queries]))

    async def _aggregate_retrieval_results(
        self,
        retrievals: list[dict[str, Any]],
        trace_root: str = "plan",
    ) -> str:
        del trace_root
        sections: list[str] = []
        total_chars = 0
        for item in retrievals:
            answer = str(item.get("answer") or "").strip()
            if not answer:
                continue
            clipped = answer[:_MAX_CHARS_PER_RETRIEVAL]
            if total_chars + len(clipped) > _MAX_AGGREGATE_INPUT_CHARS:
                clipped = clipped[: max(0, _MAX_AGGREGATE_INPUT_CHARS - total_chars)]
            if clipped:
                sections.append(f"=== Source: {item.get('query', '?')} ===\n{clipped}")
                total_chars += len(clipped)
        if not sections:
            return "(no relevant knowledge retrieved)"

        raw_text = "\n\n".join(sections)
        template = self.get_prompt("aggregate_context") if self.has_prompts() else None
        if not template:
            template = (
                "Below are passages retrieved from a knowledge base. Consolidate them "
                "into a concise structured knowledge summary. Do not solve the user's "
                "problem; only organize the retrieved knowledge.\n\n{raw_retrieval_text}"
            )
        try:
            result = await self.call_llm(
                user_prompt=template.format(raw_retrieval_text=raw_text),
                system_prompt=(
                    "You are a knowledge organizer. Consolidate passages into a clean, "
                    "structured summary."
                ),
            )
            return result.strip() or raw_text
        except Exception as exc:
            logger.warning("Retrieval aggregation failed, using raw text: %s", exc)
            return raw_text

    def _build_system_prompt(self) -> str:
        prompt = self.get_prompt("system") if self.has_prompts() else None
        if prompt:
            return prompt
        return (
            "You are a problem-solving planner. Analyze the user's question and "
            "decompose it into ordered, verifiable sub-goals. Do not specify tool "
            "names or action instructions. Output strict JSON: "
            '{"analysis": "...", "steps": [{"id": "S1", "goal": "..."}]}'
        )

    def _build_user_prompt(
        self,
        question: str,
        scratchpad: Any | None,
        kb_name: str,
        replan: bool,
        memory_context: str = "",
        retrieved_context: str = "",
    ) -> str:
        template = self.get_prompt("user_template") if self.has_prompts() else None
        scratchpad_summary = self._scratchpad_summary(scratchpad, replan=replan)
        tools_desc = self._tool_runtime.build_planner_description(kb_name=kb_name)
        if template:
            return template.format(
                question=question,
                retrieved_context=retrieved_context or "(no retrieved knowledge)",
                tools_description=tools_desc,
                scratchpad_summary=scratchpad_summary,
                memory_context=memory_context or "(no historical memory)",
            )
        return (
            f"## Question\n{question}\n\n"
            f"## Retrieved Knowledge\n{retrieved_context or '(none)'}\n\n"
            f"## Available Tools\n{tools_desc or '(none)'}\n\n"
            f"## Progress So Far\n{scratchpad_summary}\n\n"
            f"## Memory Context\n{memory_context or '(none)'}"
        )

    def _scratchpad_summary(self, scratchpad: Any | None, *, replan: bool) -> str:
        if not replan:
            return "(initial plan - no progress yet)"
        if scratchpad is None:
            return "(replan requested - no progress snapshot available)"
        if isinstance(scratchpad, dict):
            return self._dict_scratchpad_summary(scratchpad)

        plan = getattr(scratchpad, "plan", None)
        steps = list(getattr(plan, "steps", []) or [])
        if not steps:
            return str(scratchpad)

        parts: list[str] = []
        for step in steps:
            step_id = str(getattr(step, "id", "") or "")
            status = str(getattr(step, "status", "pending") or "pending").upper()
            goal = str(getattr(step, "goal", "") or "")
            parts.append(f"[{step_id}] ({status}) {goal}".strip())
            notes = self._notes_for_step(scratchpad, step_id)
            if notes:
                parts.append(f"    Notes: {notes}")
        return "\n".join(part for part in parts if part.strip()) or str(scratchpad)

    @staticmethod
    def _dict_scratchpad_summary(scratchpad: dict[str, Any]) -> str:
        plan = scratchpad.get("plan") if isinstance(scratchpad.get("plan"), dict) else {}
        steps = plan.get("steps") if isinstance(plan, dict) else scratchpad.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return str(scratchpad)
        lines: list[str] = []
        for index, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                step_id = str(step.get("id") or f"S{index}")
                status = str(step.get("status") or "pending").upper()
                goal = str(step.get("goal") or "")
                lines.append(f"[{step_id}] ({status}) {goal}".strip())
            else:
                lines.append(str(step))
        entries = scratchpad.get("entries")
        if isinstance(entries, list) and entries:
            lines.append("Recent entries:")
            for entry in entries[-3:]:
                lines.append(f"- {entry}")
        return "\n".join(lines)

    @staticmethod
    def _notes_for_step(scratchpad: Any, step_id: str) -> str:
        if hasattr(scratchpad, "get_entries_for_step"):
            entries = scratchpad.get_entries_for_step(step_id)
        else:
            entries = getattr(scratchpad, "entries", []) or []
        notes: list[str] = []
        for entry in entries:
            entry_step_id = getattr(entry, "step_id", step_id)
            if entry_step_id != step_id:
                continue
            note = str(getattr(entry, "self_note", "") or "").strip()
            if note:
                notes.append(note)
        return " | ".join(notes)

    def _parse_plan(self, response: str, question: str) -> dict[str, Any]:
        payload = parse_json_response(response, logger_instance=self.logger, fallback={})
        if isinstance(payload, list):
            raw_steps = payload
            analysis = "Plan the solution."
        elif isinstance(payload, dict):
            raw_steps = payload.get("steps", [])
            analysis = str(payload.get("analysis") or "Plan the solution.").strip()
        else:
            raw_steps = []
            analysis = "Failed to parse plan; using fallback."

        cleaned_steps: list[dict[str, Any]] = []
        if isinstance(raw_steps, list):
            for index, raw_step in enumerate(raw_steps, start=1):
                if isinstance(raw_step, str):
                    goal = raw_step.strip()
                    step_id = f"S{index}"
                    tools_hint: list[str] = []
                elif isinstance(raw_step, dict):
                    goal = str(raw_step.get("goal") or raw_step.get("title") or "").strip()
                    step_id = str(raw_step.get("id") or f"S{index}").strip() or f"S{index}"
                    raw_tools_hint = raw_step.get("tools_hint", [])
                    if isinstance(raw_tools_hint, str):
                        tools_hint = [raw_tools_hint]
                    elif isinstance(raw_tools_hint, list):
                        tools_hint = [str(item) for item in raw_tools_hint if str(item).strip()]
                    else:
                        tools_hint = []
                else:
                    continue
                if not goal:
                    continue
                step: dict[str, Any] = {"id": step_id, "goal": goal}
                if tools_hint:
                    step["tools_hint"] = tools_hint
                cleaned_steps.append(step)

        if not cleaned_steps:
            cleaned_steps = [{"id": "S1", "goal": f"Solve the problem: {question}"}]

        return {"analysis": analysis, "steps": cleaned_steps}


__all__ = ["PlannerAgent"]

