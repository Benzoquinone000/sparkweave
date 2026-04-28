"""Notebook record summarization service owned by ``sparkweave``."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sparkweave.services.context import clean_thinking_tags
from sparkweave.services.llm import get_llm_config, get_token_limit_kwargs
from sparkweave.services.llm import stream as llm_stream


def _clip_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


class NotebookSummarizeAgent:
    """Generate concise summaries for notebook records."""

    def __init__(self, language: str = "en") -> None:
        self.language = "zh" if str(language or "en").lower().startswith("zh") else "en"
        self.llm_config = get_llm_config()
        self.model = getattr(self.llm_config, "model", None)
        self.api_key = getattr(self.llm_config, "api_key", None)
        self.base_url = getattr(self.llm_config, "base_url", None)
        self.api_version = getattr(self.llm_config, "api_version", None)
        self.binding = getattr(self.llm_config, "binding", None) or "openai"
        self.extra_headers = getattr(self.llm_config, "extra_headers", None) or {}

    async def summarize(
        self,
        *,
        title: str,
        record_type: str,
        user_query: str,
        output: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        chunks: list[str] = []
        async for chunk in self.stream_summary(
            title=title,
            record_type=record_type,
            user_query=user_query,
            output=output,
            metadata=metadata,
        ):
            if chunk:
                chunks.append(chunk)
        return clean_thinking_tags("".join(chunks)).strip()

    async def stream_summary(
        self,
        *,
        title: str,
        record_type: str,
        user_query: str,
        output: str,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        prompt = self._build_user_prompt(
            title=title,
            record_type=record_type,
            user_query=user_query,
            output=output,
            metadata=metadata or {},
        )
        kwargs: dict[str, Any] = {"temperature": 0.2}
        if self.model:
            kwargs.update(get_token_limit_kwargs(self.model, 300))
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers

        async for chunk in llm_stream(
            prompt=prompt,
            system_prompt=self._system_prompt(),
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            binding=self.binding,
            **kwargs,
        ):
            if chunk:
                yield chunk

    def _system_prompt(self) -> str:
        if self.language == "zh":
            return (
                "You are SparkWeave's notebook summary agent. "
                "Write a concise Chinese summary for future retrieval and reuse. "
                "Focus on topic, key conclusions, use cases, and why the record matters. "
                "Output only the summary text."
            )
        return (
            "You are SparkWeave's notebook summary agent. "
            "Compress a saved record into a concise, retrieval-friendly summary for future reuse. "
            "Focus on topic, key conclusions, use cases, and why this record matters. "
            "Output only the summary text with no heading or bullets."
        )

    def _build_user_prompt(
        self,
        *,
        title: str,
        record_type: str,
        user_query: str,
        output: str,
        metadata: dict[str, Any],
    ) -> str:
        clipped_query = _clip_text(user_query, 1200) or "(empty)"
        clipped_output = _clip_text(output, 6000) or "(empty)"
        clipped_metadata = _clip_text(str(metadata or {}), 1000)
        record_hint = self._record_hint(record_type)
        if self.language == "zh":
            return (
                f"Record type: {record_type}\n"
                f"Type hint: {record_hint}\n"
                f"Title: {title or '(untitled)'}\n"
                f"User input:\n{clipped_query}\n\n"
                f"Saved content:\n{clipped_output}\n\n"
                f"Metadata: {clipped_metadata or '(none)'}\n\n"
                "Write an 80-180 character Chinese summary. Mention the knowledge topic, "
                "key information, completion state, and reusable value."
            )
        return (
            f"Record type: {record_type}\n"
            f"Type hint: {record_hint}\n"
            f"Title: {title or '(untitled)'}\n"
            f"User input:\n{clipped_query}\n\n"
            f"Saved content:\n{clipped_output}\n\n"
            f"Metadata: {clipped_metadata or '(none)'}\n\n"
            "Write an 80-180 word summary. Focus on the topic, key information, "
            "current completion state, and what makes this record useful for future reuse."
        )

    def _record_hint(self, record_type: str) -> str:
        hints = {
            "chat": "A full chat transcript; focus on the question, conclusion, and next actions.",
            "co_writer": (
                "A writing draft; focus on theme, structure, current completeness, "
                "and expansion paths."
            ),
            "guided_learning": (
                "A guided learning record; focus on topic, knowledge structure, "
                "and partial/final output."
            ),
        }
        return hints.get(record_type, "Summarize the most reusable information in this record.")


__all__ = ["NotebookSummarizeAgent"]

