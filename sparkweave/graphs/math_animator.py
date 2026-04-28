"""LangGraph implementation of SparkWeave's math-animator capability."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from pydantic import BaseModel, Field

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.core.dependencies import dependency_error
from sparkweave.core.json import parse_json_response
from sparkweave.core.state import TutorState, context_to_state, message_text
from sparkweave.graphs._answer_now import (
    answer_now_parts,
    extract_answer_now_payload,
    skip_notice,
)
from sparkweave.llm import ainvoke_json as llm_ainvoke_json
from sparkweave.llm import ainvoke_json_with_attachments as llm_ainvoke_json_with_attachments
from sparkweave.llm import chat_messages, create_chat_model
from sparkweave.services import math_animator as math_services

MATH_ANIMATOR_SYSTEM_PROMPT = """\
You are SparkWeave's math animation graph. Build concise educational Manim
scripts that explain mathematical ideas visually. Prefer Text, DecimalNumber,
NumberPlane, axes, labels, and simple shapes over LaTeX-only constructs so the
code remains renderable in lightweight environments.
"""


def _resolve_manim_python() -> str | None:
    """Return the configured or current Python executable when Manim is available."""

    override = os.environ.get("SPARKWEAVE_MANIM_PYTHON", "").strip().strip('"')
    if override:
        override_path = Path(override)
        return str(override_path) if _python_can_import_manim(override_path) else None

    if importlib.util.find_spec("manim") is not None:
        return sys.executable

    return None


def _python_can_import_manim(python_path: Path) -> bool:
    if not python_path.exists():
        return False
    try:
        completed = subprocess.run(
            [str(python_path), "-c", "import manim"],
            check=False,
            capture_output=True,
            text=True,
            timeout=12,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


class MathAnalysisPayload(BaseModel):
    learning_goal: str = ""
    math_focus: list[str] = Field(default_factory=list)
    visual_targets: list[str] = Field(default_factory=list)
    narrative_steps: list[str] = Field(default_factory=list)
    reference_usage: str = ""
    output_intent: str = ""


class MathDesignPayload(BaseModel):
    title: str = ""
    scene_outline: list[str] = Field(default_factory=list)
    visual_style: str = ""
    animation_notes: list[str] = Field(default_factory=list)
    image_plan: list[str] = Field(default_factory=list)
    code_constraints: list[str] = Field(default_factory=list)


class MathSummaryPayload(BaseModel):
    summary_text: str = ""
    user_request: str = ""
    generated_output: str = ""
    key_points: list[str] = Field(default_factory=list)


class DefaultMathRenderer:
    """Render generated Manim code when optional Manim dependencies exist."""

    async def render(
        self,
        *,
        turn_id: str,
        code: str,
        output_mode: str,
        quality: str,
        stream: StreamBus,
        source: str,
        repair_callback: Callable[[str, str, int], Awaitable[Any]] | None = None,
        review_callback: Callable[[str, Any], Awaitable[Any]] | None = None,
        max_retries: int = 4,
    ) -> tuple[str, dict[str, Any]]:
        manim_python = _resolve_manim_python()
        if manim_python is None:
            await stream.progress(
                (
                    "Manim is not available in the backend runtime; returning generated "
                    "code without rendered artifacts."
                ),
                source=source,
                stage="code_retry",
                metadata={"trace_kind": "warning", "reason": "manim_not_installed"},
            )
            return code, {
                "output_mode": output_mode,
                "artifacts": [],
                "public_code_path": "",
                "source_code_path": "",
                "quality": quality,
                "retry_attempts": 0,
                "retry_history": [],
                "visual_review": None,
                "render_skipped": True,
                "skip_reason": "manim_not_installed",
            }

        if Path(manim_python).resolve() != Path(sys.executable).resolve():
            await stream.progress(
                f"Using external Manim Python: {manim_python}",
                source=source,
                stage="code_retry",
                metadata={"trace_kind": "call_status", "python_executable": manim_python},
            )

        ManimRenderError, ManimRenderService, CodeRetryManager = (
            math_services.load_rendering_components()
        )

        async def _progress(message: str, raw: bool) -> None:
            await stream.progress(
                message=message,
                source=source,
                stage="render_output" if raw else "code_retry",
                metadata={"trace_layer": "raw" if raw else "summary"},
            )

        renderer_kwargs: dict[str, Any] = {
            "turn_id": turn_id,
            "progress_callback": _progress,
        }
        if Path(manim_python).resolve() != Path(sys.executable).resolve():
            renderer_kwargs["python_executable"] = manim_python
        renderer = ManimRenderService(**renderer_kwargs)
        retry_history: list[dict[str, Any]] = []

        async def _on_retry(retry_attempt: Any) -> None:
            item = (
                retry_attempt.model_dump()
                if isinstance(retry_attempt, BaseModel)
                else {
                    "attempt": int(getattr(retry_attempt, "attempt", len(retry_history) + 1)),
                    "error": str(getattr(retry_attempt, "error", "")),
                }
            )
            retry_history.append(item)
            await stream.progress(
                f"Retry {item.get('attempt')}: {item.get('error')}",
                source=source,
                stage="code_retry",
                metadata={"trace_layer": "raw", "attempt": item.get("attempt")},
            )

        async def _on_status(message: str) -> None:
            await stream.progress(
                message,
                source=source,
                stage="code_retry",
                metadata={"trace_layer": "summary"},
            )

        try:
            if repair_callback is None:
                result = await renderer.render(
                    code=code,
                    output_mode=output_mode,
                    quality=quality,
                )
                return code, result.model_dump()

            retry_manager = CodeRetryManager(
                renderer=renderer,
                repair_callback=repair_callback,
                review_callback=review_callback,
                on_retry=_on_retry,
                on_status=_on_status,
                max_retries=max_retries,
            )
            final_code, result = await retry_manager.render_with_retries(
                initial_code=code,
                output_mode=output_mode,
                quality=quality,
            )
            return final_code, result.model_dump()
        except ManimRenderError as exc:
            await stream.error(str(exc), source=source, stage="code_retry")
            return code, {
                "output_mode": output_mode,
                "artifacts": [],
                "public_code_path": "",
                "source_code_path": "",
                "quality": quality,
                "retry_attempts": len(retry_history),
                "retry_history": retry_history or [{"attempt": 1, "error": str(exc)}],
                "visual_review": {
                    "passed": False,
                    "summary": "Render failed after retry attempts; returning generated code only.",
                    "issues": [str(exc)],
                    "suggested_fix": "",
                    "reviewed_frames": 0,
                },
                "render_skipped": True,
                "skip_reason": "render_failed",
            }


class MathAnimatorGraph:
    """Explicit graph for math animation planning, code, render, and summary."""

    source = "math_animator"

    def __init__(self, *, model: Any | None = None, renderer: Any | None = None) -> None:
        self.model = model
        self.renderer = renderer or DefaultMathRenderer()
        self._compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        state = context_to_state(
            context,
            stream=stream,
            system_prompt=MATH_ANIMATOR_SYSTEM_PROMPT,
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
        builder.add_node("design", self._design_node)
        builder.add_node("generate_code", self._generate_code_node)
        builder.add_node("render", self._render_node)
        builder.add_node("summarize", self._summarize_node)
        builder.add_node("write", self._write_node)

        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "design")
        builder.add_edge("design", "generate_code")
        builder.add_edge("generate_code", "render")
        builder.add_edge("render", "summarize")
        builder.add_edge("summarize", "write")
        builder.add_edge("write", END)
        self._compiled = builder.compile()
        return self._compiled

    async def _analyze_node(self, state: TutorState) -> dict[str, Any]:
        started = time.perf_counter()
        stream = state["stream"]
        config = self._config(state)
        async with stream.stage("concept_analysis", source=self.source):
            await stream.progress(
                "Analyzing the mathematical learning goal...",
                source=self.source,
                stage="concept_analysis",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            payload = await self._ainvoke_json(
                system=(
                    "Analyze the math animation request. Return JSON only. "
                    "Focus on the learning goal, mathematical concepts, visual "
                    "targets, and narrative steps."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Output mode: {config['output_mode']}\n"
                    f"Style hint: {config['style_hint'] or '(none)'}\n"
                    f"Conversation context:\n{self._history_context(state) or '(none)'}\n\n"
                    "Return JSON with keys: learning_goal, math_focus, "
                    "visual_targets, narrative_steps, reference_usage, output_intent."
                ),
                schema=MathAnalysisPayload,
            )
            analysis = self._normalize_analysis(payload, state, config)
            await stream.thinking(
                self._format_list_payload(analysis),
                source=self.source,
                stage="concept_analysis",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="concept_analysis",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {
            "math_analysis": analysis,
            "timings": self._with_timing(state, "concept_analysis", started),
        }

    async def _design_node(self, state: TutorState) -> dict[str, Any]:
        started = time.perf_counter()
        stream = state["stream"]
        config = self._config(state)
        async with stream.stage("concept_design", source=self.source):
            await stream.progress(
                "Designing the animation storyboard...",
                source=self.source,
                stage="concept_design",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            payload = await self._ainvoke_json(
                system=(
                    "Design a compact Manim storyboard from the concept analysis. "
                    "Return JSON only. Include scene outline, style, notes, and "
                    "constraints that help code render reliably."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Output mode: {config['output_mode']}\n"
                    f"Style hint: {config['style_hint'] or '(none)'}\n"
                    f"Analysis:\n{json.dumps(state.get('math_analysis', {}), ensure_ascii=False, indent=2)}\n\n"
                    "Return JSON with keys: title, scene_outline, visual_style, "
                    "animation_notes, image_plan, code_constraints."
                ),
                schema=MathDesignPayload,
            )
            design = self._normalize_design(payload, state, config)
            await stream.thinking(
                self._format_list_payload(design),
                source=self.source,
                stage="concept_design",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="concept_design",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {
            "math_design": design,
            "timings": self._with_timing(state, "concept_design", started),
        }

    async def _generate_code_node(self, state: TutorState) -> dict[str, Any]:
        started = time.perf_counter()
        stream = state["stream"]
        config = self._config(state)
        async with stream.stage("code_generation", source=self.source):
            await stream.progress(
                "Generating Manim code...",
                source=self.source,
                stage="code_generation",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            response = await self._ainvoke(
                system=self._code_system_prompt(config["output_mode"]),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Output mode: {config['output_mode']}\n"
                    f"Quality: {config['quality']}\n"
                    f"Style hint: {config['style_hint'] or '(none)'}\n\n"
                    f"Concept analysis:\n{json.dumps(state.get('math_analysis', {}), ensure_ascii=False, indent=2)}\n\n"
                    f"Storyboard:\n{json.dumps(state.get('math_design', {}), ensure_ascii=False, indent=2)}\n\n"
                    'Return JSON: {"code": "...", "rationale": "..."}'
                ),
            )
            raw = message_text(response)
            code = self._extract_generated_code(raw)
            if not code:
                code = self._fallback_code(state, config)
            await stream.thinking(
                self._code_preview(code),
                source=self.source,
                stage="code_generation",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "Manim code prepared.",
                source=self.source,
                stage="code_generation",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {
            "math_code": code,
            "timings": self._with_timing(state, "code_generation", started),
        }

    async def _render_node(self, state: TutorState) -> dict[str, Any]:
        started = time.perf_counter()
        stream = state["stream"]
        config = self._config(state)
        turn_id = str(state.get("turn_id") or state.get("session_id") or "math-animator")
        code = state.get("math_code", "") or self._fallback_code(state, config)

        async with stream.stage("code_retry", source=self.source):
            await stream.progress(
                f"Rendering {config['output_mode']} with quality={config['quality']}.",
                source=self.source,
                stage="code_retry",
                metadata={
                    "trace_kind": "call_status",
                    "call_state": "running",
                    "output_mode": config["output_mode"],
                    "quality": config["quality"],
                },
            )
            final_code, render_result = await self._call_renderer(
                turn_id=turn_id,
                code=code,
                output_mode=config["output_mode"],
                quality=config["quality"],
                stream=stream,
                source=self.source,
                repair_callback=self._make_repair_callback(state, config),
                review_callback=self._make_visual_review_callback(state, config),
                max_retries=config["max_retries"],
            )
            await stream.progress(
                "",
                source=self.source,
                stage="code_retry",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {
            "math_code": final_code or code,
            "math_render": self._normalize_render_result(render_result, config),
            "timings": self._with_timing(state, "code_retry", started),
        }

    async def _call_renderer(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        """Call custom renderers without requiring them to accept new hooks."""
        render = self.renderer.render
        try:
            signature = inspect.signature(render)
        except (TypeError, ValueError):
            return await render(**kwargs)

        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        if not accepts_kwargs:
            kwargs = {
                key: value
                for key, value in kwargs.items()
                if key in signature.parameters
            }
        return await render(**kwargs)

    def _make_repair_callback(
        self,
        state: TutorState,
        config: dict[str, Any],
    ) -> Callable[[str, str, int], Awaitable[Any]]:
        async def _repair(current_code: str, error_message: str, attempt: int) -> Any:
            GeneratedCode = math_services.load_generated_code_model()

            stream = state["stream"]
            await stream.progress(
                f"Generating repaired code for retry #{attempt}.",
                source=self.source,
                stage="code_retry",
                metadata={
                    "trace_kind": "call_status",
                    "call_state": "running",
                    "trace_role": "repair",
                    "attempt": attempt,
                },
            )
            payload = await self._ainvoke_json(
                system=(
                    "Repair generated Manim code after a render failure. "
                    "Return JSON only with keys: code, rationale. Preserve the "
                    "requested output mode and remove the cause of the failure. "
                    "If the failure mentions LaTeX, latex, dvi, preview.sty, "
                    "Tex, or MathTex, repair the TeX expression when possible; "
                    "only replace it with Text and Unicode formulas when the "
                    "LaTeX dependency itself is unavailable."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Output mode: {config['output_mode']}\n"
                    f"Quality: {config['quality']}\n"
                    f"Retry attempt: {attempt}\n\n"
                    f"Render or review error:\n{error_message}\n\n"
                    f"Current code:\n```python\n{current_code}\n```\n\n"
                    "Return JSON: {\"code\": \"...\", \"rationale\": \"...\"}"
                ),
                schema=GeneratedCode,
            )
            repaired = GeneratedCode.model_validate(payload)
            code = repaired.code.strip()
            if code:
                await stream.thinking(
                    self._code_preview(code),
                    source=self.source,
                    stage="code_retry",
                    metadata={
                        "trace_kind": "llm_output",
                        "trace_role": "repair",
                        "attempt": attempt,
                    },
                )
            await stream.progress(
                f"Retry #{attempt} code generated.",
                source=self.source,
                stage="code_retry",
                metadata={
                    "trace_kind": "call_status",
                    "call_state": "complete",
                    "trace_role": "repair",
                    "attempt": attempt,
                },
            )
            return repaired

        return _repair

    def _make_visual_review_callback(
        self,
        state: TutorState,
        config: dict[str, Any],
    ) -> Callable[[str, Any], Awaitable[Any]] | None:
        if not config["enable_visual_review"]:
            return None

        async def _review(current_code: str, render_result: Any) -> Any:
            RenderResult, VisualReviewResult, VisualReviewService = (
                math_services.load_visual_review_components()
            )

            stream = state["stream"]
            render_payload = (
                render_result.model_dump()
                if isinstance(render_result, BaseModel)
                else dict(render_result)
                if isinstance(render_result, dict)
                else {}
            )
            artifacts = render_payload.get("artifacts", [])
            if not artifacts:
                return VisualReviewResult(
                    passed=True,
                    summary="Visual review skipped because no rendered artifacts were available.",
                    reviewed_frames=0,
                )
            render_model = (
                render_result
                if isinstance(render_result, RenderResult)
                else RenderResult.model_validate(render_payload)
            )
            turn_id = str(state.get("turn_id") or state.get("session_id") or "math-animator")
            review_service = VisualReviewService(
                turn_id,
                progress_callback=lambda message, raw=False: stream.progress(
                    message,
                    source=self.source,
                    stage="render_output" if raw else "code_retry",
                    metadata={
                        "trace_layer": "raw" if raw else "summary",
                        "trace_role": "review",
                    },
                ),
            )
            attachments = await review_service.build_attachments(render_model)
            if not attachments:
                return VisualReviewResult(
                    passed=True,
                    summary="Visual review skipped because no review frames were available.",
                    reviewed_frames=0,
                )
            await stream.progress(
                f"Reviewing {len(attachments)} rendered frame(s) for readability and framing.",
                source=self.source,
                stage="render_output",
                metadata={
                    "trace_kind": "call_status",
                    "call_state": "running",
                    "trace_role": "review",
                    "reviewed_frames": len(attachments),
                },
            )
            payload = await self._ainvoke_json_with_attachments(
                system=(
                    "Review the attached rendered Manim frames together with the "
                    "render metadata and generated code. "
                    "Return JSON only with keys: passed, summary, issues, "
                    "suggested_fix, reviewed_frames. Mark passed=false only when "
                    "the frames show overlap, cropping, missing labels, unreadable "
                    "text, or poor pacing."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Output mode: {config['output_mode']}\n"
                    f"Number of sampled review frames: {len(attachments)}\n"
                    f"Frame filenames: {', '.join(item.filename for item in attachments)}\n\n"
                    f"Render result:\n{json.dumps(render_payload, ensure_ascii=False, indent=2)}\n\n"
                    f"Generated code:\n```python\n{current_code}\n```\n\n"
                    "Return JSON: {\"passed\": true, \"summary\": \"...\", "
                    f"\"issues\": [], \"suggested_fix\": \"\", \"reviewed_frames\": {len(attachments)}}}"
                ),
                attachments=attachments,
                schema=VisualReviewResult,
            )
            payload.setdefault("reviewed_frames", len(attachments))
            review = VisualReviewResult.model_validate(payload)
            await stream.progress(
                review.summary or "Visual review complete.",
                source=self.source,
                stage="render_output",
                metadata={
                    "trace_kind": "call_status",
                    "call_state": "complete",
                    "trace_role": "review",
                    "passed": review.passed,
                    "reviewed_frames": review.reviewed_frames,
                },
            )
            return review

        return _review

    async def _summarize_node(self, state: TutorState) -> dict[str, Any]:
        started = time.perf_counter()
        stream = state["stream"]
        config = self._config(state)
        render_result = state.get("math_render", {})
        async with stream.stage("summary", source=self.source):
            await stream.progress(
                "Summarizing the generated animation...",
                source=self.source,
                stage="summary",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            payload = await self._ainvoke_json(
                system=(
                    "Write a concise user-facing summary of the generated math "
                    "animation or storyboard. Return JSON only."
                ),
                user=(
                    f"User request:\n{state['user_message']}\n\n"
                    f"Output mode: {config['output_mode']}\n"
                    f"Analysis:\n{json.dumps(state.get('math_analysis', {}), ensure_ascii=False, indent=2)}\n\n"
                    f"Design:\n{json.dumps(state.get('math_design', {}), ensure_ascii=False, indent=2)}\n\n"
                    f"Render result:\n{json.dumps(render_result, ensure_ascii=False, indent=2)}\n\n"
                    "Return JSON with keys: summary_text, user_request, generated_output, key_points."
                ),
                schema=MathSummaryPayload,
            )
            summary = self._normalize_summary(payload, state, config)
            if summary["summary_text"]:
                await stream.content(
                    summary["summary_text"],
                    source=self.source,
                    stage="summary",
                )
            await stream.progress(
                "",
                source=self.source,
                stage="summary",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {
            "math_summary": summary,
            "timings": self._with_timing(state, "summary", started),
        }

    async def _write_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        render_result = self._render(state)
        summary = self._summary(state)
        timings = dict(state.get("timings") or {})

        async with stream.stage("render_output", source=self.source):
            artifacts = render_result.get("artifacts", [])
            await stream.progress(
                f"Prepared {len(artifacts)} {'artifact' if len(artifacts) == 1 else 'artifacts'}.",
                source=self.source,
                stage="render_output",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        timings["render_output"] = 0.0

        result = {
            "response": summary["summary_text"],
            "summary": summary,
            "code": {"language": "python", "content": state.get("math_code", "")},
            "output_mode": render_result["output_mode"],
            "artifacts": render_result["artifacts"],
            "timings": timings,
            "render": {
                "quality": render_result["quality"],
                "retry_attempts": render_result["retry_attempts"],
                "retry_history": render_result["retry_history"],
                "source_code_path": render_result["source_code_path"],
                "visual_review": render_result["visual_review"],
                "render_skipped": render_result.get("render_skipped", False),
                "skip_reason": render_result.get("skip_reason", ""),
            },
            "analysis": state.get("math_analysis", {}),
            "design": state.get("math_design", {}),
            "runtime": "langgraph",
        }
        if summary.get("answer_now"):
            result["metadata"] = {"answer_now": True}
        await stream.result(result, source=self.source)
        return {
            "final_answer": summary["summary_text"],
            "math_render": render_result,
            "timings": timings,
            "artifacts": {"math_animator": result},
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
            stages_skipped=["concept_analysis", "concept_design", "summary"],
        )
        state["user_message"] = original
        state["math_analysis"] = {
            "learning_goal": original,
            "math_focus": [],
            "visual_targets": [],
            "narrative_steps": [partial] if partial else [],
            "reference_usage": trace_summary,
            "output_intent": config["output_mode"],
            "answer_now": True,
        }
        state["math_design"] = {
            "title": original[:80] or "Math animation",
            "scene_outline": [],
            "visual_style": config["style_hint"],
            "animation_notes": [trace_summary[:600]] if trace_summary else [],
            "image_plan": [],
            "code_constraints": ["Answer-now: generate directly from partial trace."],
            "answer_now": True,
        }

        code_update = await self._generate_code_node(state)
        state.update(code_update)
        render_update = await self._render_node(state)
        state.update(render_update)

        summary_text = notice or "Answer-now: generated and rendered without prior analysis/design."
        async with stream.stage("summary", source=self.source):
            await stream.content(summary_text, source=self.source, stage="summary")
        state["math_summary"] = {
            "summary_text": summary_text,
            "user_request": original,
            "generated_output": self._render(state)["output_mode"],
            "key_points": [],
            "answer_now": True,
        }
        write_update = await self._write_node(state)
        state.update(write_update)
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

    async def _ainvoke_json_with_attachments(
        self,
        *,
        system: str,
        user: str,
        attachments: list[Any],
        schema: type[BaseModel] | None = None,
    ) -> dict[str, Any]:
        return await llm_ainvoke_json_with_attachments(
            self._get_model(),
            system=system,
            user=user,
            attachments=attachments,
            schema=schema,
        )

    def _get_model(self) -> Any:
        if self.model is not None:
            return self.model
        self.model = create_chat_model(temperature=0.3)
        return self.model

    @staticmethod
    def _config(state: TutorState) -> dict[str, Any]:
        context = state.get("context")
        overrides = dict(getattr(context, "config_overrides", {}) or {})
        output_mode = str(overrides.get("output_mode") or "video").strip().lower()
        quality = str(overrides.get("quality") or "medium").strip().lower()
        if output_mode not in {"video", "image"}:
            output_mode = "video"
        if quality not in {"low", "medium", "high"}:
            quality = "medium"
        try:
            max_retries = int(overrides.get("max_retries", 4))
        except (TypeError, ValueError):
            max_retries = 4
        max_retries = min(max(max_retries, 0), 8)
        return {
            "output_mode": output_mode,
            "quality": quality,
            "style_hint": str(overrides.get("style_hint") or "").strip()[:500],
            "max_retries": max_retries,
            "enable_visual_review": MathAnimatorGraph._truthy_config(
                overrides.get("enable_visual_review", overrides.get("visual_review", False))
            ),
        }

    @staticmethod
    def _truthy_config(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return False

    @staticmethod
    def _history_context(state: TutorState) -> str:
        context = state.get("context")
        if context is None:
            return ""
        return str(context.metadata.get("conversation_context_text", "") or "").strip()

    @staticmethod
    def _with_timing(state: TutorState, key: str, started: float) -> dict[str, float]:
        timings = dict(state.get("timings") or {})
        timings[key] = round(time.perf_counter() - started, 3)
        return timings

    @staticmethod
    def _normalize_analysis(
        payload: dict[str, Any],
        state: TutorState,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "learning_goal": str(payload.get("learning_goal") or state["user_message"]).strip(),
            "math_focus": MathAnimatorGraph._list_of_strings(payload.get("math_focus")),
            "visual_targets": MathAnimatorGraph._list_of_strings(payload.get("visual_targets")),
            "narrative_steps": MathAnimatorGraph._list_of_strings(payload.get("narrative_steps")),
            "reference_usage": str(payload.get("reference_usage") or "").strip(),
            "output_intent": str(payload.get("output_intent") or config["output_mode"]).strip(),
        }

    @staticmethod
    def _normalize_design(
        payload: dict[str, Any],
        state: TutorState,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "title": str(payload.get("title") or state["user_message"][:80]).strip(),
            "scene_outline": MathAnimatorGraph._list_of_strings(payload.get("scene_outline")),
            "visual_style": str(payload.get("visual_style") or config["style_hint"]).strip(),
            "animation_notes": MathAnimatorGraph._list_of_strings(payload.get("animation_notes")),
            "image_plan": MathAnimatorGraph._list_of_strings(payload.get("image_plan")),
            "code_constraints": MathAnimatorGraph._list_of_strings(payload.get("code_constraints")),
        }

    @staticmethod
    def _normalize_summary(
        payload: dict[str, Any],
        state: TutorState,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        artifacts = state.get("math_render", {}).get("artifacts", [])
        generated = (
            f"{len(artifacts)} rendered artifact(s)"
            if artifacts
            else "Generated Manim code without rendered artifacts"
        )
        summary_text = str(payload.get("summary_text") or "").strip()
        if not summary_text:
            summary_text = (
                f"Prepared a {config['output_mode']} math animation plan and Manim script."
            )
        return {
            "summary_text": summary_text,
            "user_request": str(payload.get("user_request") or state["user_message"]).strip(),
            "generated_output": str(payload.get("generated_output") or generated).strip(),
            "key_points": MathAnimatorGraph._list_of_strings(payload.get("key_points")),
        }

    @staticmethod
    def _normalize_render_result(
        raw: Any,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        if isinstance(raw, BaseModel):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            raw = {}
        artifacts = raw.get("artifacts", [])
        if not isinstance(artifacts, list):
            artifacts = []
        retry_history = raw.get("retry_history", [])
        if not isinstance(retry_history, list):
            retry_history = []
        return {
            "output_mode": str(raw.get("output_mode") or config["output_mode"]),
            "artifacts": [
                item.model_dump() if isinstance(item, BaseModel) else dict(item)
                for item in artifacts
                if isinstance(item, (dict, BaseModel))
            ],
            "public_code_path": str(raw.get("public_code_path") or ""),
            "source_code_path": str(raw.get("source_code_path") or ""),
            "quality": str(raw.get("quality") or config["quality"]),
            "retry_attempts": int(raw.get("retry_attempts") or 0),
            "retry_history": [
                item.model_dump() if isinstance(item, BaseModel) else dict(item)
                for item in retry_history
                if isinstance(item, (dict, BaseModel))
            ],
            "visual_review": raw.get("visual_review"),
            "render_skipped": bool(raw.get("render_skipped", False)),
            "skip_reason": str(raw.get("skip_reason") or ""),
        }

    @staticmethod
    def _summary(state: TutorState) -> dict[str, Any]:
        summary = dict(state.get("math_summary") or {})
        summary.setdefault("summary_text", "")
        summary.setdefault("user_request", state.get("user_message", ""))
        summary.setdefault("generated_output", "")
        summary.setdefault("key_points", [])
        return summary

    @staticmethod
    def _render(state: TutorState) -> dict[str, Any]:
        config = MathAnimatorGraph._config(state)
        return MathAnimatorGraph._normalize_render_result(state.get("math_render", {}), config)

    @staticmethod
    def _extract_generated_code(raw: str) -> str:
        text = (raw or "").strip()
        parsed = parse_json_response(text, fallback={})
        if isinstance(parsed, dict):
            code = str(parsed.get("code") or "").strip()
            if code:
                return code

        fenced = MathAnimatorGraph._strip_code_fence(text)
        if fenced != text:
            parsed = parse_json_response(fenced, fallback={})
            if isinstance(parsed, dict):
                code = str(parsed.get("code") or "").strip()
                if code:
                    return code
            if MathAnimatorGraph._looks_like_python_code(fenced):
                return fenced

        match = re.search(r"```(?:python)?\s*\n([\s\S]*?)\n```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text

    @staticmethod
    def _strip_code_fence(raw: str) -> str:
        text = (raw or "").strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if not lines:
            return text
        body = "\n".join(lines[1:]).strip()
        if body.endswith("```"):
            body = body[:-3].strip()
        return body

    @staticmethod
    def _looks_like_python_code(raw: str) -> bool:
        text = raw.lstrip()
        return text.startswith(("from ", "import ", "class ", "def "))

    @staticmethod
    def _code_system_prompt(output_mode: str) -> str:
        if output_mode == "image":
            return (
                "Generate Python Manim code for storyboard image output. "
                "Return JSON only with code and rationale. The code must consist "
                "only of one or more blocks wrapped exactly as "
                "### YON_IMAGE_1_START ### ... ### YON_IMAGE_1_END ###. "
                "Each block must define a renderable Scene class. Use MathTex "
                "for compact mathematical formulas and Text for prose."
            )
        return (
            "Generate Python Manim code for a video animation. Return JSON only "
            "with code and rationale. Define one renderable Scene class. Use "
            "MathTex for compact mathematical formulas, Text for prose, and "
            "geometric objects for the explanation."
        )

    @staticmethod
    def _fallback_code(state: TutorState, config: dict[str, Any]) -> str:
        title = str(
            state.get("math_design", {}).get("title")
            or state.get("math_analysis", {}).get("learning_goal")
            or state.get("user_message", "Math animation")
        )[:80]
        safe_title = json.dumps(title)
        scene = (
            "from manim import *\n\n"
            "class MainScene(Scene):\n"
            "    def construct(self):\n"
            f"        title = Text({safe_title}).scale(0.7)\n"
            "        subtitle = Text('Generated by SparkWeave').scale(0.45).next_to(title, DOWN)\n"
            "        self.play(Write(title))\n"
            "        self.play(FadeIn(subtitle))\n"
            "        self.wait(1)\n"
        )
        if config["output_mode"] == "image":
            return f"### YON_IMAGE_1_START ###\n{scene}\n### YON_IMAGE_1_END ###"
        return scene

    @staticmethod
    def _list_of_strings(value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _format_list_payload(payload: dict[str, Any]) -> str:
        lines: list[str] = []
        for key, value in payload.items():
            if isinstance(value, list):
                lines.append(f"{key}: {', '.join(value) or '(none)'}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _code_preview(code: str) -> str:
        if len(code) <= 1400:
            return code
        return code[:1400].rstrip() + "\n..."

