"""Solve-specific wrapper over the NG tool registry."""

from __future__ import annotations

import os
from typing import Any

from sparkweave.core.tool_protocol import ToolResult
from sparkweave.services.prompting import ToolPromptComposer
from sparkweave.tools.registry import ToolRegistry, get_tool_registry

_CONTROL_ACTIONS = {
    "en": [
        {
            "name": "done",
            "when_to_use": "Use when the current step already has enough reliable evidence to move on.",
            "input_format": "Empty string.",
        },
        {
            "name": "replan",
            "when_to_use": "Use when the current plan is no longer appropriate.",
            "input_format": "A short reason describing why replanning is needed.",
        },
    ],
    "zh": [
        {
            "name": "done",
            "when_to_use": "Use when the current step already has enough reliable evidence to move on.",
            "input_format": "Empty string.",
        },
        {
            "name": "replan",
            "when_to_use": "Use when the current plan is no longer appropriate.",
            "input_format": "A short reason describing why replanning is needed.",
        },
    ],
}

_ACTION_INPUT_PARAM_CANDIDATES = ("query", "intent", "task", "prompt", "input", "code")


class SolveToolRuntime:
    """Solve-specific wrapper over the shared tool registry."""

    def __init__(
        self,
        enabled_tools: list[str] | None,
        language: str = "en",
        core_registry: ToolRegistry | Any | None = None,
    ) -> None:
        self.language = language
        self._core_registry = core_registry or get_tool_registry()
        self._tool_names: list[str] = []
        self._valid_actions: set[str] = {"done", "replan"}
        for name in enabled_tools or []:
            tool = self._core_registry.get(name)
            if tool is None:
                continue
            if tool.name not in self._tool_names:
                self._tool_names.append(tool.name)
            self._valid_actions.add(tool.name)
            self._valid_actions.add(name)
            for alias in tool.get_prompt_hints(language=self.language).aliases:
                if alias.name:
                    self._valid_actions.add(alias.name)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tool_names)

    @property
    def valid_actions(self) -> set[str]:
        return set(self._valid_actions)

    def has_tool(self, name: str) -> bool:
        tool = self._core_registry.get(name)
        return bool(tool and tool.name in self._tool_names)

    def resolve_tool_name(self, name: str) -> str | None:
        tool = self._core_registry.get(name)
        return tool.name if tool is not None else None

    def _build_prompt_text(self, names: list[str], format: str, **kwargs: Any) -> str:
        if hasattr(self._core_registry, "build_prompt_text"):
            return self._core_registry.build_prompt_text(
                names,
                format=format,
                language=self.language,
                **kwargs,
            )
        hints = self._core_registry.get_prompt_hints(names, language=self.language)
        composer = ToolPromptComposer(language=self.language)
        if format == "table":
            return composer.format_table(hints, control_actions=kwargs.get("control_actions"))
        if format == "aliases":
            return composer.format_aliases(hints)
        return composer.format_list(hints, kb_name=str(kwargs.get("kb_name") or ""))

    def build_planner_description(self, kb_name: str = "") -> str:
        return self._build_prompt_text(self._tool_names, "list", kb_name=kb_name)

    def build_solver_description(self) -> str:
        table = self._build_prompt_text(
            self._tool_names,
            "table",
            control_actions=_CONTROL_ACTIONS.get(self.language, _CONTROL_ACTIONS["en"]),
        )
        aliases = self._build_prompt_text(self._tool_names, "aliases")
        return "\n\n".join(part for part in (table, aliases) if part.strip())

    async def execute(
        self,
        action: str,
        action_input: str,
        *,
        kb_name: str | None = None,
        output_dir: str | None = None,
        reason_context: str = "",
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        event_sink: Any | None = None,
    ) -> ToolResult:
        tool = self._core_registry.get(action)
        if tool is None:
            raise KeyError(f"Unknown tool action: {action}")
        if tool.name not in self._tool_names:
            raise PermissionError(f"Tool action '{action}' is not enabled for solve.")
        if tool.name == "rag" and not kb_name:
            return ToolResult(
                content=(
                    "RAG retrieval was requested, but no knowledge base is configured "
                    "for this turn. Continue without retrieved knowledge or ask the user "
                    "to select a knowledge base."
                ),
                metadata={"skipped": True, "reason": "no_kb_selected"},
                success=False,
            )
        kwargs = self._build_action_input_kwargs(tool.name, action_input)
        kwargs = self._apply_runtime_context(
            tool_name=tool.name,
            kwargs=kwargs,
            kb_name=kb_name,
            output_dir=output_dir,
            reason_context=reason_context,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            event_sink=event_sink,
        )
        return await self._core_registry.execute(action, **kwargs)

    def _build_action_input_kwargs(self, tool_name: str, action_input: str) -> dict[str, Any]:
        tool = self._core_registry.get(tool_name)
        if tool is None:
            return {}
        definition = tool.get_definition()
        for candidate in _ACTION_INPUT_PARAM_CANDIDATES:
            for param in definition.parameters:
                if param.name == candidate:
                    return {candidate: action_input}
        return {}

    @staticmethod
    def _apply_runtime_context(
        *,
        tool_name: str,
        kwargs: dict[str, Any],
        kb_name: str | None,
        output_dir: str | None,
        reason_context: str,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        event_sink: Any | None,
    ) -> dict[str, Any]:
        if event_sink is not None:
            kwargs.setdefault("event_sink", event_sink)
        if tool_name == "rag" and kb_name:
            kwargs.setdefault("kb_name", kb_name)
        if tool_name == "web_search" and output_dir:
            kwargs.setdefault("output_dir", output_dir)
        if tool_name == "code_execution":
            kwargs.setdefault("timeout", 30)
            if output_dir:
                workspace_dir = os.path.join(output_dir, "code_runs")
                if "/" in output_dir and "\\" not in output_dir:
                    workspace_dir = workspace_dir.replace("\\", "/")
                kwargs.setdefault("workspace_dir", workspace_dir)
        if tool_name == "reason":
            if reason_context:
                kwargs.setdefault("context", reason_context)
            if api_key:
                kwargs.setdefault("api_key", api_key)
            if base_url:
                kwargs.setdefault("base_url", base_url)
            if model:
                kwargs.setdefault("model", model)
            if max_tokens is not None:
                kwargs.setdefault("max_tokens", max_tokens)
            if temperature is not None:
                kwargs.setdefault("temperature", temperature)
        return kwargs


__all__ = ["SolveToolRuntime"]

