"""Question/answer pair generator used by NG deep-question workflows."""

from __future__ import annotations

import json
import re
from typing import Any

from sparkweave.agents.base_agent import BaseAgent
from sparkweave.agents.question.models import QAPair, QuestionTemplate
from sparkweave.core.trace import build_trace_metadata, new_call_id
from sparkweave.services.prompting import ToolPromptComposer
from sparkweave.tools.registry import get_tool_registry


class Generator(BaseAgent):
    """Generate a question/answer pair from one template."""

    MAX_PREVIOUS_QUESTIONS = 20

    def __init__(
        self,
        kb_name: str | None = None,
        language: str = "en",
        tool_flags: dict[str, bool] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            module_name="question",
            agent_name="generator",
            language=language,
            **kwargs,
        )
        self.kb_name = kb_name
        self.tool_flags = tool_flags or {}
        self._tool_registry = get_tool_registry()

    async def process(
        self,
        template: QuestionTemplate,
        user_topic: str = "",
        preference: str = "",
        history_context: str = "",
        previous_questions: list[str] | None = None,
    ) -> QAPair:
        """Generate one Q-A pair from a template in a single call."""
        available_tools = self._build_available_tools_text()
        knowledge_context = str(template.metadata.get("knowledge_context", "")).strip()
        prev_q_text = self._format_previous_questions(previous_questions)
        payload = await self._generate_payload(
            template=template,
            user_topic=user_topic,
            preference=preference,
            history_context=history_context,
            knowledge_context=knowledge_context,
            available_tools=available_tools,
            previous_questions=prev_q_text,
        )
        payload, validation = await self._validate_and_repair_payload(
            template=template,
            payload=payload,
            user_topic=user_topic,
            preference=preference,
            history_context=history_context,
            knowledge_context=knowledge_context,
            available_tools=available_tools,
            previous_questions=prev_q_text,
        )
        return QAPair(
            question_id=template.question_id,
            question=payload.get("question", ""),
            correct_answer=payload.get("correct_answer", ""),
            explanation=payload.get("explanation", ""),
            question_type=payload.get("question_type", template.question_type),
            options=payload.get("options") if isinstance(payload.get("options"), dict) else None,
            concentration=template.concentration,
            difficulty=template.difficulty,
            validation=validation,
            metadata={
                "source": template.source,
                "reference_question": template.reference_question,
                "enabled_tools": self._enabled_tool_names(),
                "available_tools": available_tools,
                "knowledge_context": knowledge_context,
            },
        )

    def _build_available_tools_text(self) -> str:
        enabled_tools = self._enabled_tool_names()
        if not enabled_tools:
            return "(no tools available)"
        hints = self._tool_registry.get_prompt_hints(enabled_tools, language=self.language)
        return ToolPromptComposer(language=self.language).format_list(
            hints,
            kb_name=self.kb_name or "",
        )

    async def _generate_payload(
        self,
        template: QuestionTemplate,
        user_topic: str,
        preference: str,
        history_context: str,
        knowledge_context: str,
        available_tools: str,
        previous_questions: str = "",
    ) -> dict[str, Any]:
        system_prompt = self.get_prompt("system", "") or ""
        user_prompt_template = self.get_prompt("generate", "") or (
            "Template: {template}\n"
            "User topic: {user_topic}\n"
            "Preference: {preference}\n"
            "Conversation context: {history_context}\n"
            "Previously generated questions (do not repeat):\n{previous_questions}\n"
            "Knowledge context: {knowledge_context}\n"
            "Enabled tools: {available_tools}\n\n"
            'Return JSON {{"question_type":"","question":"","options":{{}},'
            '"correct_answer":"","explanation":""}}'
        )
        template_dict = self._strip_template_knowledge_context(template)
        user_prompt = user_prompt_template.format(
            template=json.dumps(template_dict, ensure_ascii=False, indent=2),
            user_topic=user_topic,
            preference=preference or "(none)",
            history_context=history_context or "(none)",
            previous_questions=previous_questions or "(none)",
            knowledge_context=knowledge_context or "(none)",
            available_tools=available_tools,
        )
        chunks: list[str] = []
        async for chunk in self.stream_llm(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            response_format={"type": "json_object"},
            stage="generator_build_qa",
            trace_meta=build_trace_metadata(
                call_id=new_call_id(f"quiz-{template.question_id}"),
                phase="generation",
                label=f"Generate {template.question_id}",
                call_kind="llm_generation",
                trace_id=template.question_id,
                question_id=template.question_id,
            ),
        ):
            chunks.append(chunk)
        payload = self._parse_json_like("".join(chunks))
        payload.setdefault("question_type", template.question_type)
        payload.setdefault(
            "question",
            f"Based on {template.concentration}, answer this {template.difficulty} "
            f"{template.question_type} question.",
        )
        payload.setdefault("correct_answer", "N/A")
        payload.setdefault("explanation", "N/A")
        return payload

    async def _validate_and_repair_payload(
        self,
        template: QuestionTemplate,
        payload: dict[str, Any],
        user_topic: str,
        preference: str,
        history_context: str,
        knowledge_context: str,
        available_tools: str,
        previous_questions: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        expected_type = self._normalize_question_type(template.question_type)
        normalized = self._normalize_payload_shape(expected_type, payload)
        issues = self._collect_payload_issues(expected_type, normalized)
        repaired = False
        if issues:
            repaired_payload = await self._repair_payload(
                template=template,
                payload=normalized,
                issues=issues,
                user_topic=user_topic,
                preference=preference,
                history_context=history_context,
                knowledge_context=knowledge_context,
                available_tools=available_tools,
                previous_questions=previous_questions,
            )
            if repaired_payload:
                candidate = self._normalize_payload_shape(expected_type, repaired_payload)
                candidate_issues = self._collect_payload_issues(expected_type, candidate)
                if not candidate_issues or len(candidate_issues) <= len(issues):
                    normalized = candidate
                    issues = candidate_issues
                    repaired = True
        return normalized, {
            "requested_question_type": expected_type,
            "schema_ok": not issues,
            "repaired": repaired,
            "issues": issues,
        }

    async def _repair_payload(
        self,
        template: QuestionTemplate,
        payload: dict[str, Any],
        issues: list[str],
        user_topic: str,
        preference: str,
        history_context: str,
        knowledge_context: str,
        available_tools: str,
        previous_questions: str = "",
    ) -> dict[str, Any]:
        expected_type = self._normalize_question_type(template.question_type)
        repair_prompt = (
            "You are repairing an invalid quiz question JSON.\n\n"
            f"QuestionTemplate:\n{json.dumps(self._strip_template_knowledge_context(template), ensure_ascii=False, indent=2)}\n\n"
            f"User topic:\n{user_topic or '(none)'}\n\n"
            f"User preference:\n{preference or '(none)'}\n\n"
            f"Conversation context:\n{history_context or '(none)'}\n\n"
            f"Previously generated questions:\n{previous_questions or '(none)'}\n\n"
            f"Knowledge context:\n{knowledge_context or '(none)'}\n\n"
            f"Enabled tools:\n{available_tools}\n\n"
            f"Invalid payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"Detected issues:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
            f"Rewrite the payload so it strictly matches question_type='{expected_type}'. "
            "Return JSON only with keys: question_type, question, options, correct_answer, explanation."
        )
        chunks: list[str] = []
        async for chunk in self.stream_llm(
            user_prompt=repair_prompt,
            system_prompt="You fix malformed quiz payloads and return valid JSON only.",
            response_format={"type": "json_object"},
            stage="generator_repair_qa",
            trace_meta=build_trace_metadata(
                call_id=new_call_id(f"quiz-repair-{template.question_id}"),
                phase="generation",
                label=f"Repair question {self._humanize_question_id(template.question_id)} format",
                call_kind="llm_generation",
                trace_id=template.question_id,
                question_id=template.question_id,
            ),
        ):
            chunks.append(chunk)
        return self._parse_json_like("".join(chunks))

    @classmethod
    def _normalize_question_type(cls, question_type: str) -> str:
        normalized = str(question_type or "").strip().lower()
        aliases = {
            "multiple_choice": "choice",
            "multiple-choice": "choice",
            "mcq": "choice",
            "select": "choice",
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
        return normalized if normalized in {"choice", "true_false", "fill_blank", "written", "coding"} else "written"

    @classmethod
    def _normalize_payload_shape(cls, expected_type: str, payload: dict[str, Any]) -> dict[str, Any]:
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
            normalized["options"] = clean_options if clean_options else None
            if normalized["correct_answer"] and clean_options:
                answer_upper = normalized["correct_answer"].upper()
                if answer_upper in clean_options:
                    normalized["correct_answer"] = answer_upper
                else:
                    for key, value in clean_options.items():
                        if normalized["correct_answer"].strip().lower() == value.lower():
                            normalized["correct_answer"] = key
                            break
        elif expected_type == "true_false":
            normalized["options"] = {"True": "正确", "False": "错误"}
            normalized["correct_answer"] = cls._normalize_true_false_answer(normalized["correct_answer"])
        elif expected_type == "fill_blank":
            normalized["options"] = None
            if normalized["question"] and not cls._question_has_blank(normalized["question"]):
                normalized["question"] = f"{normalized['question']} ____"
        else:
            normalized["options"] = None
        return normalized

    @classmethod
    def _collect_payload_issues(cls, expected_type: str, payload: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        question = str(payload.get("question", "") or "")
        correct_answer = str(payload.get("correct_answer", "") or "").strip()
        options = payload.get("options")
        if expected_type == "choice":
            option_keys = set(options.keys()) if isinstance(options, dict) else set()
            if not option_keys:
                issues.append("choice_missing_options")
            elif option_keys != {"A", "B", "C", "D"}:
                issues.append("choice_options_must_be_a_to_d")
            if correct_answer.upper() not in {"A", "B", "C", "D"}:
                issues.append("choice_correct_answer_must_be_option_key")
        elif expected_type == "true_false":
            if correct_answer not in {"True", "False"}:
                issues.append("true_false_answer_must_be_true_or_false")
        elif expected_type == "fill_blank":
            if not cls._question_has_blank(question):
                issues.append("fill_blank_question_must_include_blank")
        elif cls._payload_looks_like_choice(
            question=question,
            correct_answer=correct_answer,
            options=options,
        ):
            issues.append("non_choice_payload_looks_like_multiple_choice")
        if not question:
            issues.append("missing_question")
        if not correct_answer:
            issues.append("missing_correct_answer")
        if not str(payload.get("explanation", "") or "").strip():
            issues.append("missing_explanation")
        return issues

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
        if re.search(r"(^|\n)\s*[A-D][\.\):]\s+", question):
            return True
        return correct_answer.upper() in {"A", "B", "C", "D"}

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
    def _humanize_question_id(question_id: str) -> str:
        match = re.fullmatch(r"q_(\d+)", str(question_id or "").strip().lower())
        if match:
            return f"question {match.group(1)}"
        return str(question_id or "question").strip() or "question"

    def _is_tool_enabled(self, tool_name: str) -> bool:
        aliases = {
            "rag": ["rag", "rag_tool"],
            "web_search": ["web_search"],
            "code_execution": ["code_execution", "write_code"],
        }
        keys = aliases.get(tool_name, [tool_name])
        present = [key for key in keys if key in self.tool_flags]
        return True if not present else any(bool(self.tool_flags.get(key)) for key in present)

    def _enabled_tool_names(self) -> list[str]:
        enabled_tools: list[str] = []
        if self._is_tool_enabled("rag"):
            enabled_tools.append("rag")
        if self._is_tool_enabled("web_search"):
            enabled_tools.append("web_search")
        if self._is_tool_enabled("code_execution"):
            enabled_tools.append("code_execution")
        return enabled_tools

    @staticmethod
    def _strip_template_knowledge_context(template: QuestionTemplate) -> dict[str, Any]:
        template_dict = template.__dict__.copy()
        if isinstance(template_dict.get("metadata"), dict):
            template_dict["metadata"] = {
                key: value
                for key, value in template_dict["metadata"].items()
                if key != "knowledge_context"
            }
        return template_dict

    @classmethod
    def _format_previous_questions(cls, questions: list[str] | None) -> str:
        if not questions:
            return ""
        capped = questions[-cls.MAX_PREVIOUS_QUESTIONS :]
        return "\n".join(f"{index}. {question}" for index, question in enumerate(capped, 1))

    @staticmethod
    def _parse_json_like(content: str) -> dict[str, Any]:
        if not content or not content.strip():
            return {}
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", content.strip())
        block_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
        if block_match:
            cleaned = block_match.group(1).strip()
        try:
            payload = json.loads(cleaned)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
        obj_match = re.search(r"\{[\s\S]*\}", cleaned)
        if obj_match:
            try:
                payload = json.loads(obj_match.group(0))
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}
        return {}


__all__ = ["Generator"]

