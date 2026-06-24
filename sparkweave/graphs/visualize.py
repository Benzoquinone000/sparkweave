"""LangGraph implementation of SparkWeave's visualize capability."""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from xml.etree import ElementTree

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
viewer-ready result. Prefer correctness, direct renderability, and learning
clarity over ornament. Every visual should help a student understand a concept,
relationship, process, comparison, or data pattern at a glance.
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


class VisualizationRepairPayload(BaseModel):
    code: str
    repair_notes: str = ""


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
                    "sequence diagrams, state diagrams, mindmaps, and similar structures. "
                    "For concept relationship maps, learning maps, or diagrams that mention "
                    "a center with surrounding modules, prefer Mermaid flowchart over mindmap "
                    "unless the learner explicitly asks for a mindmap/思维导图/脑图. "
                    "Prefer the simplest format that makes the learning relation clear. "
                    "Identify the key labels and avoid decorative elements that do not teach."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Conversation context:\n{self._history_context(state) or '(none)'}\n\n"
                    f"Render mode hint: {config['render_mode']}\n\n"
                    f"Learner style hint: {config['style_hint'] or '(none)'}\n\n"
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
        config = self._config(state)
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
                    f"Learner style hint: {config['style_hint'] or '(none)'}\n\n"
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
        config = self._config(state)
        code = state.get("visualization_code", "")
        async with stream.stage("reviewing", source=self.source):
            await stream.progress(
                "Reviewing, validating, and optimizing code...",
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
            final_code = review["optimized_code"]
            validation = self._validate_visualization_code(
                analysis["render_type"],
                final_code,
                user_message=state["user_message"],
                analysis=analysis,
            )
            repair_history: list[dict[str, Any]] = []
            if not validation["passed"]:
                await stream.observation(
                    self._format_validation_failure(validation),
                    source=self.source,
                    stage="reviewing",
                    metadata={
                        "trace_kind": "validation",
                        "passed": False,
                        "errors": validation["errors"],
                    },
                )
                for attempt in range(config["max_repair_attempts"]):
                    await stream.progress(
                        f"Repairing visualization code from validation feedback ({attempt + 1}/{config['max_repair_attempts']})...",
                        source=self.source,
                        stage="reviewing",
                        metadata={
                            "trace_kind": "call_status",
                            "call_state": "running",
                            "repair_attempt": attempt + 1,
                        },
                    )
                    repair_payload = await self._ainvoke_json(
                        system=self._repair_system_prompt(analysis["render_type"]),
                        user=(
                            f"User request:\n{state['user_message']}\n\n"
                            f"Render type: {analysis['render_type']}\n"
                            f"Analysis:\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n\n"
                            f"Current code:\n{final_code}\n\n"
                            f"Validation errors:\n{self._format_validation_errors(validation)}\n\n"
                            "Return JSON with keys: code, repair_notes."
                        ),
                        schema=VisualizationRepairPayload,
                    )
                    repaired_code = self._extract_code(
                        str(repair_payload.get("code") or ""),
                        analysis["render_type"],
                    )
                    if not repaired_code:
                        repaired_code = final_code
                    repaired_validation = self._validate_visualization_code(
                        analysis["render_type"],
                        repaired_code,
                        user_message=state["user_message"],
                        analysis=analysis,
                    )
                    repair_notes = str(repair_payload.get("repair_notes") or "").strip()
                    repair_history.append(
                        {
                            "attempt": attempt + 1,
                            "passed": repaired_validation["passed"],
                            "errors": repaired_validation["errors"],
                            "repair_notes": repair_notes,
                        }
                    )
                    await stream.observation(
                        repair_notes
                        or (
                            "Repair passed validation."
                            if repaired_validation["passed"]
                            else self._format_validation_failure(repaired_validation)
                        ),
                        source=self.source,
                        stage="reviewing",
                        metadata={
                            "trace_kind": "repair",
                            "repair_attempt": attempt + 1,
                            "passed": repaired_validation["passed"],
                            "errors": repaired_validation["errors"],
                        },
                    )
                    final_code = repaired_code
                    validation = repaired_validation
                    if validation["passed"]:
                        break

            review["optimized_code"] = final_code
            review["changed"] = final_code != code or bool(review.get("changed"))
            review["validation"] = validation
            review["repair_attempts"] = len(repair_history)
            review["repair_history"] = repair_history
            if review["changed"]:
                message = f"Code optimized: {review['review_notes'] or 'validation feedback applied.'}"
            elif validation["passed"]:
                message = "Code looks good - validation passed."
            else:
                message = "Code kept, but validation still reports issues."
            await stream.observation(
                review["review_notes"] or message,
                source=self.source,
                stage="reviewing",
                metadata={
                    "trace_kind": "review",
                    "validation_passed": validation["passed"],
                    "repair_attempts": len(repair_history),
                },
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
        config = self._config(state)
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
                "validation": review.get("validation"),
                "style_hint": config["style_hint"],
                "learner_profile_hints": config["learner_profile_hints"],
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
                    "validation": review.get("validation"),
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
                    extra_context=(
                        f"Render mode hint: {config['render_mode']}\n"
                        f"Learner style hint: {config['style_hint'] or '(none)'}"
                    ),
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
                    "style_hint": config["style_hint"],
                    "learner_profile_hints": config["learner_profile_hints"],
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
        return {
            "render_mode": render_mode,
            "style_hint": str(overrides.get("style_hint") or "").strip()[:500],
            "learner_profile_hints": VisualizeGraph._profile_hints(overrides.get("learner_profile_hints")),
            "max_repair_attempts": VisualizeGraph._clamp_int(
                overrides.get("max_repair_attempts"),
                default=2,
                minimum=0,
                maximum=3,
            ),
        }

    @staticmethod
    def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))

    @staticmethod
    def _profile_hints(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        allowed = {
            "current_focus",
            "summary",
            "level",
            "time_budget_minutes",
            "goals",
            "preferences",
            "strengths",
            "weak_points",
            "mastery_needs_attention",
            "concepts",
            "next_action",
        }
        return {key: value[key] for key in allowed if key in value}

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
    def _validate_visualization_code(
        render_type: str,
        code: str,
        *,
        user_message: str = "",
        analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned = VisualizeGraph._strip_code_fence(code)
        errors: list[str] = []
        warnings: list[str] = []

        if not cleaned:
            errors.append("Generated code is empty.")
        elif render_type == "svg":
            errors.extend(VisualizeGraph._validate_svg(cleaned))
        elif render_type == "chartjs":
            errors.extend(VisualizeGraph._validate_chartjs(cleaned))
        elif render_type == "mermaid":
            errors.extend(VisualizeGraph._validate_mermaid(cleaned))
            errors.extend(
                VisualizeGraph._validate_mermaid_learning_fit(
                    cleaned,
                    user_message=user_message,
                    analysis=analysis or {},
                )
            )
        else:
            errors.append(f"Unsupported render type: {render_type}.")

        return {
            "passed": not errors,
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _validate_svg(code: str) -> list[str]:
        errors: list[str] = []
        if not re.match(r"^\s*<svg(?:\s|>)", code, flags=re.IGNORECASE):
            errors.append("SVG must start with a root <svg> element.")
            return errors
        try:
            root = ElementTree.fromstring(code)
        except ElementTree.ParseError as exc:
            return [f"SVG XML parse error: {exc}"]

        if not VisualizeGraph._local_xml_name(root.tag).lower() == "svg":
            errors.append("SVG root element must be <svg>.")
        if not (root.get("viewBox") or (root.get("width") and root.get("height"))):
            errors.append("SVG should include viewBox or width/height so the viewer can size it.")

        for element in root.iter():
            tag = VisualizeGraph._local_xml_name(element.tag).lower()
            if tag in {"script", "foreignobject"}:
                errors.append(f"SVG must not contain <{tag}> elements.")
            for attr, value in element.attrib.items():
                attr_name = VisualizeGraph._local_xml_name(attr).lower()
                attr_value = str(value or "").strip().lower()
                if attr_name.startswith("on"):
                    errors.append(f"SVG must not contain event handler attribute '{attr_name}'.")
                if attr_name in {"href", "xlink:href"} and attr_value.startswith("javascript:"):
                    errors.append("SVG links must not use javascript: URLs.")
        return errors

    @staticmethod
    def _validate_chartjs(code: str) -> list[str]:
        errors: list[str] = []
        try:
            parsed = json.loads(code)
        except json.JSONDecodeError as exc:
            return [
                "Chart.js code must be strict JSON because the frontend parses it with JSON.parse. "
                f"JSON parse error: {exc.msg} at line {exc.lineno} column {exc.colno}."
            ]

        if isinstance(parsed, dict) and isinstance(parsed.get("config"), dict):
            config = parsed["config"]
        elif isinstance(parsed, dict) and isinstance(parsed.get("chart"), dict):
            config = parsed["chart"]
        else:
            config = parsed
        if not isinstance(config, dict):
            return ["Chart.js code must parse to a JSON object."]
        if not isinstance(config.get("type"), str) or not config.get("type"):
            errors.append("Chart.js config is missing a string 'type' field.")
        data = config.get("data")
        if not isinstance(data, dict):
            errors.append("Chart.js config is missing an object 'data' field.")
        else:
            labels = data.get("labels")
            datasets = data.get("datasets")
            if labels is not None and not isinstance(labels, list):
                errors.append("Chart.js data.labels must be an array when provided.")
            if not isinstance(datasets, list) or not datasets:
                errors.append("Chart.js data.datasets must be a non-empty array.")
        return errors

    @staticmethod
    def _validate_mermaid(code: str) -> list[str]:
        text = code.strip()
        if not text:
            return ["Mermaid code is empty."]
        if "<script" in text.lower() or "<svg" in text.lower():
            return ["Mermaid code must be plain Mermaid DSL, not HTML or SVG."]

        first_line = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("%%"):
                first_line = stripped
                break
        if not first_line:
            return ["Mermaid code has no diagram declaration."]

        supported = (
            "graph ",
            "graph\t",
            "flowchart ",
            "flowchart\t",
            "sequenceDiagram",
            "classDiagram",
            "stateDiagram",
            "stateDiagram-v2",
            "erDiagram",
            "journey",
            "gantt",
            "pie",
            "mindmap",
            "timeline",
            "gitGraph",
            "quadrantChart",
            "requirementDiagram",
        )
        if not first_line.startswith(supported):
            return [f"Mermaid diagram must start with a supported declaration, got: {first_line[:80]}"]
        return []

    @staticmethod
    def _validate_mermaid_learning_fit(
        code: str,
        *,
        user_message: str,
        analysis: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        text = code.strip()
        if not text:
            return errors

        if (
            VisualizeGraph._looks_like_relation_map_request(user_message, analysis)
            and text.startswith("mindmap")
        ):
            errors.append(
                "The learner asked for a concept relationship diagram, so Mermaid should use "
                "a flowchart with a visible center, module nodes, and relationship links. "
                "Mindmap is too hierarchical for this request unless explicitly requested."
            )

        if VisualizeGraph._asks_for_reading_guide(user_message, analysis) and "读图" not in text:
            errors.append("The learner asked for a one-sentence reading guide, but the diagram does not include one.")

        if VisualizeGraph._asks_for_three_learning_blocks(user_message, analysis):
            missing = [
                label
                for label in ("核心概念", "关键步骤", "常见混淆")
                if label not in text
            ]
            if missing:
                errors.append("The diagram is missing required learning blocks: " + ", ".join(missing) + ".")
        return errors

    @staticmethod
    def _looks_like_relation_map_request(user_message: str, analysis: dict[str, Any]) -> bool:
        haystack = VisualizeGraph._request_haystack(user_message, analysis)
        if re.search(r"\b(mindmap|mind map)\b|思维导图|脑图", user_message, flags=re.IGNORECASE):
            return False
        return bool(
            re.search(
                r"关系图|概念关系|学习图解|中心|辐射|模块|concept map|relationship map|learning map",
                haystack,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _asks_for_reading_guide(user_message: str, analysis: dict[str, Any]) -> bool:
        haystack = VisualizeGraph._request_haystack(user_message, analysis)
        return bool(re.search(r"读图|怎么看|怎么读|reading guide|how to read", haystack, flags=re.IGNORECASE))

    @staticmethod
    def _asks_for_three_learning_blocks(user_message: str, analysis: dict[str, Any]) -> bool:
        haystack = VisualizeGraph._request_haystack(user_message, analysis)
        return bool(
            ("核心概念" in haystack and "关键步骤" in haystack and "常见混淆" in haystack)
            or re.search(r"三大模块|three (blocks|modules)", haystack, flags=re.IGNORECASE)
        )

    @staticmethod
    def _request_haystack(user_message: str, analysis: dict[str, Any]) -> str:
        parts = [
            user_message,
            str(analysis.get("description") or ""),
            str(analysis.get("data_description") or ""),
            str(analysis.get("chart_type") or ""),
            str(analysis.get("rationale") or ""),
            " ".join(str(item) for item in (analysis.get("visual_elements") or [])),
        ]
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _local_xml_name(name: Any) -> str:
        text = str(name or "")
        if "}" in text:
            return text.rsplit("}", 1)[-1]
        return text

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
                "Generate a strict JSON Chart.js configuration object only. "
                "Do not call new Chart, do not access DOM, do not use comments, "
                "and do not use JavaScript object-literal syntax with single quotes. "
                "The frontend parses this with JSON.parse. Use clear labels, readable "
                "colors, and concise dataset names that explain the learning point."
            )
        if render_type == "mermaid":
            return (
                "Generate Mermaid DSL only. Do not wrap in prose. Use a diagram "
                "type supported by Mermaid such as flowchart, sequenceDiagram, "
                "classDiagram, stateDiagram, mindmap, or timeline. For learning "
                "concept relationship diagrams, prefer flowchart TD/LR with a clear "
                "center node, 3-5 module nodes, short subnodes, and a few explicit "
                "relationship arrows; use subgraph blocks when they improve scanning. "
                "Use mindmap only when the learner explicitly asks for a mindmap/思维导图/脑图. "
                "Keep node text short and user-facing; avoid implementation jargon unless requested."
            )
        return (
            "Generate complete raw SVG markup only. The SVG must start with <svg, "
            "include viewBox/width/height, and avoid scripts or external assets. "
            "Use a clean educational layout with stable spacing, readable labels, "
            "high contrast, and no decorative clutter."
        )

    @staticmethod
    def _repair_system_prompt(render_type: str) -> str:
        base = (
            "You repair visualization code from concrete validation errors. "
            "Return JSON only with keys code and repair_notes. Preserve the teaching "
            "intent, but prioritize code the frontend can render."
        )
        if render_type == "chartjs":
            return (
                base
                + " The code field must be strict JSON for a Chart.js configuration; "
                "use double quotes and no functions, comments, trailing commas, or DOM access."
            )
        if render_type == "mermaid":
            return (
                base
                + " The code field must be plain Mermaid DSL only. If validation says the "
                "learner asked for a concept relationship diagram, rewrite mindmap output "
                "as a flowchart with a center node, module nodes, subnodes, and relationship links."
            )
        return (
            base
            + " The code field must be complete safe raw SVG that starts with <svg, "
            "has viewBox or width/height, and contains no scripts or event handlers."
        )

    @staticmethod
    def _format_validation_errors(validation: dict[str, Any]) -> str:
        errors = validation.get("errors")
        if not isinstance(errors, list) or not errors:
            return "- Unknown validation error."
        return "\n".join(f"- {error}" for error in errors)

    @staticmethod
    def _format_validation_failure(validation: dict[str, Any]) -> str:
        return "Validation failed:\n" + VisualizeGraph._format_validation_errors(validation)

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
            return json.dumps(
                {
                    "type": "bar",
                    "data": {
                        "labels": ["A", "B", "C"],
                        "datasets": [{"label": title, "data": [3, 5, 4]}],
                    },
                    "options": {"responsive": True},
                },
                ensure_ascii=False,
                indent=2,
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

