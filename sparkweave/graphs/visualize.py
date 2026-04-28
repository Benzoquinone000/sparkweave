"""LangGraph implementation of SparkWeave's visualize capability."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

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
    parse_answer_now_json,
    skip_notice,
)
from sparkweave.llm import ainvoke_json as llm_ainvoke_json
from sparkweave.llm import chat_messages, create_chat_model

VISUALIZE_SYSTEM_PROMPT = """\
You are SparkWeave's visualization graph. Analyze the learner's request,
generate renderable SVG, Chart.js, or Mermaid code, review it, and return a
viewer-ready result. Prefer correctness and direct renderability over ornament.
"""

RenderType = Literal["svg", "chartjs", "mermaid"]


class VisualizationAnalysisPayload(BaseModel):
    render_type: RenderType = Field(
        description="Whether to render as raw SVG, Chart.js config, or Mermaid DSL."
    )
    description: str = ""
    data_description: str = ""
    chart_type: str = ""
    visual_elements: list[str] = Field(default_factory=list)
    rationale: str = ""


class VisualizationReviewPayload(BaseModel):
    optimized_code: str
    changed: bool = False
    review_notes: str = ""


class VisualizeGraph:
    """Explicit graph for visualization analysis, code generation, and review."""

    source = "visualize"

    def __init__(self, *, model: Any | None = None) -> None:
        self.model = model
        self._compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        state = context_to_state(
            context,
            stream=stream,
            system_prompt=VISUALIZE_SYSTEM_PROMPT,
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
        builder.add_node("analyze", self._analyze_node)
        builder.add_node("generate", self._generate_node)
        builder.add_node("review", self._review_node)
        builder.add_node("write", self._write_node)

        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "generate")
        builder.add_edge("generate", "review")
        builder.add_edge("review", "write")
        builder.add_edge("write", END)
        self._compiled = builder.compile()
        return self._compiled

    async def _analyze_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        config = self._config(state)
        async with stream.stage("analyzing", source=self.source):
            await stream.progress(
                "Analyzing visualization requirements...",
                source=self.source,
                stage="analyzing",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            payload = await self._ainvoke_json(
                system=(
                    "Analyze the visualization request and choose the best render type. "
                    "Return JSON only. Use svg for custom illustrations/schematics, "
                    "chartjs for quantitative charts, and mermaid for flowcharts, "
                    "sequence diagrams, state diagrams, mindmaps, and similar structures."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Conversation context:\n{self._history_context(state) or '(none)'}\n\n"
                    f"Render mode hint: {config['render_mode']}\n\n"
                    "Return JSON with keys: render_type, description, data_description, "
                    "chart_type, visual_elements, rationale."
                ),
                schema=VisualizationAnalysisPayload,
            )
            analysis = self._normalize_analysis(payload, state, config["render_mode"])
            await stream.thinking(
                self._format_analysis(analysis),
                source=self.source,
                stage="analyzing",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                f"Render type: {analysis['render_type']} - {analysis['description']}",
                source=self.source,
                stage="analyzing",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"visualization_analysis": analysis}

    async def _generate_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        analysis = self._analysis(state)
        async with stream.stage("generating", source=self.source):
            await stream.progress(
                "Generating visualization code...",
                source=self.source,
                stage="generating",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=self._code_system_prompt(analysis["render_type"]),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Conversation context:\n{self._history_context(state) or '(none)'}\n\n"
                    f"Analysis:\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n\n"
                    "Generate the visualization code now."
                ),
            )
            raw = message_text(response)
            code = self._extract_code(raw, analysis["render_type"])
            if not code:
                code = self._fallback_code(analysis, state["user_message"])
            await stream.thinking(
                self._code_preview(code),
                source=self.source,
                stage="generating",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "Code generated.",
                source=self.source,
                stage="generating",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"visualization_code": code}

    async def _review_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        analysis = self._analysis(state)
        code = state.get("visualization_code", "")
        async with stream.stage("reviewing", source=self.source):
            await stream.progress(
                "Reviewing and optimizing code...",
                source=self.source,
                stage="reviewing",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            payload = await self._ainvoke_json(
                system=(
                    "Review the generated visualization code for renderability, "
                    "syntax, safety, and alignment with the analysis. Return JSON only. "
                    "If changes are needed, put the final code in optimized_code."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Render type: {analysis['render_type']}\n"
                    f"Analysis:\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n\n"
                    f"Generated code:\n{code}\n\n"
                    "Return JSON with keys: optimized_code, changed, review_notes."
                ),
                schema=VisualizationReviewPayload,
            )
            review = self._normalize_review(payload, code)
            if review["changed"]:
                message = f"Code optimized: {review['review_notes']}"
            else:
                message = "Code looks good - no changes needed."
            await stream.observation(
                review["review_notes"] or message,
                source=self.source,
                stage="reviewing",
                metadata={"trace_kind": "review"},
            )
            await stream.progress(
                message,
                source=self.source,
                stage="reviewing",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"visualization_review": review}

    async def _write_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        analysis = self._analysis(state)
        review = self._review(state)
        final_code = review["optimized_code"] or state.get("visualization_code", "")
        lang_tag = self._language_tag(analysis["render_type"])
        content_md = f"```{lang_tag}\n{final_code}\n```"

        await stream.content(content_md, source=self.source, stage="reviewing")
        await stream.result(
            {
                "response": self._viewer_summary(analysis),
                "render_type": analysis["render_type"],
                "code": {
                    "language": lang_tag,
                    "content": final_code,
                },
                "analysis": analysis,
                "review": review,
                "runtime": "langgraph",
            },
            source=self.source,
        )
        return {
            "final_answer": content_md,
            "visualization_code": final_code,
            "artifacts": {
                "visualize": {
                    "render_type": analysis["render_type"],
                    "code": final_code,
                    "analysis": analysis,
                    "review": review,
                    "runtime": "langgraph",
                }
            },
        }

    async def _run_answer_now(
        self,
        state: TutorState,
        payload: dict[str, Any],
    ) -> TutorState:
        stream = state["stream"]
        config = self._config(state)
        original, partial, trace_summary = answer_now_parts(state, payload)
        notice = skip_notice(
            capability=self.source,
            stages_skipped=["analyzing", "reviewing"],
        )

        async with stream.stage("generating", source=self.source):
            await stream.progress(
                "Generating final visualization code from the partial trace...",
                source=self.source,
                stage="generating",
                metadata=answer_now_progress_metadata("running"),
            )
            response = await self._ainvoke(
                system=(
                    "You are SparkWeave's visualization code generator. The user "
                    "is waiting, so emit final renderable code in one shot. "
                    "Return JSON only: {\"render_type\": \"svg|chartjs|mermaid\", "
                    "\"code\": \"...\"}."
                ),
                user=answer_now_user_prompt(
                    original=original,
                    original_label="User request",
                    partial=partial,
                    trace_summary=trace_summary,
                    extra_context=f"Render mode hint: {config['render_mode']}",
                    final_instruction="Emit the JSON object now.",
                ),
            )
            parsed = parse_answer_now_json(message_text(response))
            if not isinstance(parsed, dict):
                parsed = {"render_type": "svg", "code": str(parsed)}
            render_type = str(parsed.get("render_type") or "").strip().lower()
            if config["render_mode"] in {"svg", "chartjs", "mermaid"}:
                render_type = config["render_mode"]
            if render_type not in {"svg", "chartjs", "mermaid"}:
                render_type = self._infer_render_type(original)
            final_code = str(parsed.get("code") or "").strip()
            if not final_code:
                final_code = self._fallback_code(
                    {"render_type": render_type, "description": original},
                    original,
                )
            lang_tag = self._language_tag(render_type)
            content_md = f"```{lang_tag}\n{final_code}\n```"
            body = answer_now_body(content_md, notice=notice)
            await stream.content(body, source=self.source, stage="generating")
            await stream.progress(
                "",
                source=self.source,
                stage="generating",
                metadata=answer_now_progress_metadata("complete"),
            )

            analysis = {
                "render_type": render_type,
                "description": "Answer-now: skipped analysis stage.",
                "data_description": "",
                "chart_type": "",
                "visual_elements": [],
                "rationale": "",
            }
            review = {
                "optimized_code": final_code,
                "changed": False,
                "review_notes": "Answer-now: skipped review stage.",
            }
            await stream.result(
                {
                    "response": self._viewer_summary(analysis),
                    "render_type": render_type,
                    "code": {
                        "language": lang_tag,
                        "content": final_code,
                    },
                    "analysis": analysis,
                    "review": review,
                    "metadata": answer_now_metadata(),
                    "runtime": "langgraph",
                },
                source=self.source,
            )

        state["user_message"] = original
        state["visualization_analysis"] = analysis
        state["visualization_code"] = final_code
        state["visualization_review"] = review
        state["final_answer"] = body
        state["artifacts"] = {
            "visualize": {
                "render_type": render_type,
                "code": final_code,
                "analysis": analysis,
                "review": review,
                "runtime": "langgraph",
                "answer_now": True,
            }
        }
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

    @staticmethod
    def _config(state: TutorState) -> dict[str, Any]:
        context = state.get("context")
        overrides = dict(getattr(context, "config_overrides", {}) or {})
        render_mode = str(overrides.get("render_mode") or "auto").strip().lower()
        if render_mode not in {"auto", "svg", "chartjs", "mermaid"}:
            render_mode = "auto"
        return {"render_mode": render_mode}

    @staticmethod
    def _history_context(state: TutorState) -> str:
        context = state.get("context")
        if context is None:
            return ""
        return str(context.metadata.get("conversation_context_text", "") or "").strip()

    def _normalize_analysis(
        self,
        payload: dict[str, Any],
        state: TutorState,
        render_mode: str,
    ) -> dict[str, Any]:
        render_type = str(payload.get("render_type") or "").strip().lower()
        if render_mode in {"svg", "chartjs", "mermaid"}:
            render_type = render_mode
        if render_type not in {"svg", "chartjs", "mermaid"}:
            render_type = self._infer_render_type(state["user_message"])

        visual_elements = payload.get("visual_elements", [])
        if isinstance(visual_elements, str):
            visual_elements = [visual_elements]
        if not isinstance(visual_elements, list):
            visual_elements = []
        return {
            "render_type": render_type,
            "description": str(payload.get("description") or state["user_message"]).strip(),
            "data_description": str(payload.get("data_description") or "").strip(),
            "chart_type": str(payload.get("chart_type") or "").strip(),
            "visual_elements": [str(item).strip() for item in visual_elements if str(item).strip()],
            "rationale": str(payload.get("rationale") or "").strip(),
        }

    @staticmethod
    def _normalize_review(payload: dict[str, Any], code: str) -> dict[str, Any]:
        optimized = VisualizeGraph._strip_code_fence(str(payload.get("optimized_code") or "").strip()) or code
        changed = bool(payload.get("changed", False)) and optimized != code
        return {
            "optimized_code": optimized,
            "changed": changed,
            "review_notes": str(payload.get("review_notes") or "").strip(),
        }

    @staticmethod
    def _analysis(state: TutorState) -> dict[str, Any]:
        analysis = dict(state.get("visualization_analysis") or {})
        if analysis.get("render_type") not in {"svg", "chartjs", "mermaid"}:
            analysis["render_type"] = "svg"
        analysis.setdefault("description", "")
        analysis.setdefault("data_description", "")
        analysis.setdefault("chart_type", "")
        analysis.setdefault("visual_elements", [])
        analysis.setdefault("rationale", "")
        return analysis

    @staticmethod
    def _review(state: TutorState) -> dict[str, Any]:
        review = dict(state.get("visualization_review") or {})
        review.setdefault("optimized_code", state.get("visualization_code", ""))
        review.setdefault("changed", False)
        review.setdefault("review_notes", "")
        return review

    @staticmethod
    def _format_analysis(analysis: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"Render type: {analysis.get('render_type', '')}",
                f"Description: {analysis.get('description', '')}",
                f"Data: {analysis.get('data_description', '')}",
                f"Elements: {', '.join(analysis.get('visual_elements', []))}",
            ]
        ).strip()

    @staticmethod
    def _code_system_prompt(render_type: str) -> str:
        if render_type == "chartjs":
            return (
                "Generate a Chart.js configuration object expression only. "
                "Do not call new Chart, do not access DOM, and do not wrap in prose. "
                "A JavaScript object literal is acceptable."
            )
        if render_type == "mermaid":
            return (
                "Generate Mermaid DSL only. Do not wrap in prose. Use a diagram "
                "type supported by Mermaid such as flowchart, sequenceDiagram, "
                "classDiagram, stateDiagram, mindmap, or timeline."
            )
        return (
            "Generate complete raw SVG markup only. The SVG must start with <svg, "
            "include viewBox/width/height, and avoid scripts or external assets."
        )

    @staticmethod
    def _extract_code(raw: str, render_type: str) -> str:
        language = VisualizeGraph._language_tag(render_type)
        patterns = [
            rf"```{re.escape(language)}\s*\n([\s\S]*?)\n```",
            rf"```{re.escape(language)}\s+([\s\S]*?)\s*```",
            r"```[A-Za-z]*\s*\n([\s\S]*?)\n```",
            r"```[A-Za-z]*\s+([\s\S]*?)\s*```",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw or "", flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return VisualizeGraph._strip_code_fence(raw)

    @staticmethod
    def _strip_code_fence(raw: str) -> str:
        text = (raw or "").strip()
        match = re.fullmatch(r"```[A-Za-z0-9_-]*\s*([\s\S]*?)\s*```", text)
        return match.group(1).strip() if match else text

    @staticmethod
    def _viewer_summary(analysis: dict[str, Any]) -> str:
        description = str(analysis.get("description") or "").strip()
        render_type = str(analysis.get("render_type") or "visualization").strip()
        return description or f"Generated {render_type} visualization."

    @staticmethod
    def _language_tag(render_type: str) -> str:
        if render_type == "svg":
            return "svg"
        if render_type == "mermaid":
            return "mermaid"
        return "javascript"

    @staticmethod
    def _code_preview(code: str) -> str:
        if len(code) <= 1200:
            return code
        return code[:1200].rstrip() + "\n..."

    @staticmethod
    def _infer_render_type(user_message: str) -> RenderType:
        lowered = user_message.lower()
        if any(word in lowered for word in ("flowchart", "sequence", "mermaid", "mindmap")):
            return "mermaid"
        if any(word in lowered for word in ("chart", "bar", "line", "pie", "dataset", "trend")):
            return "chartjs"
        return "svg"

    @staticmethod
    def _fallback_code(analysis: dict[str, Any], user_message: str) -> str:
        render_type = analysis.get("render_type", "svg")
        title = (analysis.get("description") or user_message or "Visualization").strip()
        if render_type == "chartjs":
            return (
                "{\n"
                "  type: 'bar',\n"
                f"  data: {{ labels: ['A', 'B', 'C'], datasets: [{{ label: {json.dumps(title)}, data: [3, 5, 4] }}] }},\n"
                "  options: { responsive: true }\n"
                "}"
            )
        if render_type == "mermaid":
            return f"flowchart TD\n  A[{json.dumps(title)}] --> B[Key idea]"
        safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="360" '
            'viewBox="0 0 720 360">\n'
            '  <rect width="720" height="360" fill="#f8fafc"/>\n'
            f'  <text x="360" y="180" text-anchor="middle" font-size="28" fill="#111827">{safe_title}</text>\n'
            "</svg>"
        )

