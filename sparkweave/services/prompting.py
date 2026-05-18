"""Prompt hint loading and rendering helpers for tools."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

from sparkweave.core.tool_protocol import ToolAlias, ToolPromptHints

ToolHintEntry = tuple[str, ToolPromptHints]

_GUIDELINE_HEADER = {
    "en": (
        "**Autonomously decide which tool to use** based on the current sub-goal "
        "and the evidence gathered so far. Consider all available options:"
    ),
    "zh": (
        "**根据当前子目标和已收集的证据，自主决定使用哪个工具**。"
        "请综合考虑所有可用选项："
    ),
}

_PHASE_LABELS = {
    "en": {
        "exploration": "Phase 1: Exploration",
        "expansion": "Phase 2: Expansion",
        "synthesis": "Phase 3: Synthesis",
        "verification": "Phase 4: Verification",
        "other": "Other Tools",
    },
    "zh": {
        "exploration": "阶段 1：基础探索",
        "expansion": "阶段 2：扩展补充",
        "synthesis": "阶段 3：综合推理",
        "verification": "阶段 4：验证核查",
        "other": "其他工具",
    },
}

_PHASE_ORDER = ["exploration", "expansion", "synthesis", "verification", "other"]


class PromptManager:
    """Load and cache NG-owned agent prompt YAML files."""

    _instance: "PromptManager | None" = None
    _cache: dict[str, dict[str, Any]] = {}

    LANGUAGE_FALLBACKS = {
        "zh": ["zh", "cn", "en"],
        "en": ["en", "zh", "cn"],
    }

    def __new__(cls) -> "PromptManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_prompts(
        self,
        module_name: str,
        agent_name: str,
        language: str = "zh",
        subdirectory: str | None = None,
    ) -> dict[str, Any]:
        lang_code = _normalize_language(language)
        if lang_code not in self.LANGUAGE_FALLBACKS:
            lang_code = "en"
        cache_key = self._build_cache_key(module_name, agent_name, lang_code, subdirectory)
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompts = self._load_with_fallback(module_name, agent_name, lang_code, subdirectory)
        self._cache[cache_key] = prompts
        return prompts

    def reload_prompts(
        self,
        module_name: str,
        agent_name: str,
        language: str = "zh",
        subdirectory: str | None = None,
    ) -> dict[str, Any]:
        lang_code = _normalize_language(language)
        if lang_code not in self.LANGUAGE_FALLBACKS:
            lang_code = "en"
        cache_key = self._build_cache_key(module_name, agent_name, lang_code, subdirectory)
        self._cache.pop(cache_key, None)
        return self.load_prompts(module_name, agent_name, lang_code, subdirectory)

    def clear_cache(self, module_name: str | None = None) -> None:
        if module_name is None:
            self._cache.clear()
            return
        for key in [key for key in self._cache if key.startswith(f"{module_name}_")]:
            del self._cache[key]

    def get_prompt(
        self,
        prompts: dict[str, Any],
        section: str,
        field: str | None = None,
        fallback: str = "",
    ) -> str:
        if section not in prompts:
            return fallback
        value = prompts[section]
        if field is None:
            return value if isinstance(value, str) else fallback
        if isinstance(value, dict):
            result = value.get(field)
            return result if isinstance(result, str) else fallback
        return fallback

    @staticmethod
    def _build_cache_key(
        module_name: str,
        agent_name: str,
        lang_code: str,
        subdirectory: str | None,
    ) -> str:
        subdir_part = f"_{subdirectory}" if subdirectory else ""
        return f"{module_name}_{agent_name}_{lang_code}{subdir_part}"

    def _load_with_fallback(
        self,
        module_name: str,
        agent_name: str,
        lang_code: str,
        subdirectory: str | None,
    ) -> dict[str, Any]:
        fallback_chain = self.LANGUAGE_FALLBACKS.get(lang_code, ["en"])
        for prompt_root in self._candidate_prompt_dirs(module_name):
            for lang in fallback_chain:
                prompt_path = self._resolve_prompt_path(
                    prompt_root,
                    lang,
                    agent_name,
                    subdirectory,
                )
                if prompt_path is None:
                    continue
                try:
                    with open(prompt_path, encoding="utf-8") as file:
                        loaded = yaml.safe_load(file) or {}
                    return loaded if isinstance(loaded, dict) else {}
                except Exception:
                    continue
        return {}

    @staticmethod
    def _candidate_prompt_dirs(module_name: str) -> list[Path]:
        base = Path(__file__).parent / "prompts"
        return [base / module_name]

    @staticmethod
    def _resolve_prompt_path(
        prompts_dir: Path,
        lang: str,
        agent_name: str,
        subdirectory: str | None,
    ) -> Path | None:
        lang_dir = prompts_dir / lang
        if not lang_dir.exists():
            return None
        if subdirectory:
            direct = lang_dir / subdirectory / f"{agent_name}.yaml"
            if direct.exists():
                return direct
        direct = lang_dir / f"{agent_name}.yaml"
        if direct.exists():
            return direct
        found = list(lang_dir.rglob(f"{agent_name}.yaml"))
        return found[0] if found else None


_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Return the shared NG prompt manager."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


def _normalize_language(language: str) -> str:
    normalized = language.lower()
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("en"):
        return "en"
    return normalized


def load_prompt_hints(tool_name: str, language: str = "en") -> ToolPromptHints:
    """Load per-tool prompt hints from YAML with zh/en fallback."""
    normalized_language = _normalize_language(language)
    base_dir = Path(__file__).parent / "prompt_hints"
    candidates = [base_dir / normalized_language / f"{tool_name}.yaml"]
    if normalized_language != "en":
        candidates.append(base_dir / "en" / f"{tool_name}.yaml")

    for path in candidates:
        if not path.is_file():
            continue
        with open(path, encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        aliases = [
            ToolAlias(
                name=str(item.get("name", "")).strip(),
                description=str(item.get("description", "")).strip(),
                input_format=str(item.get("input_format", "")).strip(),
                when_to_use=str(item.get("when_to_use", "")).strip(),
                phase=str(item.get("phase", "")).strip(),
            )
            for item in data.get("aliases", [])
            if str(item.get("name", "")).strip()
        ]
        return ToolPromptHints(
            short_description=str(data.get("short_description", "")).strip(),
            when_to_use=str(data.get("when_to_use", "")).strip(),
            input_format=str(data.get("input_format", "")).strip(),
            guideline=str(data.get("guideline", "")).strip(),
            note=str(data.get("note", "")).strip(),
            phase=str(data.get("phase", "")).strip(),
            aliases=aliases,
        )

    return ToolPromptHints()


class ToolPromptComposer:
    """Render prompt metadata into reusable prompt fragments."""

    def __init__(self, language: str = "en") -> None:
        self.language = _normalize_language(language)

    def format_list(self, hints: list[ToolHintEntry], kb_name: str = "") -> str:
        lines: list[str] = []
        for name, hint in hints:
            description = self._apply_kb_name(hint.short_description, kb_name)
            if description:
                lines.append(f"- {name}: {description}")
        return "\n".join(lines)

    def format_table(
        self,
        hints: list[ToolHintEntry],
        control_actions: list[dict[str, str]] | None = None,
    ) -> str:
        parts: list[str] = []
        table_lines = [
            "| action | When to use | action_input |",
            "|--------|------------|--------------|",
        ]
        for name, hint in hints:
            if hint.when_to_use or hint.input_format:
                table_lines.append(
                    f"| `{name}` | {hint.when_to_use} | {hint.input_format} |"
                )
        for control in control_actions or []:
            table_lines.append(
                f"| `{control['name']}` | {control['when_to_use']} | {control['input_format']} |"
            )
        parts.append("\n".join(table_lines))

        guidelines = [
            f"  - `{name}` {hint.guideline}"
            for name, hint in hints
            if hint.guideline
        ]
        if guidelines:
            header = _GUIDELINE_HEADER.get(self.language, _GUIDELINE_HEADER["en"])
            parts.append(f"{header}\n" + "\n".join(guidelines))

        notes = [f"- {hint.note}" for _, hint in hints if hint.note]
        if notes:
            parts.append("\n".join(notes))

        return "\n\n".join(parts)

    def format_aliases(self, hints: list[ToolHintEntry]) -> str:
        lines: list[str] = []
        for name, hint in hints:
            if hint.aliases:
                for alias in hint.aliases:
                    description = alias.description or hint.short_description
                    input_format = alias.input_format or hint.input_format or "Natural language"
                    lines.append(
                        f"- {alias.name}: {description} | Query format: {input_format}"
                    )
                continue
            if hint.short_description:
                lines.append(
                    f"- {name}: {hint.short_description} | Query format: {hint.input_format or 'Natural language'}"
                )
        return "\n".join(lines)

    def format_phased(self, hints: list[ToolHintEntry]) -> str:
        grouped: OrderedDict[str, list[str]] = OrderedDict(
            (phase, []) for phase in _PHASE_ORDER
        )
        for name, hint in hints:
            phase = hint.phase or "other"
            grouped.setdefault(phase, [])
            if hint.aliases:
                for alias in hint.aliases:
                    alias_phase = alias.phase or phase
                    grouped.setdefault(alias_phase, [])
                    alias_text = (
                        alias.when_to_use
                        or alias.description
                        or hint.guideline
                        or hint.short_description
                    )
                    if alias_text:
                        grouped[alias_phase].append(f"- `{alias.name}`: {alias_text}")
                continue
            if hint.guideline:
                grouped[phase].append(f"- `{name}`: {hint.guideline}")
            elif hint.short_description:
                grouped[phase].append(f"- `{name}`: {hint.short_description}")

        labels = _PHASE_LABELS.get(self.language, _PHASE_LABELS["en"])
        sections: list[str] = []
        for phase in _PHASE_ORDER:
            items = grouped.get(phase) or []
            if not items:
                continue
            label = labels.get(phase, labels["other"])
            sections.append(f"**{label}**\n" + "\n".join(items))
        return "\n\n".join(sections)

    @staticmethod
    def _apply_kb_name(text: str, kb_name: str) -> str:
        if not kb_name or not text:
            return text
        updated = text.replace("the uploaded knowledge base", f'the knowledge base "{kb_name}"')
        return updated.replace("已上传知识库", f'知识库 "{kb_name}"')


__all__ = [
    "PromptManager",
    "ToolPromptComposer",
    "get_prompt_manager",
    "load_prompt_hints",
]

