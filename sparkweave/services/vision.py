"""Vision-analysis service for NG tools."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
from pathlib import Path
from typing import Any

from sparkweave.core.json import parse_json_response
from sparkweave.services.llm import get_llm_config
from sparkweave.services.llm import stream as llm_stream

logger = logging.getLogger(__name__)


def _empty_bbox_output() -> dict[str, Any]:
    return {"image_dimensions": {"width": 0, "height": 0}, "elements": []}


def _empty_analysis_output() -> dict[str, Any]:
    return {
        "image_reference_detected": False,
        "image_reference_keywords": [],
        "key_elements": {
            "points": [],
            "segments": [],
            "shapes": [],
            "circles": [],
            "special_points": [],
        },
        "constraints": [],
        "geometric_relations": [],
        "relative_position_analysis": [],
        "element_positions": {"relative_positions": [], "layout_description": ""},
        "annotations": [],
        "construction_steps": [],
    }


def _empty_ggbscript_output() -> dict[str, Any]:
    return {"commands": []}


def _empty_reflection_output() -> dict[str, Any]:
    return {
        "verification_results": [],
        "issues_found": [],
        "corrections": [],
        "final_verification": {
            "no_wrong_assumptions": False,
            "all_derived_points_use_commands": False,
            "all_use_bbox_points_use_coordinates": False,
            "all_constraints_satisfied": False,
            "layout_matches_original": False,
            "ready_for_rendering": False,
        },
        "corrected_commands": [],
    }


class VisionSolverAgent:
    """Analyze math problem images and generate GeoGebra visualizations."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        vision_model: str | None = None,
        language: str = "zh",
    ) -> None:
        config = get_llm_config()
        self.api_key = api_key if api_key is not None else getattr(config, "api_key", None)
        self.base_url = base_url or getattr(config, "base_url", None)
        self.model = model or getattr(config, "model", None)
        self.vision_model = vision_model or self.model
        self.api_version = getattr(config, "api_version", None)
        self.binding = getattr(config, "binding", None) or "openai"
        self.language = language
        self.prompt_templates = self._load_prompts()

    def _load_prompts(self) -> dict[str, str]:
        prompts_dir = Path(__file__).parent / "vision_prompts"
        templates: dict[str, str] = {}
        for prompt_name in ["bbox", "analysis", "ggbscript", "reflection", "tutor"]:
            prompt_file = prompts_dir / f"{prompt_name}.md"
            templates[prompt_name] = (
                prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""
            )
        return templates

    def _render_prompt(self, template_name: str, context: dict[str, Any]) -> str:
        template = self.prompt_templates.get(template_name, "")
        for key, value in context.items():
            placeholder = "{{ " + key + " }}"
            if isinstance(value, (dict, list)):
                replacement = str(value)
            else:
                replacement = str(value)
            template = template.replace(placeholder, replacement)
        return template

    async def _call_vision_llm(
        self,
        prompt: str,
        image_base64: str,
        temperature: float = 0.3,
    ) -> str:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_base64}},
                ],
            }
        ]
        chunks: list[str] = []
        async for chunk in llm_stream(
            prompt="",
            system_prompt="",
            messages=messages,
            temperature=temperature,
            model=self.vision_model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            binding=self.binding,
        ):
            chunks.append(chunk)
        return "".join(chunks)

    @staticmethod
    def _parse_json(response: str) -> dict[str, Any]:
        parsed = parse_json_response(response, logger_instance=logger, fallback={})
        return parsed if isinstance(parsed, dict) else {}

    async def _process_bbox(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            prompt = self._render_prompt("bbox", {"question_text": state["question_text"]})
            return self._parse_json(
                await self._call_vision_llm(prompt, state["image_base64"], temperature=0.3)
            ) or _empty_bbox_output()
        except Exception:
            logger.exception("BBox stage failed")
            return _empty_bbox_output()

    async def _process_analysis(self, state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        try:
            prompt = self._render_prompt(
                "analysis",
                {
                    "question_text": state["question_text"],
                    "bbox_output_json": state["bbox_output"],
                },
            )
            output = self._parse_json(
                await self._call_vision_llm(prompt, state["image_base64"], temperature=0.3)
            ) or _empty_analysis_output()
            return output, bool(output.get("image_reference_detected", False))
        except Exception:
            logger.exception("Analysis stage failed")
            return _empty_analysis_output(), False

    async def _process_ggbscript(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            prompt = self._render_prompt(
                "ggbscript",
                {
                    "question_text": state["question_text"],
                    "bbox_output_json": state["bbox_output"],
                    "analysis_output_json": state["analysis_output"],
                },
            )
            return self._parse_json(
                await self._call_vision_llm(prompt, state["image_base64"], temperature=0.3)
            ) or _empty_ggbscript_output()
        except Exception:
            logger.exception("GGBScript stage failed")
            return _empty_ggbscript_output()

    async def _process_reflection(self, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        try:
            prompt = self._render_prompt(
                "reflection",
                {
                    "question_text": state["question_text"],
                    "bbox_output_json": state["bbox_output"],
                    "analysis_output_json": state["analysis_output"],
                    "ggbscript_output_json": state["ggbscript_output"],
                },
            )
            output = self._parse_json(
                await self._call_vision_llm(prompt, state["image_base64"], temperature=0.3)
            ) or _empty_reflection_output()
            final_commands = output.get("corrected_commands") or state["ggbscript_output"].get(
                "commands",
                [],
            )
            return output, final_commands
        except Exception:
            logger.exception("Reflection stage failed")
            return _empty_reflection_output(), state["ggbscript_output"].get("commands", [])

    async def process(
        self,
        question_text: str,
        image_base64: str | None = None,
        session_id: str = "default",
    ) -> dict[str, Any]:
        if not image_base64:
            return {"has_image": False, "final_ggb_commands": []}

        state: dict[str, Any] = {
            "session_id": session_id,
            "question_text": question_text,
            "image_base64": image_base64,
            "has_image": True,
        }
        state["bbox_output"] = await self._process_bbox(state)
        state["analysis_output"], state["image_is_reference"] = await self._process_analysis(state)
        state["ggbscript_output"] = await self._process_ggbscript(state)
        state["reflection_output"], state["final_ggb_commands"] = await self._process_reflection(
            state
        )
        return {
            "has_image": True,
            "bbox_output": state["bbox_output"],
            "analysis_output": state["analysis_output"],
            "ggbscript_output": state["ggbscript_output"],
            "reflection_output": state["reflection_output"],
            "final_ggb_commands": state["final_ggb_commands"],
            "image_is_reference": state["image_is_reference"],
        }

    async def stream_process(
        self,
        question_text: str,
        image_base64: str | None = None,
        session_id: str = "default",
    ) -> AsyncGenerator[dict[str, Any], None]:
        result = await self.process(
            question_text=question_text,
            image_base64=image_base64,
            session_id=session_id,
        )
        if not result.get("has_image"):
            yield {"event": "no_image", "data": {}}
            return
        yield {"event": "analysis_complete", "data": result}

    async def stream_tutor_response(
        self,
        question_text: str,
        final_ggb_commands: list[dict[str, Any]],
        analysis_output: dict[str, Any] | None = None,
        session_id: str = "default",
    ) -> AsyncGenerator[str, None]:
        """Stream a tutor answer grounded in the image-analysis result."""
        logger.info("[%s] Starting tutor response stream", session_id)

        ggb_commands_str = self._format_ggb_commands(final_ggb_commands)
        constraints_count = 0
        image_is_reference = False
        if analysis_output:
            constraints = analysis_output.get("constraints", [])
            constraints_count = len(constraints) if isinstance(constraints, list) else 0
            image_is_reference = bool(analysis_output.get("image_reference_detected", False))

        tutor_prompt = self._render_prompt(
            "tutor",
            {
                "question_text": question_text,
                "ggb_commands": ggb_commands_str,
                "elements_count": len(final_ggb_commands),
                "constraints_count": constraints_count,
                "image_is_reference": "yes" if image_is_reference else "no",
            },
        )
        system_prompt = (
            "你是一位专业的数学教师，善于结合可视化过程讲解数学题。"
            if self.language == "zh"
            else "You are a professional math tutor who explains with visual reasoning."
        )

        try:
            async for chunk in llm_stream(
                prompt=tutor_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                api_version=self.api_version,
                binding=self.binding,
            ):
                yield chunk
        except Exception as exc:
            logger.exception("[%s] Tutor response error", session_id)
            yield f"\n\n抱歉，解题过程生成出错：{exc}"

    async def stream_process_with_tutor(
        self,
        question_text: str,
        image_base64: str | None = None,
        session_id: str = "default",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream the full image-analysis pipeline and the tutor answer."""
        if not image_base64:
            yield {"event": "no_image", "data": {}}
            yield {"event": "answer_start", "data": {"has_image_analysis": False}}
            async for chunk in self.stream_tutor_response(
                question_text=question_text,
                final_ggb_commands=[],
                analysis_output=None,
                session_id=session_id,
            ):
                yield {"event": "text", "data": {"content": chunk}}
            yield {"event": "done", "data": {}}
            return

        state: dict[str, Any] = {
            "session_id": session_id,
            "question_text": question_text,
            "image_base64": image_base64,
            "has_image": True,
        }
        yield {"event": "analysis_start", "data": {"session_id": session_id}}

        state["bbox_output"] = await self._process_bbox(state)
        elements = state["bbox_output"].get("elements", [])
        yield {
            "event": "bbox_complete",
            "data": {
                "stage": "bbox",
                "elements_count": len(elements) if isinstance(elements, list) else 0,
                "elements": [
                    {"type": item.get("type", "unknown"), "label": item.get("label", "")}
                    for item in elements[:10]
                    if isinstance(item, dict)
                ]
                if isinstance(elements, list)
                else [],
            },
        }

        state["analysis_output"], state["image_is_reference"] = await self._process_analysis(state)
        constraints = state["analysis_output"].get("constraints", [])
        relations = state["analysis_output"].get("geometric_relations", [])
        yield {
            "event": "analysis_complete",
            "data": {
                "stage": "analysis",
                "constraints_count": len(constraints) if isinstance(constraints, list) else 0,
                "relations_count": len(relations) if isinstance(relations, list) else 0,
                "image_is_reference": state["image_is_reference"],
                "constraints": constraints[:10] if isinstance(constraints, list) else [],
            },
        }

        state["ggbscript_output"] = await self._process_ggbscript(state)
        commands = state["ggbscript_output"].get("commands", [])
        yield {
            "event": "ggbscript_complete",
            "data": {
                "stage": "ggbscript",
                "commands_count": len(commands) if isinstance(commands, list) else 0,
                "commands": [
                    {
                        "command": command.get("command", ""),
                        "description": command.get("description", ""),
                    }
                    for command in commands[:10]
                    if isinstance(command, dict)
                ]
                if isinstance(commands, list)
                else [],
            },
        }

        state["reflection_output"], state["final_ggb_commands"] = await self._process_reflection(
            state
        )
        issues = state["reflection_output"].get("issues_found", [])
        yield {
            "event": "reflection_complete",
            "data": {
                "stage": "reflection",
                "issues_count": len(issues) if isinstance(issues, list) else 0,
                "commands_count": len(state["final_ggb_commands"]),
                "final_commands": state["final_ggb_commands"],
            },
        }

        ggb_script_content = self._format_ggb_commands(state["final_ggb_commands"])
        yield {
            "event": "analysis_message_complete",
            "data": {
                "ggb_block": {
                    "page_id": "image-analysis-restore",
                    "title": "题目配图还原",
                    "content": ggb_script_content,
                }
                if ggb_script_content
                else None,
                "analysis_summary": {
                    "constraints": constraints[:10] if isinstance(constraints, list) else [],
                    "relations": [
                        relation.get("description", str(relation))
                        if isinstance(relation, dict)
                        else str(relation)
                        for relation in relations[:10]
                    ]
                    if isinstance(relations, list)
                    else [],
                },
            },
        }

        yield {"event": "answer_start", "data": {"has_image_analysis": True}}
        async for chunk in self.stream_tutor_response(
            question_text=question_text,
            final_ggb_commands=state["final_ggb_commands"],
            analysis_output=state["analysis_output"],
            session_id=session_id,
        ):
            yield {"event": "text", "data": {"content": chunk}}
        yield {"event": "done", "data": {}}

    def _format_ggb_commands(self, commands: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for command_item in commands:
            if isinstance(command_item, dict):
                description = str(command_item.get("description", "") or "")
                command = str(command_item.get("command", "") or "")
                if description:
                    lines.append(f"# {description}")
                if command:
                    lines.append(command)
            else:
                lines.append(str(command_item))
        return "\n".join(lines)

    def format_ggb_block(
        self,
        commands: list[dict[str, Any]],
        page_id: str = "main",
        title: str = "Problem Figure",
    ) -> str:
        content = self._format_ggb_commands(commands)
        if not content:
            return ""
        return f"```ggbscript[{page_id};{title}]\n{content}\n```"


async def analyze_geogebra_image(
    *,
    question: str,
    image_base64: str,
    language: str = "zh",
) -> dict[str, Any]:
    llm_config = get_llm_config()
    agent = VisionSolverAgent(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        language=language,
    )
    result = await agent.process(question_text=question, image_base64=image_base64)
    return {
        "result": result,
        "ggb_block": agent.format_ggb_block(result.get("final_ggb_commands", [])),
    }


__all__ = ["VisionSolverAgent", "analyze_geogebra_image"]

