"""LangGraph implementation of SparkWeave's deep-question capability."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Literal

from pydantic import BaseModel, Field

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.core.dependencies import dependency_error
from sparkweave.core.state import TutorState, context_to_state
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
from sparkweave.llm import create_chat_model
from sparkweave.services.question import (
    QuestionParsingUnavailable,
    extract_questions_from_paper,
    parse_pdf_with_mineru,
)
from sparkweave.tools import LangChainToolRegistry

QuestionType = Literal["choice", "true_false", "fill_blank", "written", "coding"]
QUESTION_TYPES: set[str] = {"choice", "true_false", "fill_blank", "written", "coding"}
AUTO_QUESTION_TYPES: tuple[str, ...] = ("choice", "true_false", "fill_blank", "written")

QUESTION_SYSTEM_PROMPT = """\
You are SparkWeave's quiz generation graph. Generate useful learning questions
that match the requested topic, difficulty, and question type. Keep outputs
structured so the quiz UI can render them directly.

Treat each question as an assessment signal: test one concrete knowledge point,
make distractors diagnose common misconceptions, and write explanations that
teach why the correct answer is correct and why tempting wrong answers fail.
Support interactive practice across choice, true_false, fill_blank, written,
and coding questions.
"""


class QuestionTemplatePayload(BaseModel):
    concentration: str = Field(description="The specific concept or skill to test.")
    question_type: QuestionType = "written"
    difficulty: str = "medium"
    rationale: str = ""


class IdeationPayload(BaseModel):
    templates: list[QuestionTemplatePayload]


class GeneratedQuestionPayload(BaseModel):
    question_type: QuestionType = "written"
    question: str
    options: dict[str, str] | None = None
    correct_answer: str
    explanation: str


class DeepQuestionGraph:
    """Explicit graph for ideation, generation, validation, repair, and output."""

    source = "deep_question"

    def __init__(
        self,
        *,
        model: Any | None = None,
        tool_registry: LangChainToolRegistry | None = None,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry or LangChainToolRegistry()
        self._compiled: Any | None = None

    async def run(self, context: UnifiedContext, stream: StreamBus) -> TutorState:
        state = context_to_state(
            context,
            stream=stream,
            system_prompt=QUESTION_SYSTEM_PROMPT,
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
        builder.add_node("ideate", self._ideate_node)
        builder.add_node("generate", self._generate_node)
        builder.add_node("validate", self._validate_node)
        builder.add_node("repair", self._repair_node)
        builder.add_node("write", self._write_node)

        builder.add_edge(START, "ideate")
        builder.add_conditional_edges(
            "ideate",
            self._route_after_ideation,
            {"generate": "generate", "write": "write"},
        )
        builder.add_edge("generate", "validate")
        builder.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {"repair": "repair", "write": "write"},
        )
        builder.add_edge("repair", "write")
        builder.add_edge("write", END)
        self._compiled = builder.compile()
        return self._compiled

    async def _ideate_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        config = self._config(state)
        if config["mode"] == "mimic":
            return await self._ideate_mimic_node(state, config)
        if config["mode"] != "custom":
            message = f"LangGraph deep_question does not support mode `{config['mode']}`."
            await stream.error(message, source=self.source, stage="ideation")
            return {"errors": [message], "templates": []}

        async with stream.stage("ideation", source=self.source):
            topic = config["topic"]
            knowledge_context = await self._retrieve_knowledge(state, topic)
            await stream.progress(
                "Generating question templates...",
                source=self.source,
                stage="ideation",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            payload = await self._ainvoke_json(
                system=(
                    "Generate concise quiz templates. Return templates that are "
                    "diverse, aligned to the requested difficulty/type, and not "
                    "full questions yet. Cover different cognitive levels when "
                    "possible: recall, understanding, application, and diagnosis "
                    "of misconceptions."
                ),
                user=(
                    f"Topic: {topic}\n"
                    f"Number requested: {config['num_questions']}\n"
                    f"Difficulty: {config['difficulty'] or 'auto'}\n"
                    f"Question type: {config['question_type'] or 'auto'}\n"
                    f"Preference: {config['preference'] or '(none)'}\n\n"
                    f"Knowledge context:\n{knowledge_context or '(none)'}\n\n"
                    'Return JSON: {"templates": [{"concentration": "...", '
                    '"question_type": "choice|true_false|fill_blank|written|coding", '
                    '"difficulty": "...", "rationale": "..."}]}'
                ),
                schema=IdeationPayload,
            )
            templates = self._normalize_templates(payload, config, knowledge_context)
            await stream.thinking(
                self._format_templates(templates),
                source=self.source,
                stage="ideation",
                metadata={"trace_kind": "llm_output"},
            )
            await stream.progress(
                "",
                source=self.source,
                stage="ideation",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {"templates": templates}

    async def _ideate_mimic_node(
        self,
        state: TutorState,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        stream = state["stream"]
        async with stream.stage("ideation", source=self.source):
            await stream.progress(
                "Loading exam paper templates...",
                source=self.source,
                stage="ideation",
                metadata={"trace_kind": "call_status", "call_state": "running"},
            )
            try:
                questions, trace = self._load_mimic_questions(state, config)
            except Exception as exc:
                message = str(exc)
                await stream.error(message, source=self.source, stage="ideation")
                return {
                    "errors": [message],
                    "templates": [],
                    "artifacts": {
                        **dict(state.get("artifacts", {}) or {}),
                        "mimic_trace": {"error": message, "runtime": "langgraph"},
                    },
                }

            templates = self._normalize_mimic_templates(
                questions,
                count=config["max_questions"],
            )
            if not templates:
                message = "No reference questions were found for mimic mode."
                await stream.error(message, source=self.source, stage="ideation")
                return {
                    "errors": [message],
                    "templates": [],
                    "artifacts": {
                        **dict(state.get("artifacts", {}) or {}),
                        "mimic_trace": {
                            **trace,
                            "error": message,
                            "runtime": "langgraph",
                        },
                    },
                }

            trace = {**trace, "template_count": len(templates), "runtime": "langgraph"}
            await stream.thinking(
                self._format_templates(templates),
                source=self.source,
                stage="ideation",
                metadata={
                    "trace_kind": "templates_ready",
                    "source": "mimic",
                    "template_count": len(templates),
                },
            )
            await stream.progress(
                "",
                source=self.source,
                stage="ideation",
                metadata={"trace_kind": "call_status", "call_state": "complete"},
            )
        return {
            "templates": templates,
            "artifacts": {
                **dict(state.get("artifacts", {}) or {}),
                "mimic_trace": trace,
            },
        }

    async def _generate_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        config = self._config(state)
        questions: list[dict[str, Any]] = []
        previous_questions: list[str] = []

        async with stream.stage("generation", source=self.source):
            for index, template in enumerate(state.get("templates", []), start=1):
                question_id = str(template.get("question_id") or f"q_{index}")
                await stream.progress(
                    f"Generating Question {index}...",
                    source=self.source,
                    stage="generation",
                    metadata={
                        "trace_kind": "call_status",
                        "call_state": "running",
                        "question_id": question_id,
                    },
                )
                payload = await self._ainvoke_json(
                    system=self._generation_system_prompt(config["mode"]),
                    user=(
                        f"Template:\n{json.dumps(template, ensure_ascii=False, indent=2)}\n\n"
                        f"Topic: {config['topic']}\n"
                        f"Preference: {config['preference'] or '(none)'}\n"
                        f"Previous questions:\n{self._format_previous_questions(previous_questions)}\n"
                        f"Conversation context:\n{self._history_context(state)}\n\n"
                        "Return JSON with keys: question_type, question, options, "
                        "correct_answer, explanation."
                    ),
                    schema=GeneratedQuestionPayload,
                )
                qa_pair = self._build_qa_pair(template, payload)
                questions.append(
                    {
                        "template": template,
                        "qa_pair": qa_pair,
                        "success": True,
                    }
                )
                previous_questions.append(str(qa_pair.get("question") or ""))
                await stream.progress(
                    "",
                    source=self.source,
                    stage="generation",
                    metadata={
                        "trace_kind": "call_status",
                        "call_state": "complete",
                        "question_id": question_id,
                    },
                )
        return {"questions": questions}

    async def _validate_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        questions = list(state.get("questions", []))
        validation: dict[str, Any] = {"needs_repair": [], "items": {}}

        async with stream.stage("generation", source=self.source):
            for item in questions:
                qa_pair = item.get("qa_pair", {})
                template = item.get("template", {})
                question_id = str(qa_pair.get("question_id") or template.get("question_id") or "")
                expected_type = self._normalize_question_type(
                    template.get("question_type", "written")
                )
                normalized = self._normalize_payload_shape(expected_type, qa_pair)
                normalized["question_id"] = question_id
                normalized["concentration"] = template.get("concentration", "")
                normalized["difficulty"] = template.get("difficulty", "")
                issues = self._collect_payload_issues(expected_type, normalized)
                normalized["validation"] = {
                    "requested_question_type": expected_type,
                    "schema_ok": not issues,
                    "repaired": False,
                    "issues": issues,
                }
                item["qa_pair"] = normalized
                validation["items"][question_id] = normalized["validation"]
                if issues:
                    validation["needs_repair"].append(question_id)

            await stream.observation(
                self._format_validation(validation),
                source=self.source,
                stage="generation",
                metadata={"trace_kind": "validation"},
            )
        return {"questions": questions, "validation": validation}

    async def _repair_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        questions = list(state.get("questions", []))
        needs_repair = set(state.get("validation", {}).get("needs_repair", []))

        async with stream.stage("generation", source=self.source):
            for item in questions:
                qa_pair = item.get("qa_pair", {})
                question_id = str(qa_pair.get("question_id") or "")
                if question_id not in needs_repair:
                    continue
                template = item.get("template", {})
                expected_type = self._normalize_question_type(
                    template.get("question_type", "written")
                )
                await stream.progress(
                    f"Repairing {question_id}...",
                    source=self.source,
                    stage="generation",
                    metadata={"trace_kind": "call_status", "call_state": "running"},
                )
                repaired = await self._ainvoke_json(
                    system=(
                        "Repair the invalid quiz JSON. Keep the original intent, "
                        "but strictly satisfy the expected question_type."
                    ),
                    user=(
                        f"Expected question_type: {expected_type}\n"
                        f"Template:\n{json.dumps(template, ensure_ascii=False, indent=2)}\n\n"
                        f"Invalid payload:\n{json.dumps(qa_pair, ensure_ascii=False, indent=2)}\n\n"
                        "Return JSON with keys: question_type, question, options, "
                        "correct_answer, explanation."
                    ),
                    schema=GeneratedQuestionPayload,
                )
                normalized = self._normalize_payload_shape(expected_type, repaired)
                normalized["question_id"] = question_id
                normalized["concentration"] = template.get("concentration", "")
                normalized["difficulty"] = template.get("difficulty", "")
                issues = self._collect_payload_issues(expected_type, normalized)
                normalized["validation"] = {
                    "requested_question_type": expected_type,
                    "schema_ok": not issues,
                    "repaired": True,
                    "issues": issues,
                }
                item["qa_pair"] = normalized
                item["success"] = not issues
                await stream.progress(
                    "",
                    source=self.source,
                    stage="generation",
                    metadata={"trace_kind": "call_status", "call_state": "complete"},
                )
        return {"questions": questions}

    async def _write_node(self, state: TutorState) -> dict[str, Any]:
        stream = state["stream"]
        config = self._config(state)
        async with stream.stage("generation", source=self.source):
            if state.get("errors"):
                body = "\n".join(str(item) for item in state.get("errors", []))
                await stream.content(body, source=self.source, stage="generation")
                await stream.result(
                    {
                        "response": body,
                        "summary": {
                            "success": False,
                            "results": [],
                            "errors": state.get("errors", []),
                            "mode": config["mode"],
                        },
                        "mode": config["mode"],
                        "runtime": "langgraph",
                    },
                    source=self.source,
                )
                return {"final_answer": body}

            summary = self._build_summary(state, config)
            body = self._render_summary_markdown(summary)
            if body:
                await stream.content(body, source=self.source, stage="generation")
            await stream.result(
                {
                    "response": body or "No questions generated.",
                    "summary": summary,
                    "mode": config["mode"],
                    "runtime": "langgraph",
                },
                source=self.source,
            )
        return {"final_answer": body}

    def _route_after_ideation(self, state: TutorState) -> str:
        return "write" if state.get("errors") else "generate"

    def _route_after_validation(self, state: TutorState) -> str:
        return "repair" if state.get("validation", {}).get("needs_repair") else "write"

    async def _run_answer_now(
        self,
        state: TutorState,
        payload: dict[str, Any],
    ) -> TutorState:
        stream = state["stream"]
        config = self._config(state)
        original, partial, trace_summary = answer_now_parts(state, payload)
        notice = skip_notice(capability=self.source, stages_skipped=["ideation"])

        async with stream.stage("generation", source=self.source):
            await stream.progress(
                "Generating answer-now quiz payload...",
                source=self.source,
                stage="generation",
                metadata=answer_now_progress_metadata("running"),
            )
            parsed = await self._ainvoke_json(
                system=(
                    "You are SparkWeave's question generator. The user is "
                    "waiting, so produce a complete question set in one shot "
                    "using the gathered context. Return JSON only with key "
                    "`questions`, an array of objects containing question_id, "
                    "question, question_type, options, correct_answer, "
                    "explanation, difficulty, and concentration. Supported "
                    "question_type values are choice, true_false, fill_blank, "
                    "written, and coding."
                ),
                user=answer_now_user_prompt(
                    original=original,
                    partial=partial,
                    trace_summary=trace_summary,
                    extra_context=(
                        f"Topic: {config['topic'] or original}\n"
                        f"Number of questions: {config['num_questions']}\n"
                        f"Preferred type: {config['question_type'] or 'auto'}\n"
                        f"Preferred difficulty: {config['difficulty'] or 'auto'}\n"
                        f"Preference: {config['preference'] or '(none)'}"
                    ),
                    final_instruction='Return JSON: {"questions": [...]}',
                ),
            )
            results = self._answer_now_results(parsed, config, original)
            summary = self._answer_now_summary(results, config)
            body = self._render_summary_markdown(summary)
            body = answer_now_body(body, notice=notice)
            if body:
                await stream.content(body, source=self.source, stage="generation")
            await stream.progress(
                "",
                source=self.source,
                stage="generation",
                metadata=answer_now_progress_metadata("complete"),
            )
            await stream.result(
                {
                    "response": body or "No questions generated.",
                    "summary": summary,
                    "mode": "answer_now",
                    "metadata": answer_now_metadata(),
                    "runtime": "langgraph",
                },
                source=self.source,
            )

        state["user_message"] = original
        state["questions"] = results
        state["final_answer"] = body
        state["artifacts"] = {
            **dict(state.get("artifacts", {}) or {}),
            "deep_question": {"summary": summary, "runtime": "langgraph"},
        }
        return state

    async def _retrieve_knowledge(self, state: TutorState, topic: str) -> str:
        enabled_tools = set(state.get("enabled_tools") or [])
        if "rag" not in enabled_tools or not state.get("knowledge_bases"):
            return ""

        stream = state["stream"]
        kb_name = state["knowledge_bases"][0]
        await stream.tool_call(
            tool_name="rag",
            args={"query": topic, "kb_name": kb_name},
            source=self.source,
            stage="ideation",
            metadata={"trace_kind": "tool_call", "tool_name": "rag"},
        )
        try:
            result = await self.tool_registry.execute("rag", query=topic, kb_name=kb_name)
            content = result.content or ""
            success = result.success
            sources = result.sources
        except Exception as exc:
            content = f"RAG retrieval failed: {exc}"
            success = False
            sources = []
        await stream.tool_result(
            tool_name="rag",
            result=content,
            source=self.source,
            stage="ideation",
            metadata={
                "trace_kind": "tool_result",
                "tool_name": "rag",
                "success": success,
                "sources": sources,
            },
        )
        return content[:6000]

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
        topic = str(overrides.get("topic") or state.get("user_message") or "").strip()
        num_questions = int(overrides.get("num_questions", 1) or 1)
        max_questions = int(overrides.get("max_questions", 10) or 10)
        return {
            "mode": str(overrides.get("mode", "custom") or "custom").strip().lower(),
            "topic": topic,
            "num_questions": max(1, min(num_questions, 50)),
            "max_questions": max(1, min(max_questions, 100)),
            "difficulty": str(overrides.get("difficulty", "") or "").strip().lower(),
            "question_type": str(overrides.get("question_type", "") or "").strip().lower(),
            "preference": str(overrides.get("preference", "") or "").strip(),
            "paper_path": str(overrides.get("paper_path", "") or "").strip(),
        }

    @staticmethod
    def _history_context(state: TutorState) -> str:
        context = state.get("context")
        if context is None:
            return ""
        return str(context.metadata.get("conversation_context_text", "") or "").strip()

    def _normalize_templates(
        self,
        payload: dict[str, Any],
        config: dict[str, Any],
        knowledge_context: str,
    ) -> list[dict[str, Any]]:
        raw_templates = payload.get("templates", [])
        if not isinstance(raw_templates, list):
            raw_templates = []
        templates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_templates:
            if isinstance(item, BaseModel):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            concentration = str(item.get("concentration") or "").strip()
            if not concentration or concentration.lower() in seen:
                continue
            seen.add(concentration.lower())
            templates.append(
                {
                    "question_id": f"q_{len(templates) + 1}",
                    "concentration": concentration,
                    "question_type": self._resolve_question_type(
                        config["question_type"], item.get("question_type")
                    ),
                    "difficulty": config["difficulty"]
                    or str(item.get("difficulty") or "medium").strip()
                    or "medium",
                    "source": "custom",
                    "metadata": {
                        "rationale": str(item.get("rationale") or "").strip(),
                        "knowledge_context": knowledge_context,
                    },
                }
            )
            if len(templates) >= config["num_questions"]:
                break
        while len(templates) < config["num_questions"]:
            index = len(templates) + 1
            fallback_type = (
                AUTO_QUESTION_TYPES[(index - 1) % len(AUTO_QUESTION_TYPES)]
                if config["question_type"] in {"", "auto", "mixed"}
                else "written"
            )
            templates.append(
                {
                    "question_id": f"q_{index}",
                    "concentration": f"{config['topic']} - aspect {index}",
                    "question_type": self._resolve_question_type(
                        config["question_type"], fallback_type
                    ),
                    "difficulty": config["difficulty"] or "medium",
                    "source": "custom",
                    "metadata": {
                        "rationale": "Fallback template generated by LangGraph runtime.",
                        "knowledge_context": knowledge_context,
                    },
                }
            )
        return templates

    def _load_mimic_questions(
        self,
        state: TutorState,
        config: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        paper_path = str(config.get("paper_path") or "").strip()
        if paper_path:
            return self._load_mimic_questions_from_path(
                Path(paper_path),
                max_questions=config["max_questions"],
            )

        context = state.get("context")
        attachment = None
        for item in getattr(context, "attachments", []) if context is not None else []:
            if (
                str(getattr(item, "type", "") or "").lower() == "pdf"
                or str(getattr(item, "mime_type", "") or "").lower() == "application/pdf"
                or str(getattr(item, "filename", "") or "").lower().endswith(".pdf")
            ):
                attachment = item
                break

        if attachment is None or not getattr(attachment, "base64", ""):
            raise ValueError(
                "Mimic mode requires either an uploaded PDF or a parsed exam directory."
            )

        raw_b64 = str(getattr(attachment, "base64", "") or "")
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / (getattr(attachment, "filename", "") or "exam.pdf")
            pdf_path.write_bytes(base64.b64decode(raw_b64))
            return self._load_mimic_questions_from_path(
                pdf_path,
                max_questions=config["max_questions"],
            )

    @staticmethod
    def _load_mimic_questions_from_path(
        paper_path: Path,
        *,
        max_questions: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not paper_path.exists():
            raise ValueError(f"Mimic paper path not found: {paper_path}")

        if paper_path.is_file() and paper_path.suffix.lower() == ".json":
            return DeepQuestionGraph._read_question_json(
                paper_path,
                max_questions=max_questions,
                trace={"paper_dir": str(paper_path.parent), "question_file": str(paper_path)},
            )

        if paper_path.is_dir():
            question_file = DeepQuestionGraph._find_or_extract_question_json(paper_path)
            return DeepQuestionGraph._read_question_json(
                question_file,
                max_questions=max_questions,
                trace={"paper_dir": str(paper_path), "question_file": str(question_file)},
            )

        if paper_path.is_file() and paper_path.suffix.lower() == ".pdf":
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_dir = Path(tmp_dir)
                try:
                    parsed = parse_pdf_with_mineru(str(paper_path), str(output_dir))
                except QuestionParsingUnavailable as exc:
                    raise ValueError(
                        "PDF mimic mode requires the local PDF/MinerU parsing dependencies."
                    ) from exc
                if not parsed:
                    raise ValueError("Failed to parse exam paper with MinerU.")
                subdirs = sorted(
                    [item for item in output_dir.iterdir() if item.is_dir()],
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )
                if not subdirs:
                    raise ValueError("No parsed exam directory found after PDF parsing.")
                working_dir = subdirs[0]
                question_files = list(working_dir.glob("*_questions.json"))
                if not question_files:
                    try:
                        extracted = extract_questions_from_paper(
                            str(working_dir), output_dir=None
                        )
                    except QuestionParsingUnavailable as exc:
                        raise ValueError(
                            "Parsed exam directory does not contain question JSON output."
                        ) from exc
                    if not extracted:
                        raise ValueError("Failed to extract questions from parsed exam.")
                    question_files = list(working_dir.glob("*_questions.json"))
                if not question_files:
                    raise ValueError("Question extraction output not found.")
                return DeepQuestionGraph._read_question_json(
                    question_files[0],
                    max_questions=max_questions,
                    trace={
                        "paper_dir": str(working_dir),
                        "question_file": str(question_files[0]),
                    },
                )

        raise ValueError(
            "Mimic mode paper_path must be a parsed exam directory, a question JSON file, or a PDF."
        )

    @staticmethod
    def _find_or_extract_question_json(paper_dir: Path) -> Path:
        question_files = list(paper_dir.glob("*_questions.json"))
        if not question_files:
            direct = paper_dir / "questions.json"
            if direct.exists():
                question_files = [direct]
        if not question_files:
            try:
                extracted = extract_questions_from_paper(str(paper_dir), output_dir=None)
            except QuestionParsingUnavailable as exc:
                raise ValueError(
                    "Parsed exam directory does not contain question JSON output."
                ) from exc
            if not extracted:
                raise ValueError("Failed to extract questions from parsed exam.")
            question_files = list(paper_dir.glob("*_questions.json"))
        if not question_files:
            raise ValueError("Question extraction output not found.")
        return question_files[0]

    @staticmethod
    def _read_question_json(
        question_file: Path,
        *,
        max_questions: int,
        trace: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        try:
            payload = json.loads(question_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid question JSON: {question_file}") from exc
        if isinstance(payload, dict):
            raw_questions = payload.get("questions", [])
        elif isinstance(payload, list):
            raw_questions = payload
        else:
            raw_questions = []
        if not isinstance(raw_questions, list):
            raw_questions = []
        questions = [item for item in raw_questions if isinstance(item, dict)]
        if max_questions > 0:
            questions = questions[:max_questions]
        return questions, {**trace, "raw_question_count": len(questions)}

    @staticmethod
    def _normalize_mimic_templates(
        questions: list[dict[str, Any]],
        *,
        count: int,
    ) -> list[dict[str, Any]]:
        templates: list[dict[str, Any]] = []
        for item in questions[:count]:
            question_text = str(
                item.get("question_text") or item.get("question") or item.get("stem") or ""
            ).strip()
            if not question_text:
                continue
            index = len(templates) + 1
            raw_type = str(item.get("question_type") or item.get("type") or "").lower()
            templates.append(
                {
                    "question_id": f"q_{index}",
                    "concentration": question_text[:240],
                    "question_type": DeepQuestionGraph._normalize_mimic_question_type(raw_type),
                    "difficulty": "medium",
                    "source": "mimic",
                    "reference_question": question_text,
                    "reference_answer": str(item.get("answer", "") or "").strip() or None,
                    "metadata": {
                        "question_number": item.get("question_number", str(index)),
                        "images": item.get("images", []),
                    },
                }
            )
        return templates

    @staticmethod
    def _normalize_mimic_question_type(raw_type: str) -> str:
        lowered = str(raw_type or "").strip().lower()
        if "choice" in lowered or "multiple" in lowered or lowered in {"mcq", "select"}:
            return "choice"
        if "true" in lowered or "false" in lowered or "judge" in lowered:
            return "true_false"
        if "blank" in lowered or "fill" in lowered or "cloze" in lowered:
            return "fill_blank"
        if "code" in lowered or "program" in lowered:
            return "coding"
        return "written"

    @classmethod
    def _build_qa_pair(cls, template: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        expected_type = cls._normalize_question_type(template.get("question_type", "written"))
        normalized = cls._normalize_payload_shape(expected_type, payload)
        normalized["question_id"] = template.get("question_id", "")
        normalized["concentration"] = template.get("concentration", "")
        normalized["difficulty"] = template.get("difficulty", "")
        normalized["metadata"] = {
            "source": template.get("source", "custom"),
            "knowledge_context": (template.get("metadata") or {}).get("knowledge_context", ""),
        }
        return normalized

    @staticmethod
    def _resolve_question_type(requested: str, candidate: Any) -> str:
        if requested and requested not in {"auto", "mixed"}:
            return DeepQuestionGraph._normalize_question_type(requested)
        return DeepQuestionGraph._normalize_question_type(str(candidate or "written"))

    @staticmethod
    def _generation_system_prompt(mode: str) -> str:
        type_rules = (
            "Supported question_type values: choice, true_false, fill_blank, "
            "written, coding. For choice, use exactly options A-D and "
            "correct_answer as the option key. For true_false, use "
            'correct_answer as "True" or "False" and keep options empty or '
            'as {"True":"Correct","False":"Incorrect"}. For fill_blank, '
            "include a visible blank such as ____ in the question and put the "
            "expected phrase in correct_answer. For written, make the expected "
            "answer concise and gradeable. For coding, specify input/output or "
            "observable behavior clearly. Explanations must include the tested "
            "knowledge point and a short reason a learner can act on."
        )
        if mode == "mimic":
            return (
                "Generate one new quiz question that mimics the reference exam "
                "question's style, difficulty, and skill focus without copying it. "
                "Keep it suitable for interactive practice and avoid ambiguity. "
                f"Return JSON only. {type_rules}"
            )
        return (
            "Generate one high-quality quiz question from the template. Make it "
            "interactive, unambiguous, and aligned to the learner's topic. "
            f"Return JSON only. {type_rules}"
        )

    @staticmethod
    def _normalize_question_type(question_type: Any) -> str:
        normalized = str(question_type or "").strip().lower()
        aliases = {
            "multiple_choice": "choice",
            "multiple-choice": "choice",
            "mcq": "choice",
            "select": "choice",
            "single_choice": "choice",
            "truefalse": "true_false",
            "true-false": "true_false",
            "tf": "true_false",
            "judge": "true_false",
            "judgement": "true_false",
            "judgment": "true_false",
            "判断": "true_false",
            "判断题": "true_false",
            "是非题": "true_false",
            "fill": "fill_blank",
            "blank": "fill_blank",
            "fill_in_blank": "fill_blank",
            "fill-in-the-blank": "fill_blank",
            "cloze": "fill_blank",
            "填空": "fill_blank",
            "填空题": "fill_blank",
            "open_ended": "written",
            "short_answer": "written",
            "subjective": "written",
            "programming": "coding",
            "code": "coding",
        }
        normalized = aliases.get(normalized, normalized)
        return normalized if normalized in QUESTION_TYPES else "written"

    @classmethod
    def _normalize_payload_shape(
        cls,
        expected_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(payload or {})
        normalized["question_type"] = expected_type
        normalized["question"] = str(normalized.get("question", "") or "").strip()
        normalized["correct_answer"] = str(normalized.get("correct_answer", "") or "").strip()
        normalized["explanation"] = str(normalized.get("explanation", "") or "").strip()
        raw_options = normalized.get("options")

        if expected_type == "choice":
            clean_options: dict[str, str] = {}
            if isinstance(raw_options, dict):
                for key, value in raw_options.items():
                    option_key = str(key or "").strip().upper()[:1]
                    option_value = str(value or "").strip()
                    if option_key in {"A", "B", "C", "D"} and option_value:
                        clean_options[option_key] = option_value
            normalized["options"] = clean_options or None
            answer_upper = normalized["correct_answer"].upper()
            if clean_options and answer_upper not in clean_options:
                for key, value in clean_options.items():
                    if normalized["correct_answer"].lower() == value.lower():
                        normalized["correct_answer"] = key
                        break
        elif expected_type == "true_false":
            normalized["options"] = {"True": "正确", "False": "错误"}
            normalized["correct_answer"] = cls._normalize_true_false_answer(
                normalized["correct_answer"]
            )
        elif expected_type == "fill_blank":
            normalized["options"] = None
            if normalized["question"] and not cls._question_has_blank(normalized["question"]):
                normalized["question"] = f"{normalized['question']} ____"
        else:
            normalized["options"] = None
        return normalized

    @classmethod
    def _collect_payload_issues(
        cls,
        expected_type: str,
        payload: dict[str, Any],
    ) -> list[str]:
        issues: list[str] = []
        question = str(payload.get("question", "") or "")
        correct_answer = str(payload.get("correct_answer", "") or "").strip()
        options = payload.get("options")
        if not question:
            issues.append("missing_question")
        if not correct_answer:
            issues.append("missing_correct_answer")
        if not str(payload.get("explanation", "") or "").strip():
            issues.append("missing_explanation")

        if expected_type == "choice":
            option_keys = set(options.keys()) if isinstance(options, dict) else set()
            if option_keys != {"A", "B", "C", "D"}:
                issues.append("choice_options_must_be_a_to_d")
            if correct_answer.upper() not in {"A", "B", "C", "D"}:
                issues.append("choice_correct_answer_must_be_option_key")
        elif expected_type == "true_false":
            if correct_answer not in {"True", "False"}:
                issues.append("true_false_answer_must_be_true_or_false")
        elif expected_type == "fill_blank":
            if not cls._question_has_blank(question):
                issues.append("fill_blank_question_must_include_blank")
        elif cls._payload_looks_like_choice(question, correct_answer, options):
            issues.append("non_choice_payload_looks_like_multiple_choice")
        return issues

    @staticmethod
    def _question_has_blank(question: str) -> bool:
        return bool(re.search(r"_{2,}|____|\(\s*\)|（\s*）|\[\s*\]", question))

    @staticmethod
    def _normalize_true_false_answer(answer: Any) -> str:
        value = str(answer or "").strip().lower()
        true_values = {"true", "t", "yes", "y", "correct", "right", "对", "正确", "是", "真"}
        false_values = {"false", "f", "no", "n", "incorrect", "wrong", "错", "错误", "否", "假"}
        if value in true_values:
            return "True"
        if value in false_values:
            return "False"
        return str(answer or "").strip()

    @staticmethod
    def _payload_looks_like_choice(question: str, correct_answer: str, options: Any) -> bool:
        if isinstance(options, dict) and bool(options):
            return True
        lowered = question.lower()
        if re.search(
            r"\b(select|choose|pick|which of the following|which option|multiple[- ]choice)\b",
            lowered,
        ):
            return True
        return correct_answer.upper() in {"A", "B", "C", "D"}

    @staticmethod
    def _format_templates(templates: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"- {item.get('question_id')}: {item.get('concentration')} "
            f"({item.get('question_type')}/{item.get('difficulty')})"
            for item in templates
        )

    @staticmethod
    def _format_previous_questions(questions: list[str]) -> str:
        if not questions:
            return "(none)"
        return "\n".join(f"{idx}. {question}" for idx, question in enumerate(questions, 1))

    @staticmethod
    def _format_validation(validation: dict[str, Any]) -> str:
        needs_repair = validation.get("needs_repair", [])
        if not needs_repair:
            return "Validation passed."
        return "Needs repair: " + ", ".join(str(item) for item in needs_repair)

    @classmethod
    def _answer_now_results(
        cls,
        parsed: Any,
        config: dict[str, Any],
        original: str,
    ) -> list[dict[str, Any]]:
        if isinstance(parsed, dict):
            raw_items = parsed.get("questions")
        else:
            raw_items = parsed
        if not isinstance(raw_items, list):
            raw_items = []

        results: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items[: config["num_questions"]], start=1):
            if not isinstance(raw, dict):
                continue
            expected_type = cls._resolve_question_type(
                config["question_type"],
                raw.get("question_type"),
            )
            qa_pair = cls._normalize_payload_shape(expected_type, raw)
            qa_pair["question_id"] = str(raw.get("question_id") or f"q_{index}")
            qa_pair["concentration"] = str(
                raw.get("concentration") or config["topic"] or original
            ).strip()
            qa_pair["difficulty"] = str(
                raw.get("difficulty") or config["difficulty"] or ""
            ).strip()
            issues = cls._collect_payload_issues(expected_type, qa_pair)
            qa_pair["validation"] = {
                "requested_question_type": expected_type,
                "schema_ok": not issues,
                "repaired": False,
                "issues": issues,
                "answer_now": True,
            }
            results.append(
                {
                    "template": {
                        "question_id": qa_pair["question_id"],
                        "concentration": qa_pair["concentration"],
                        "question_type": expected_type,
                        "difficulty": qa_pair["difficulty"],
                        "source": "answer_now",
                    },
                    "qa_pair": qa_pair,
                    "success": not issues,
                    "metadata": {"answer_now": True},
                }
            )

        if results:
            return results

        expected_type = cls._resolve_question_type(config["question_type"], "written")
        fallback = {
            "question_type": expected_type,
            "question": original,
            "correct_answer": "",
            "explanation": "Answer-now could not parse a structured question payload.",
        }
        qa_pair = cls._normalize_payload_shape(expected_type, fallback)
        qa_pair["question_id"] = "q_1"
        qa_pair["concentration"] = config["topic"] or original
        qa_pair["difficulty"] = config["difficulty"]
        qa_pair["validation"] = {
            "requested_question_type": expected_type,
            "schema_ok": False,
            "repaired": False,
            "issues": ["unparseable_answer_now_payload"],
            "answer_now": True,
        }
        return [
            {
                "template": {
                    "question_id": "q_1",
                    "concentration": qa_pair["concentration"],
                    "question_type": expected_type,
                    "difficulty": qa_pair["difficulty"],
                    "source": "answer_now",
                },
                "qa_pair": qa_pair,
                "success": False,
                "metadata": {"answer_now": True},
            }
        ]

    @staticmethod
    def _answer_now_summary(
        results: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        completed = sum(1 for item in results if item.get("success", True))
        failed = len(results) - completed
        return {
            "success": bool(results) and failed == 0,
            "source": "answer_now",
            "requested": config["num_questions"],
            "template_count": len(results),
            "completed": completed,
            "failed": failed,
            "templates": [item.get("template", {}) for item in results],
            "results": results,
            "trace": {"runtime": "langgraph", "answer_now": True},
            "mode": "answer_now",
        }

    @staticmethod
    def _build_summary(state: TutorState, config: dict[str, Any]) -> dict[str, Any]:
        questions = list(state.get("questions", []))
        completed = sum(1 for item in questions if item.get("success", True))
        failed = len(questions) - completed
        is_mimic = config["mode"] == "mimic"
        artifacts = state.get("artifacts", {}) if isinstance(state.get("artifacts"), dict) else {}
        return {
            "success": completed > 0 and failed == 0,
            "source": "exam" if is_mimic else "topic",
            "requested": config["max_questions"] if is_mimic else config["num_questions"],
            "template_count": len(state.get("templates", [])),
            "completed": completed,
            "failed": failed,
            "templates": state.get("templates", []),
            "results": questions,
            "trace": artifacts.get("mimic_trace", {"runtime": "langgraph"}),
            "mode": config["mode"],
        }

    @staticmethod
    def _render_summary_markdown(summary: dict[str, Any]) -> str:
        results = summary.get("results", []) if isinstance(summary, dict) else []
        lines: list[str] = []
        for idx, item in enumerate(results, 1):
            qa_pair = item.get("qa_pair", {}) if isinstance(item, dict) else {}
            question = qa_pair.get("question", "")
            if not question:
                continue
            lines.append(f"### Question {idx}\n")
            lines.append(str(question))
            options = qa_pair.get("options", {})
            if isinstance(options, dict) and options:
                for key, value in options.items():
                    lines.append(f"- {key}. {value}")
            answer = qa_pair.get("correct_answer", "")
            if answer:
                lines.append(f"\n**Answer:** {answer}")
            explanation = qa_pair.get("explanation", "")
            if explanation:
                lines.append(f"\n**Explanation:** {explanation}")
            lines.append("")
        return "\n".join(lines).strip()

