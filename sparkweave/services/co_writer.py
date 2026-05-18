"""NG-owned co-writer editing helpers and compatibility facades."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from threading import RLock
from typing import Any, AsyncGenerator
import uuid

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.logging import get_logger
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.llm import get_llm_config
from sparkweave.services.llm import stream as llm_stream
from sparkweave.services.paths import get_path_service
from sparkweave.tools import LangChainToolRegistry

logger = get_logger("CoWriterService")

_path_service = get_path_service()
HISTORY_FILE = _path_service.get_co_writer_history_file()
TOOL_CALLS_DIR = _path_service.get_co_writer_tool_calls_dir()
TOOL_CALLS_DIR.mkdir(parents=True, exist_ok=True)
_HISTORY_LOCK = RLock()


@dataclass
class ToolTrace:
    tool_name: str
    args: dict[str, Any]
    result: str
    success: bool = True
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def _load_history_unlocked() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def load_history() -> list[dict[str, Any]]:
    with _HISTORY_LOCK:
        return _load_history_unlocked()


def save_history(history: list[dict[str, Any]]) -> None:
    with _HISTORY_LOCK:
        _write_json_atomic(HISTORY_FILE, history)


def append_history(entry: dict[str, Any]) -> None:
    with _HISTORY_LOCK:
        history = _load_history_unlocked()
        history.append(entry)
        _write_json_atomic(HISTORY_FILE, history)


def save_tool_call(operation_id: str, kind: str, payload: dict[str, Any]) -> str:
    TOOL_CALLS_DIR.mkdir(parents=True, exist_ok=True)
    path = TOOL_CALLS_DIR / f"{operation_id}_{kind}.json"
    _write_json_atomic(path, payload)
    return str(path)


def print_stats() -> None:
    logger.debug("Co-writer token stats are provided by the NG LLM facade.")


class EditAgent:
    """Markdown editing agent using the NG LLM facade."""

    def __init__(self, language: str = "en") -> None:
        self.language = language
        self._config = None
        self.refresh_config()

    def refresh_config(self) -> None:
        try:
            self._config = get_llm_config()
        except Exception:
            self._config = None

    def get_model(self) -> str:
        return str(getattr(self._config, "model", "") or "")

    async def process(
        self,
        *,
        text: str,
        instruction: str,
        action: str = "rewrite",
        source: str | None = None,
        kb_name: str | None = None,
    ) -> dict[str, Any]:
        operation_id = self._operation_id()
        prompt = self._edit_prompt(
            text=text,
            instruction=instruction,
            action=action,
            source=source,
            kb_name=kb_name,
        )
        edited_text = await self._complete_or_fallback(prompt, text, action)
        self._append_history(
            {
                "id": operation_id,
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "source": source,
                "kb_name": kb_name,
                "input": {"text": text, "instruction": instruction},
                "output": {"edited_text": edited_text},
                "model": self.get_model(),
            }
        )
        return {"edited_text": edited_text, "operation_id": operation_id}

    async def auto_mark(self, *, text: str) -> dict[str, Any]:
        operation_id = self._operation_id()
        prompt = (
            "Add concise Markdown emphasis, headings, and bullet structure where helpful. "
            "Return only the marked-up text.\n\n"
            f"{text}"
        )
        marked_text = await self._complete_or_fallback(prompt, text, "automark")
        self._append_history(
            {
                "id": operation_id,
                "timestamp": datetime.now().isoformat(),
                "action": "automark",
                "input": {"text": text},
                "output": {"marked_text": marked_text},
                "model": self.get_model(),
            }
        )
        return {"marked_text": marked_text, "operation_id": operation_id}

    async def stream_llm(
        self,
        *,
        user_prompt: str,
        system_prompt: str,
        stage: str = "edit",
    ) -> AsyncGenerator[str, None]:
        try:
            async for chunk in llm_stream(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=getattr(self._config, "model", None),
                api_key=getattr(self._config, "api_key", None),
                base_url=getattr(self._config, "base_url", None),
                api_version=getattr(self._config, "api_version", None),
                binding=getattr(self._config, "binding", None),
                temperature=0.4,
            ):
                yield chunk
        except Exception as exc:
            logger.debug("Co-writer stream fallback at %s: %s", stage, exc)
            yield self._fallback_edit(user_prompt, "rewrite")

    async def _complete_or_fallback(self, prompt: str, original: str, action: str) -> str:
        try:
            result = await llm_complete(
                prompt=prompt,
                system_prompt="You are an expert Markdown editor. Return only the edited text.",
                model=getattr(self._config, "model", None),
                api_key=getattr(self._config, "api_key", None),
                base_url=getattr(self._config, "base_url", None),
                api_version=getattr(self._config, "api_version", None),
                binding=getattr(self._config, "binding", None),
                temperature=0.4,
            )
            return result.strip() or original
        except Exception as exc:
            logger.debug("Co-writer completion fallback: %s", exc)
            return self._fallback_edit(original, action)

    def _edit_prompt(
        self,
        *,
        text: str,
        instruction: str,
        action: str,
        source: str | None,
        kb_name: str | None,
    ) -> str:
        return (
            f"Action: {action}\n"
            f"Instruction: {instruction or '(none)'}\n"
            f"Source: {source or '(none)'}\n"
            f"Knowledge base: {kb_name or '(none)'}\n\n"
            "Text:\n"
            f"{text}\n\n"
            "Return only the edited Markdown text."
        )

    @staticmethod
    def _fallback_edit(text: str, action: str) -> str:
        cleaned = text.strip()
        if action == "shorten":
            words = cleaned.split()
            return " ".join(words[: max(1, min(len(words), 80))])
        if action == "expand":
            return cleaned + "\n\nAdditional detail: clarify the key idea and connect it to the context."
        if action == "automark":
            return cleaned if cleaned.startswith("#") else f"## Notes\n\n{cleaned}"
        return cleaned

    @staticmethod
    def _operation_id() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    @staticmethod
    def _append_history(entry: dict[str, Any]) -> None:
        append_history(entry)


class AgenticChatPipeline:
    """Small tool-use helper compatible with the legacy co-writer route."""

    def __init__(self, language: str = "en") -> None:
        self.language = language
        self.tool_registry = LangChainToolRegistry()

    def _normalize_enabled_tools(self, enabled_tools: list[str] | None) -> list[str]:
        known = set(self.tool_registry.names())
        normalized: list[str] = []
        for item in enabled_tools or []:
            name = str(item or "").strip()
            if name and name in known and name not in normalized:
                normalized.append(name)
        return normalized

    async def _stage_thinking(
        self,
        context: UnifiedContext,
        enabled_tools: list[str],
        stream: StreamBus,
    ) -> str:
        note = (
            "Use the selected text, user instruction, and any requested tools "
            "to produce a direct Markdown replacement."
        )
        await stream.thinking(note, source="co_writer_react_edit", stage="thinking")
        if enabled_tools:
            await stream.progress(
                f"Using tools: {', '.join(enabled_tools)}",
                source="co_writer_react_edit",
                stage="thinking",
            )
        return note

    async def _stage_acting(
        self,
        *,
        context: UnifiedContext,
        enabled_tools: list[str],
        thinking_text: str,
        stream: StreamBus,
    ) -> list[ToolTrace]:
        traces: list[ToolTrace] = []
        for tool_name in enabled_tools:
            args = self._tool_args(tool_name, context)
            await stream.tool_call(tool_name, args, source="co_writer_react_edit", stage="acting")
            try:
                result = await self.tool_registry.execute(tool_name, **args)
                trace = ToolTrace(
                    tool_name=tool_name,
                    args=args,
                    result=result.content,
                    success=result.success,
                    sources=result.sources,
                    metadata=result.metadata,
                )
            except Exception as exc:
                trace = ToolTrace(
                    tool_name=tool_name,
                    args=args,
                    result=str(exc),
                    success=False,
                    metadata={"error": str(exc), "thinking": thinking_text},
                )
            traces.append(trace)
            await stream.tool_result(
                tool_name,
                trace.result,
                source="co_writer_react_edit",
                stage="acting",
                metadata={"success": trace.success, "sources": trace.sources},
            )
        return traces

    def _format_tool_traces(self, traces: list[ToolTrace]) -> str:
        lines: list[str] = []
        for trace in traces:
            lines.append(f"Tool: {trace.tool_name}")
            lines.append(f"Success: {trace.success}")
            lines.append(f"Result: {trace.result}")
        return "\n".join(lines)

    @staticmethod
    def _tool_args(tool_name: str, context: UnifiedContext) -> dict[str, Any]:
        query = context.user_message
        if tool_name == "rag":
            return {"query": query, "kb_name": (context.knowledge_bases or [""])[0]}
        if tool_name == "web_search":
            return {"query": query}
        if tool_name == "paper_search":
            return {"query": query}
        if tool_name == "code_execution":
            return {"code": "", "intent": query}
        if tool_name == "reason":
            return {"query": query, "context": query}
        if tool_name == "brainstorm":
            return {"topic": query}
        return {"query": query}


def tool_traces_to_dicts(traces: list[ToolTrace]) -> list[dict[str, Any]]:
    return [asdict(trace) for trace in traces]


__all__ = [
    "AgenticChatPipeline",
    "EditAgent",
    "HISTORY_FILE",
    "TOOL_CALLS_DIR",
    "ToolTrace",
    "load_history",
    "print_stats",
    "save_history",
    "save_tool_call",
    "tool_traces_to_dicts",
]

