"""Built-in tool wrappers owned by the next-generation runtime."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any

from sparkweave.core.tool_protocol import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from sparkweave.services.prompting import load_prompt_hints

logger = logging.getLogger(__name__)


class _PromptHintsMixin:
    """Shared prompt-hint loader for NG built-in tools."""

    def get_prompt_hints(self, language: str = "en"):
        return load_prompt_hints(self.name, language=language)


class BrainstormTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="brainstorm",
            description="Broadly explore multiple possibilities for a topic and give a short rationale for each.",
            parameters=[
                ToolParameter(
                    name="topic",
                    type="string",
                    description="The topic, goal, or problem to brainstorm about.",
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Optional supporting context, constraints, or background.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.reasoning import brainstorm

        result = await brainstorm(
            topic=kwargs.get("topic", ""),
            context=kwargs.get("context", ""),
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
        )
        return ToolResult(content=result.get("answer", ""), metadata=result)


class RAGTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="rag",
            description=(
                "Search a knowledge base using Retrieval-Augmented Generation. "
                "Returns relevant passages, sources, and grounded context for the "
                "agent to synthesize."
            ),
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
                ToolParameter(
                    name="kb_name",
                    type="string",
                    description="Knowledge base to search.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.rag import rag_search

        query = kwargs.get("query", "")
        kb_name = kwargs.get("kb_name")
        event_sink = kwargs.get("event_sink")
        if not kb_name:
            return ToolResult(
                content=(
                    "RAG retrieval was requested, but no knowledge base is configured "
                    "for this turn."
                ),
                sources=[{"type": "rag", "query": query, "kb_name": kb_name}],
                metadata={"skipped": True, "reason": "no_kb_selected"},
                success=False,
            )
        extra_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in {"query", "kb_name", "event_sink"}
        }

        result = await rag_search(
            query=query,
            kb_name=kb_name,
            event_sink=event_sink,
            **extra_kwargs,
        )
        content = result.get("answer") or result.get("content", "")
        success = bool(result.get("success", True))
        sources = result.get("sources")
        if not isinstance(sources, list):
            sources = []
        sources = [source for source in sources if isinstance(source, dict)]
        if not sources:
            sources = [{"type": "rag", "query": query, "kb_name": kb_name}]
        return ToolResult(
            content=content,
            sources=sources,
            metadata=result,
            success=success,
        )


class WebSearchTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web and return summarised results with citations.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.search import web_search

        query = kwargs.get("query", "")
        output_dir = kwargs.get("output_dir")
        verbose = kwargs.get("verbose", False)
        result = await web_search(
            query=query,
            output_dir=output_dir,
            verbose=verbose,
        )

        if isinstance(result, dict):
            answer = result.get("answer", "")
            citations = result.get("citations", [])
        else:
            answer = str(result)
            citations = []

        return ToolResult(
            content=answer,
            sources=[
                {"type": "web", "url": citation.get("url", ""), "title": citation.get("title", "")}
                for citation in citations
            ],
            metadata=result if isinstance(result, dict) else {"raw": answer},
        )


class ExternalVideoSearchTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="external_video_search",
            description=(
                "Find and rank a concise set of public learning videos for the current learning task. "
                "Use this when the learner asks for recommended videos, video explanations, or short lessons from the web."
            ),
            parameters=[
                ToolParameter(
                    name="topic",
                    type="string",
                    description="The learning topic or question to search videos for.",
                ),
                ToolParameter(
                    name="prompt",
                    type="string",
                    description="Optional full learner request for better ranking context.",
                    required=False,
                ),
                ToolParameter(
                    name="language",
                    type="string",
                    description="Preferred result language. Use zh for Chinese learners unless asked otherwise.",
                    required=False,
                    enum=["zh", "en"],
                    default="zh",
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of video cards to return.",
                    required=False,
                    default=3,
                ),
                ToolParameter(
                    name="learner_hints",
                    type="object",
                    description="Optional learner profile hints used for ranking and explanations.",
                    required=False,
                    default={},
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.video_search import recommend_learning_videos

        topic = str(kwargs.get("topic") or kwargs.get("query") or kwargs.get("prompt") or "").strip()
        prompt = str(kwargs.get("prompt") or topic).strip()
        language = str(kwargs.get("language") or "zh").strip() or "zh"
        learner_hints = kwargs.get("learner_hints")
        if not isinstance(learner_hints, dict):
            learner_hints = {}
        try:
            max_results = int(kwargs.get("max_results") or 3)
        except (TypeError, ValueError):
            max_results = 3
        max_results = max(1, min(max_results, 6))

        if not topic:
            return ToolResult(
                content="请先告诉我要找哪一个学习主题的视频。",
                success=False,
                metadata={
                    "render_type": "external_video",
                    "videos": [],
                    "tool_name": "external_video_search",
                },
            )

        result = await recommend_learning_videos(
            topic=topic,
            learner_hints=learner_hints,
            prompt=prompt,
            language=language,
            max_results=max_results,
            event_sink=self._bridge_event_sink(kwargs.get("event_sink")),
        )
        metadata = dict(result)
        videos = metadata.get("videos") if isinstance(metadata.get("videos"), list) else []
        metadata["render_type"] = "external_video"
        metadata["tool_name"] = "external_video_search"
        metadata["agent_chain"] = []
        metadata["tool_chain"] = [
            {"label": "精选视频工具", "state": "done", "detail": "检索公开视频候选"},
            {"label": "排序筛选", "state": "done", "detail": "按学习任务和画像提示筛选"},
        ]

        response = str(metadata.get("response") or "").strip()
        if not response:
            response = "我为你筛选了几条适合当前任务的视频。"
        sources = [
            {
                "type": "external_video",
                "title": str(video.get("title") or "学习视频"),
                "url": str(video.get("url") or ""),
                "platform": str(video.get("platform") or ""),
            }
            for video in videos
            if isinstance(video, dict) and video.get("url")
        ]
        return ToolResult(
            content=response,
            success=bool(metadata.get("success", True)),
            metadata=metadata,
            sources=sources,
        )

    @staticmethod
    def _bridge_event_sink(raw_event_sink: Any) -> Any:
        if not callable(raw_event_sink):
            return None

        def _sink(event_type: str, payload: dict[str, Any]) -> None:
            message = str(payload.get("message") or payload.get("query") or "")
            result = raw_event_sink(event_type, message, payload)
            if inspect.isawaitable(result):
                try:
                    asyncio.create_task(result)
                except RuntimeError:
                    logger.debug("Skipped async video progress event outside a running loop.")

        return _sink


class CodeExecutionTool(_PromptHintsMixin, BaseTool):
    _CODEGEN_SYSTEM_PROMPT = """You are a Python code generator.

