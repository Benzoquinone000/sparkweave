"""Research topic decomposition agent for NG."""

from __future__ import annotations

from typing import Any

from sparkweave.agents.base_agent import BaseAgent
from sparkweave.core.json import parse_json_response
from sparkweave.tools import get_tool_registry


class DecomposeAgent(BaseAgent):
    """Topic decomposition agent used by NG research workflows."""

    _MODE_TO_STYLE = {
        "notes": "study_notes",
        "report": "report",
        "comparison": "comparison",
        "learning_path": "learning_path",
    }

    def __init__(
        self,
        config: dict[str, Any],
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        kb_name: str | None = None,
    ) -> None:
        language = config.get("system", {}).get("language", "zh")
        super().__init__(
            module_name="research",
            agent_name="decompose_agent",
            api_key=api_key,
            base_url=base_url,
            api_version=api_version,
            language=language,
            config=config,
        )
        rag_cfg = config.get("rag", {}) or {}
        self.kb_name = rag_cfg.get("kb_name") or kb_name or None
        self.enable_rag = bool(config.get("researching", {}).get("enable_rag", True))
        if not self.kb_name:
            self.enable_rag = False
        self.conversation_history: list[dict[str, Any]] = config.get("conversation_history", [])
        self.citation_manager: Any | None = None

        intent_mode = str(config.get("intent", {}).get("mode", "") or "")
        reporting_style = str(config.get("reporting", {}).get("style", "") or "")
        self._research_style = reporting_style or self._MODE_TO_STYLE.get(intent_mode, "report")

    def set_citation_manager(self, citation_manager: Any) -> None:
        """Attach a citation manager for compatibility with the legacy pipeline."""
        self.citation_manager = citation_manager

    async def process(
        self,
        topic: str,
        num_subtopics: int = 5,
        mode: str = "manual",
    ) -> dict[str, Any]:
        """Decompose a research topic into subtopics.

        The return shape intentionally matches the legacy agent contract so
        direct callers can move to ``sparkweave`` without adapting their
        downstream code.
        """
        normalized_mode = "auto" if str(mode).lower() == "auto" else "manual"
        limit = max(1, int(num_subtopics or 1))

        rag_context = ""
        source_query = ""
        if self.enable_rag:
            rag_context, source_query = await self._retrieve_background_knowledge(topic)

        sub_topics = await self._generate_sub_topics(
            topic=topic,
            num_subtopics=limit,
            mode=normalized_mode,
            rag_context=rag_context,
        )

        used_rag = bool(rag_context)
        return {
            "main_topic": topic,
            "sub_queries": [source_query] if source_query and used_rag else [],
            "rag_context": rag_context,
            "sub_topics": sub_topics,
            "total_subtopics": len(sub_topics),
            "mode": normalized_mode if used_rag else f"{normalized_mode}_no_rag",
            "rag_context_summary": (
                "RAG background based on topic"
                if used_rag
                else "RAG disabled or unavailable - subtopics generated directly from LLM"
            ),
        }

    async def _retrieve_background_knowledge(self, topic: str) -> tuple[str, str]:
        """Retrieve lightweight background context from the NG RAG tool."""
        source_query = (topic or "").strip()
        if not source_query or not self.kb_name:
            return "", source_query
        try:
            result = await get_tool_registry().execute(
                "rag",
                query=source_query,
                kb_name=self.kb_name,
            )
        except Exception as exc:
            self.logger.warning("Research decomposition RAG retrieval failed: %s", exc)
            return "", source_query
        return (result.content or "").strip(), source_query

    async def _generate_sub_topics(
        self,
        topic: str,
        num_subtopics: int,
        mode: str,
        rag_context: str = "",
    ) -> list[dict[str, str]]:
        system_prompt = self.get_prompt(
            "system",
            "role",
            "You are a research planning expert. Decompose topics into clear subtopics.",
        )
        system_prompt = f"{system_prompt or ''}{self._format_conversation_context()}"

        prompt_key = "decompose" if rag_context else "decompose_without_rag"
        template = self.get_prompt("process", prompt_key)
        if not template:
            template = self._fallback_decompose_template(with_rag=bool(rag_context))

        user_prompt = template.format(
            topic=topic,
            rag_context=rag_context,
            decompose_requirement=self._build_decompose_requirement(num_subtopics, mode),
            mode_instruction=self._get_mode_contract("decompose"),
        )

        response = await self.call_llm(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            response_format={"type": "json_object"},
        )
        return self._parse_sub_topics(response, limit=num_subtopics)

    def _format_conversation_context(self) -> str:
        if not self.conversation_history:
            return ""
        parts: list[str] = []
        for message in self.conversation_history:
            role = str(message.get("role", "user") or "user")
            content = str(message.get("content", "") or "").strip()
            if content:
                parts.append(f"[{role}]: {content}")
        if not parts:
            return ""
        return (
            "\n<conversation_history>\n"
            "Use this conversation history when the current request refers to earlier context.\n\n"
            + "\n\n".join(parts)
            + "\n</conversation_history>\n"
        )

    def _get_mode_contract(self, stage: str) -> str:
        return (
            self.get_prompt("mode_contracts", f"{self._research_style}_{stage}", "")
            or ""
        ).strip()

    @staticmethod
    def _build_decompose_requirement(num_subtopics: int, mode: str) -> str:
        if mode == "auto":
            return (
                "Quantity Requirements:\n"
                f"Generate between 3 and {num_subtopics} subtopics based on topic complexity. "
                f"Never exceed {num_subtopics} subtopics. Prioritize distinct, important aspects."
            )
        return (
            "Quantity Requirements:\n"
            f"Generate exactly {num_subtopics} subtopics. Avoid overlap and cover the topic fully."
        )

    @staticmethod
    def _fallback_decompose_template(*, with_rag: bool) -> str:
        rag_block = "Background Knowledge:\n{rag_context}\n\n" if with_rag else ""
        return (
            "Decompose this research topic into clear subtopics. Only output JSON.\n\n"
            "Main Topic: {topic}\n\n"
            f"{rag_block}"
            "{decompose_requirement}\n\n"
            "Mode-Specific Focus:\n{mode_instruction}\n\n"
            'Output JSON: {{"sub_topics": [{{"title": "...", "overview": "..."}}]}}'
        )

    def _parse_sub_topics(self, response: str, limit: int) -> list[dict[str, str]]:
        payload = parse_json_response(response, logger_instance=self.logger, fallback={})
        if not isinstance(payload, dict):
            return []
        raw_topics = payload.get("sub_topics") or payload.get("subtopics") or []
        if not isinstance(raw_topics, list):
            return []

        cleaned: list[dict[str, str]] = []
        for item in raw_topics:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or "").strip()
            overview = str(
                item.get("overview") or item.get("description") or item.get("summary") or ""
            ).strip()
            if not title and not overview:
                continue
            cleaned.append({"title": title, "overview": overview})
            if len(cleaned) >= limit:
                break
        return cleaned



__all__ = ["DecomposeAgent"]