Convert the user's natural-language request into executable Python code only.

Rules:
- Output only Python code, with no markdown fences or explanation.
- Prefer standard library plus these common packages when useful: math, numpy, pandas, matplotlib, scipy, sympy.
- Print the final answer to stdout.
- Save plots or generated files to the current working directory.
- Keep the code focused on the requested computation or verification task.
"""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="code_execution",
            description="Turn a natural-language computation request into Python, run it in a restricted Python worker, and return the result.",
            parameters=[
                ToolParameter(
                    name="intent",
                    type="string",
                    description="Natural-language description of the computation or verification task.",
                ),
                ToolParameter(
                    name="code",
                    type="string",
                    description="Optional raw Python code to execute directly.",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Max execution time in seconds.",
                    required=False,
                    default=30,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.code_execution import run_python_code

        code = str(kwargs.get("code") or "").strip()
        intent = str(kwargs.get("intent") or kwargs.get("query") or "").strip()
        timeout = int(kwargs.get("timeout", 30) or 30)
        workspace_dir = kwargs.get("workspace_dir")
        feature = kwargs.get("feature")
        task_id = kwargs.get("task_id")
        session_id = kwargs.get("session_id")
        turn_id = kwargs.get("turn_id")

        if not code:
            if not intent:
                raise ValueError("code_execution requires either 'intent' or 'code'")
            code = await self._generate_code(intent)

        result = await run_python_code(
            code=code,
            timeout=timeout,
            workspace_dir=workspace_dir,
            feature=feature,
            task_id=task_id,
            session_id=session_id,
            turn_id=turn_id,
        )
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        exit_code = result.get("exit_code", 1)
        artifacts = result.get("artifacts", [])

        parts: list[str] = []
        if stdout:
            parts.append(stdout.strip())
        if stderr:
            label = "Error" if exit_code else "Stderr"
            parts.append(f"{label}:\n{stderr.strip()}")
        if artifacts:
            parts.append(f"Artifacts: {', '.join(str(item) for item in artifacts)}")
        if not parts:
            parts.append("Execution completed with no output.")

        metadata = {**result, "code": code, "intent": intent}
        return ToolResult(
            content="\n\n".join(parts),
            success=exit_code == 0,
            sources=[{"type": "code", "file": artifact} for artifact in artifacts],
            metadata=metadata,
        )

    async def _generate_code(self, intent: str) -> str:
        from sparkweave.services.llm import complete, get_llm_config, get_token_limit_kwargs

        llm_config = get_llm_config()
        completion_kwargs: dict[str, Any] = {"temperature": 0.0}
        if getattr(llm_config, "model", None):
            completion_kwargs.update(get_token_limit_kwargs(llm_config.model, 1200))

        response = await complete(
            prompt=intent,
            system_prompt=self._CODEGEN_SYSTEM_PROMPT,
            model=llm_config.model,
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            api_version=getattr(llm_config, "api_version", None),
            binding=getattr(llm_config, "binding", None),
            **completion_kwargs,
        )
        code = self._strip_markdown_fences(response)
        if not code.strip():
            raise ValueError("LLM returned empty code for code_execution")
        return code

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        cleaned = content.strip()
        if not cleaned.startswith("```"):
            return cleaned

        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()


class ReasonTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="reason",
            description=(
                "Perform deep reasoning on a complex sub-problem using a dedicated LLM call. "
                "Use when the current context is insufficient for a confident answer."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The sub-problem to reason about.",
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Supporting context for reasoning.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.reasoning import reason

        result = await reason(
            query=kwargs.get("query", ""),
            context=kwargs.get("context", ""),
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
        )
        return ToolResult(content=result.get("answer", ""), metadata=result)


class PaperSearchToolWrapper(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="paper_search",
            description="Search arXiv preprints by keyword and return concise metadata.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum papers to return.",
                    required=False,
                    default=3,
                ),
                ToolParameter(
                    name="years_limit",
                    type="integer",
                    description="Only include preprints from the last N years.",
                    required=False,
                    default=3,
                ),
                ToolParameter(
                    name="sort_by",
                    type="string",
                    description="Sort by relevance or submission date.",
                    required=False,
                    default="relevance",
                    enum=["relevance", "date"],
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.papers import search_arxiv_papers

        try:
            papers = await search_arxiv_papers(
                query=kwargs.get("query", ""),
                max_results=kwargs.get("max_results", 3),
                years_limit=kwargs.get("years_limit", 3),
                sort_by=kwargs.get("sort_by", "relevance"),
            )
        except Exception:
            return ToolResult(
                content="arXiv search is temporarily unavailable (rate-limited or network error). Please try again later.",
                sources=[],
                metadata={"provider": "arxiv", "papers": [], "error": True},
            )
        if not papers:
            return ToolResult(
                content="No arXiv preprints found for this query.",
                sources=[],
                metadata={"provider": "arxiv", "papers": []},
            )

        lines: list[str] = []
        for paper in papers:
            lines.append(f"**{paper['title']}** ({paper.get('year', '?')})")
            lines.append(f"Authors: {', '.join(paper.get('authors', []))}")
            lines.append(f"arXiv: {paper.get('arxiv_id', '')}")
            lines.append(f"URL: {paper.get('url', '')}")
            lines.append(f"Abstract: {paper.get('abstract', '')[:400]}")
            lines.append("")

        return ToolResult(
            content="\n".join(lines),
            sources=[
                {
                    "type": "paper",
                    "provider": "arxiv",
                    "url": paper.get("url", ""),
                    "title": paper.get("title", ""),
                    "arxiv_id": paper.get("arxiv_id", ""),
                }
                for paper in papers
            ],
            metadata={"provider": "arxiv", "papers": papers},
        )


class GeoGebraAnalysisTool(_PromptHintsMixin, BaseTool):
    """Analyze a math-problem image and generate GeoGebra commands."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="geogebra_analysis",
            description=(
                "Analyze a math problem image, detect geometric elements, "
                "and generate validated GeoGebra commands for visualization. "
                "Requires an attached image."
            ),
            parameters=[
                ToolParameter(
                    name="question",
                    type="string",
                    description="The math problem text to analyze.",
                ),
                ToolParameter(
                    name="image_base64",
                    type="string",
                    description="Base64-encoded image (data URI or raw). Injected from attachments when called via function-calling.",
                    required=False,
                    default="",
                ),
                ToolParameter(
                    name="language",
                    type="string",
                    description="Output language: 'zh' or 'en'.",
                    required=False,
                    default="zh",
                    enum=["zh", "en"],
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from sparkweave.services.vision import analyze_geogebra_image

        question = kwargs.get("question", "")
        image_base64 = kwargs.get("image_base64", "")
        language = kwargs.get("language", "zh")

        if not image_base64:
            return ToolResult(
                content="No image provided. This tool requires an image attachment.",
                success=False,
            )

        try:
            analysis_result = await analyze_geogebra_image(
                question=question,
                image_base64=image_base64,
                language=language,
            )
        except Exception as exc:
            logger.exception("GeoGebra analysis pipeline failed")
            return ToolResult(content=f"Analysis pipeline error: {exc}", success=False)

        result = analysis_result.get("result", {})
        if not result.get("has_image"):
            return ToolResult(content="No image was processed.", success=False)

        final_commands = result.get("final_ggb_commands", [])
        ggb_block = str(analysis_result.get("ggb_block") or "")

        analysis = result.get("analysis_output") or {}
        constraints = analysis.get("constraints", [])
        relations = analysis.get("geometric_relations", [])
        summary_parts: list[str] = []
        if constraints:
            summary_parts.append(
                f"Constraints ({len(constraints)}): {json.dumps(constraints[:5], ensure_ascii=False)}"
            )
        if relations:
            relation_descriptions = [
                relation.get("description", str(relation))
                if isinstance(relation, dict)
                else str(relation)
                for relation in relations[:5]
            ]
            summary_parts.append(
                f"Relations ({len(relations)}): {json.dumps(relation_descriptions, ensure_ascii=False)}"
            )

        content_parts: list[str] = []
        if summary_parts:
            content_parts.append("\n".join(summary_parts))
        content_parts.append(ggb_block or "(No GeoGebra commands generated.)")

        return ToolResult(
            content="\n\n".join(content_parts),
            metadata={
                "has_image": True,
                "commands_count": len(final_commands),
                "final_ggb_commands": final_commands,
                "image_is_reference": result.get("image_is_reference", False),
                "bbox_elements": len((result.get("bbox_output") or {}).get("elements", [])),
                "constraints_count": len(constraints),
                "relations_count": len(relations),
                "reflection_issues": len(
                    (result.get("reflection_output") or {}).get("issues_found", [])
                ),
            },
        )


BUILTIN_TOOL_TYPES: tuple[type[BaseTool], ...] = (
    BrainstormTool,
    RAGTool,
    WebSearchTool,
    ExternalVideoSearchTool,
    CodeExecutionTool,
    ReasonTool,
    PaperSearchToolWrapper,
    GeoGebraAnalysisTool,
)

BUILTIN_TOOL_NAMES: tuple[str, ...] = tuple(tool_type().name for tool_type in BUILTIN_TOOL_TYPES)

TOOL_ALIASES: dict[str, tuple[str, dict[str, Any]]] = {
    "rag_hybrid": ("rag", {"mode": "hybrid"}),
    "rag_naive": ("rag", {"mode": "naive"}),
    "rag_search": ("rag", {}),
    "code_execute": ("code_execution", {}),
    "run_code": ("code_execution", {}),
    "video_search": ("external_video_search", {}),
    "learning_video_search": ("external_video_search", {}),
    "curated_video_search": ("external_video_search", {}),
}


__all__ = [
    "BUILTIN_TOOL_NAMES",
    "BUILTIN_TOOL_TYPES",
    "TOOL_ALIASES",
    "BrainstormTool",
    "CodeExecutionTool",
    "ExternalVideoSearchTool",
    "GeoGebraAnalysisTool",
    "PaperSearchToolWrapper",
    "RAGTool",
    "ReasonTool",
    "WebSearchTool",
]

