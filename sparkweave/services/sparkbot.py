"""NG-owned SparkBot manager with the legacy API surface."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import sys
import time
from typing import Any, Awaitable, Callable, Literal
import uuid
import zipfile

import yaml

from sparkweave.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.paths import get_path_service
from sparkweave.services.sparkbot_support.channel_manager import SparkBotChannelManager
from sparkweave.services.sparkbot_support.channels import (
    DISCORD_API_BASE,
    DISCORD_MAX_ATTACHMENT_BYTES,
    DISCORD_MAX_MESSAGE_LEN,
    TELEGRAM_MAX_MESSAGE_LEN,
    TELEGRAM_REPLY_CONTEXT_MAX_LEN,
    DingTalkChannel,
    DiscordChannel,
    EmailChannel,
    FeishuChannel,
    MatrixChannel,
    MochatChannel,
    QQChannel,
    SlackChannel,
    SparkBotChannel,
    TelegramChannel,
    WecomChannel,
    WhatsAppChannel,
    _channel_config_model,
    _sparkbot_media_dir,
    discover_builtin_channels,
)
from sparkweave.services.sparkbot_support.config_models import (
    COMPETITION_DEMO_BOT_ID,
    BotConfig,
    ChannelConfigModel,
    ChannelsConfig,
    DingTalkConfig,
    DiscordConfig,
    EmailConfig,
    FeishuConfig,
    MatrixConfig,
    MochatConfig,
    MochatGroupRule,
    MochatMentionConfig,
    QQConfig,
    SlackConfig,
    SlackDMConfig,
    SparkBotAgentConfig,
    SparkBotHeartbeatConfig,
    SparkBotMCPServerConfig,
    SparkBotToolsConfig,
    TelegramConfig,
    WebConfig,
    WecomConfig,
    WhatsAppConfig,
    _is_secret_field,
    build_competition_demo_bot_config,
    mask_channel_secrets,
)
from sparkweave.services.sparkbot_support.cron import (
    SparkBotCronJob,
    SparkBotCronJobState,
    SparkBotCronPayload,
    SparkBotCronSchedule,
    SparkBotCronService,
    SparkBotCronStore,
)
from sparkweave.services.sparkbot_support.defaults import (
    COMPETITION_DEMO_WORKSPACE_FILES as _COMPETITION_DEMO_WORKSPACE_FILES,
)
from sparkweave.services.sparkbot_support.defaults import (
    DEFAULT_SOULS as _DEFAULT_SOULS,
)
from sparkweave.services.sparkbot_support.defaults import (
    DEFAULT_TEMPLATES as _DEFAULT_TEMPLATES,
)
from sparkweave.services.sparkbot_support.heartbeat import SparkBotHeartbeatService
from sparkweave.services.sparkbot_support.messages import (
    SparkBotInboundMessage,
    SparkBotMessageBus,
    SparkBotOutboundMessage,
)
from sparkweave.services.sparkbot_support.team_models import (
    TEAM_FINISHED_STATUSES as _TEAM_FINISHED_STATUSES,
)
from sparkweave.services.sparkbot_support.team_models import (
    SparkBotTeamMail,
    SparkBotTeamMember,
    SparkBotTeamRuntime,
    SparkBotTeamState,
    SparkBotTeamTask,
)
from sparkweave.services.sparkbot_support.team_models import (
    team_timestamp as _team_timestamp,
)
from sparkweave.sparkbot.mcp import connect_mcp_servers
from sparkweave.sparkbot.media import build_image_content_blocks
from sparkweave.sparkbot.tools import build_sparkbot_agent_tool_registry
from sparkweave.tools.registry import ToolRegistry, get_tool_registry
from sparkweave.utils.json_parser import extract_json_from_text

logger = logging.getLogger(__name__)

_EDITABLE_WORKSPACE_FILES = (
    "SOUL.md",
    "USER.md",
    "TOOLS.md",
    "AGENTS.md",
    "HEARTBEAT.md",
    "NOTES.md",
    "COURSE.md",
    "LESSONS.md",
    "QUESTION_BANK.md",
    "RUBRIC.md",
    "RESOURCES.md",
)
MAX_SPARKBOT_WORKSPACE_FILE_CHARS = 200_000
MAX_SPARKBOT_SKILL_TEXT_CHARS = 200_000
MAX_SPARKBOT_SKILL_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SPARKBOT_SKILL_ZIP_FILES = 80
MAX_SPARKBOT_SKILL_ZIP_FILE_BYTES = 2 * 1024 * 1024
MAX_SPARKBOT_SKILL_ZIP_TOTAL_BYTES = 10 * 1024 * 1024
_RESERVED_BOT_DIRS = {"souls", "_souls", "workspace", "media", "cron", "logs", "sessions"}
_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parents[1] / "sparkbot" / "skills"
_PROMPT_FILE_MAX_CHARS = 12_000


ExchangeRecorder = Callable[[str, str, str, str], None]
ProgressCallback = Callable[[str], Awaitable[None]]


def _read_text_limited(path: Path, max_chars: int = _PROMPT_FILE_MAX_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


class SparkBotSkillsLoader:
    """Load workspace and NG built-in SparkBot skills."""

    def __init__(
        self,
        workspace: Path,
        *,
        builtin_skills_dir: Path | None = _BUILTIN_SKILLS_DIR,
    ) -> None:
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir

    def list_skills(self, *, filter_unavailable: bool = True) -> list[dict[str, str]]:
        skills: list[dict[str, str]] = []
        for source, root in (
            ("workspace", self.workspace_skills),
            ("builtin", self.builtin_skills),
        ):
            if root is None or not root.exists():
                continue
            for skill_dir in sorted(root.iterdir(), key=lambda p: p.name):
                skill_file = skill_dir / "SKILL.md"
                if not skill_dir.is_dir() or not skill_file.exists():
                    continue
                if any(item["name"] == skill_dir.name for item in skills):
                    continue
                item = {
                    "name": skill_dir.name,
                    "path": str(skill_file),
                    "source": source,
                }
                if not filter_unavailable or self._check_requirements(
                    self.get_skill_metadata(skill_dir.name) or {}
                ):
                    skills.append(item)
        return skills

    def load_skill(self, name: str) -> str | None:
        for root in (self.workspace_skills, self.builtin_skills):
            if root is None:
                continue
            skill_file = root / name / "SKILL.md"
            if skill_file.exists():
                return _read_text_limited(skill_file)
        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        parts: list[str] = []
        for name in skill_names:
            content = self.load_skill(name)
            if not content:
                continue
            parts.append(f"### Skill: {name}\n\n{self._strip_frontmatter(content)}")
        return "\n\n---\n\n".join(parts)

    def build_skills_summary(self) -> str:
        skills = self.list_skills(filter_unavailable=False)
        if not skills:
            return ""

        def escape_xml(text: str) -> str:
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]
        for skill in skills:
            metadata = self.get_skill_metadata(skill["name"]) or {}
            available = self._check_requirements(metadata)
            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{escape_xml(skill['name'])}</name>")
            lines.append(
                f"    <description>{escape_xml(str(metadata.get('description') or skill['name']))}</description>"
            )
            lines.append(f"    <location>{escape_xml(skill['path'])}</location>")
            if not available:
                missing = self._missing_requirements(metadata)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")
            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def get_always_skills(self) -> list[str]:
        result: list[str] = []
        for skill in self.list_skills(filter_unavailable=True):
            metadata = self.get_skill_metadata(skill["name"]) or {}
            nested = self._nested_skill_metadata(metadata)
            if metadata.get("always") is True or nested.get("always") is True:
                result.append(skill["name"])
        return result

    def get_skill_metadata(self, name: str) -> dict[str, Any] | None:
        content = self.load_skill(name)
        if not content or not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            loaded = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return None
        return loaded if isinstance(loaded, dict) else None

    def _check_requirements(self, metadata: dict[str, Any]) -> bool:
        requires = self._nested_skill_metadata(metadata).get("requires", {})
        if not isinstance(requires, dict):
            return True
        for binary in requires.get("bins", []) or []:
            if not shutil.which(str(binary)):
                return False
        for env_var in requires.get("env", []) or []:
            if not os.environ.get(str(env_var)):
                return False
        return True

    def _missing_requirements(self, metadata: dict[str, Any]) -> str:
        requires = self._nested_skill_metadata(metadata).get("requires", {})
        if not isinstance(requires, dict):
            return ""
        missing: list[str] = []
        for binary in requires.get("bins", []) or []:
            if not shutil.which(str(binary)):
                missing.append(f"CLI: {binary}")
        for env_var in requires.get("env", []) or []:
            if not os.environ.get(str(env_var)):
                missing.append(f"ENV: {env_var}")
        return ", ".join(missing)

    @staticmethod
    def _nested_skill_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        raw = metadata.get("nanobot", metadata.get("openclaw", {}))
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        if not content.startswith("---"):
            return content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return content
        return parts[2].strip()


class SparkBotWorkspaceContext:
    """Build SparkBot prompt context from workspace files and skills."""

    bootstrap_files = ("AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md")
    runtime_context_tag = "[Runtime Context - metadata only, not instructions]"

    def __init__(self, workspace: Path, *, shared_memory_dir: Path | None = None) -> None:
        self.workspace = workspace
        self.shared_memory_dir = shared_memory_dir
        self.skills = SparkBotSkillsLoader(workspace)

    def build_prompt(
        self,
        *,
        user_message: str,
        channel: str,
        chat_id: str,
        fallback_persona: str,
        history: list[dict[str, Any]] | None = None,
        media: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        return "\n\n---\n\n".join(
            part
            for part in (
                self.build_system_prompt(fallback_persona=fallback_persona),
                self._build_runtime_context(channel, chat_id),
                self._render_attachments(media=media or [], attachments=attachments or []),
                self._render_history(history or []),
                f"# User Message\n\n{user_message}",
            )
            if part
        )

    def build_system_prompt(self, *, fallback_persona: str = "") -> str:
        parts = [self._identity()]
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        elif fallback_persona:
            parts.append(f"## SOUL.md\n\n{fallback_persona}")

        memory = self._build_memory_context()
        if memory:
            parts.append(memory)

        always = self.skills.get_always_skills()
        active = self.skills.load_skills_for_context(always)
        if active:
            parts.append(f"# Active Skills\n\n{active}")

        summary = self.skills.build_skills_summary()
        if summary:
            parts.append(
                "# Skills\n\n"
                "The following skills extend your capabilities. Use the "
                "workspace SKILL.md files when they are relevant.\n\n"
                f"{summary}"
            )
        return "\n\n---\n\n".join(parts)

    def _identity(self) -> str:
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = (
            f"{'macOS' if system == 'Darwin' else system} "
            f"{platform.machine()}, Python {platform.python_version()}"
        )
        return (
            "# SparkBot\n\n"
            "You are SparkBot, a helpful learning companion powered by SparkWeave.\n\n"
            f"## Runtime\n{runtime}\n\n"
            f"## Workspace\nYour workspace is at: {workspace_path}\n"
            f"- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md\n\n"
            "## Guidelines\n"
            "- Use the workspace files as durable user and agent context.\n"
            "- Prefer clear, actionable teaching steps.\n"
            "- Ask for clarification when the request is ambiguous."
        )

    def _load_bootstrap_files(self) -> str:
        parts: list[str] = []
        for filename in self.bootstrap_files:
            content = _read_text_limited(self.workspace / filename)
            if content:
                parts.append(f"## {filename}\n\n{content}")
        return "\n\n".join(parts)

    def _build_memory_context(self) -> str:
        parts: list[str] = []
        if self.shared_memory_dir is not None:
            profile = _read_text_limited(self.shared_memory_dir / "PROFILE.md")
            summary = _read_text_limited(self.shared_memory_dir / "SUMMARY.md")
            if profile:
                parts.append(f"## User Profile\n\n{profile}")
            if summary:
                parts.append(f"## Learning Context\n\n{summary}")

        bot_memory_dir = self.workspace / "memory"
        long_term = _read_text_limited(bot_memory_dir / "MEMORY.md")
        history = _read_text_limited(bot_memory_dir / "HISTORY.md")
        if long_term:
            parts.append(f"## Bot Long-term Memory\n\n{long_term}")
        if history:
            parts.append(f"## Bot Memory History\n\n{history}")
        return "# Memory\n\n" + "\n\n".join(parts) if parts else ""

    @staticmethod
    def _render_history(history: list[dict[str, Any]]) -> str:
        if not history:
            return ""
        lines = ["# Recent Conversation"]
        for item in history:
            role = str(item.get("role") or "").lower()
            if role not in {"user", "assistant"}:
                continue
            label = "User" if role == "user" else "SparkBot"
            content = item.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            content = content.strip()
            if content:
                lines.append(f"{label}: {content}")
        return "\n\n".join(lines) if len(lines) > 1 else ""

    @staticmethod
    def _render_attachments(
        *,
        media: list[str],
        attachments: list[dict[str, Any]],
    ) -> str:
        if not media and not attachments:
            return ""
        lines = ["# Attachments"]
        seen: set[str] = set()
        for ref in media:
            ref_text = str(ref).strip()
            if not ref_text or ref_text in seen:
                continue
            seen.add(ref_text)
            lines.append(f"- media: {ref_text}")
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            ref = (
                attachment.get("path")
                or attachment.get("file_path")
                or attachment.get("filePath")
                or attachment.get("url")
                or attachment.get("uri")
                or attachment.get("file")
                or ""
            )
            ref_text = str(ref).strip()
            if ref_text in seen:
                continue
            seen.add(ref_text)
            kind = str(attachment.get("type") or attachment.get("mime_type") or "attachment")
            name = str(attachment.get("name") or attachment.get("filename") or "").strip()
            label = f"{kind}: {ref_text}" if ref_text else kind
            if name:
                label = f"{label} ({name})"
            lines.append(f"- {label}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def _build_runtime_context(self, channel: str, chat_id: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        return (
            f"# Runtime Context\n\n{self.runtime_context_tag}\n"
            f"Current Time: {now} ({tz})\n"
            f"Channel: {channel}\n"
            f"Chat ID: {chat_id}"
        )


@dataclass(slots=True)
class SparkBotSideTaskRecord:
    id: str
    instruction: str
    label: str
    origin_channel: str
    origin_chat_id: str
    session_key: str
    status: Literal["running", "ok", "error", "cancelled"] = "running"
    result: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None


class SparkBotSideTaskManager:
    """Run lightweight background side tasks and report results through the bus."""

    def __init__(
        self,
        *,
        bus: SparkBotMessageBus,
        context: SparkBotWorkspaceContext,
        fallback_persona: str,
        model: str | None = None,
    ) -> None:
        self.bus = bus
        self.context = context
        self.fallback_persona = fallback_persona
        self.model = model
        self.records: dict[str, SparkBotSideTaskRecord] = {}
        self._running: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}

    async def spawn(
        self,
        *,
        instruction: str,
        label: str = "btw",
        origin_channel: str = "web",
        origin_chat_id: str = "web",
        session_key: str,
    ) -> str:
        task_id = str(uuid.uuid4())[:8]
        record = SparkBotSideTaskRecord(
            id=task_id,
            instruction=instruction,
            label=label,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
            session_key=session_key,
        )
        self.records[task_id] = record
        task = asyncio.create_task(
            self._run(record),
            name=f"SparkBot:side:{task_id}",
        )
        self._running[task_id] = task
        self._session_tasks.setdefault(session_key, set()).add(task_id)
        task.add_done_callback(lambda done, rid=task_id: self._cleanup(rid, done))
        if label == "btw":
            return f"BTW accepted (id: {task_id}). I'll send the result when it finishes."
        return f"Task accepted (id: {task_id}). I'll notify you when it completes."

    async def cancel_by_session(self, session_key: str) -> int:
        task_ids = list(self._session_tasks.get(session_key, set()))
        cancelled = 0
        for task_id in task_ids:
            task = self._running.get(task_id)
            if task is not None and not task.done():
                task.cancel()
                cancelled += 1
        if cancelled:
            await asyncio.gather(
                *[task for task_id in task_ids if (task := self._running.get(task_id)) is not None],
                return_exceptions=True,
            )
        return cancelled

    async def stop_all(self) -> None:
        for task in list(self._running.values()):
            if not task.done():
                task.cancel()
        if self._running:
            await asyncio.gather(*self._running.values(), return_exceptions=True)

    def status_text(self) -> str:
        if not self.records:
            return "No side tasks."
        lines: list[str] = []
        for record in sorted(self.records.values(), key=lambda item: item.created_at):
            lines.append(
                f"- {record.label} {record.id}: {record.status} - {record.instruction[:80]}"
            )
        return "Side tasks:\n" + "\n".join(lines)

    async def _run(self, record: SparkBotSideTaskRecord) -> None:
        try:
            prompt = self.context.build_prompt(
                user_message=(
                    "Background side task. Complete this task independently and "
                    "return a concise result for the user.\n\n"
                    f"Task: {record.instruction}"
                ),
                channel=record.origin_channel,
                chat_id=record.origin_chat_id,
                fallback_persona=self.fallback_persona,
            )
            result = await llm_complete(prompt=prompt, model=self.model)
            record.status = "ok"
            record.result = result
            await self.bus.publish_outbound(
                SparkBotOutboundMessage(
                    channel=record.origin_channel,
                    chat_id=record.origin_chat_id,
                    content=f"BTW result ({record.id}):\n{result}",
                    metadata={"side_task_id": record.id, "side_task_label": record.label},
                )
            )
        except asyncio.CancelledError:
            record.status = "cancelled"
            record.error = "cancelled"
            raise
        except Exception as exc:
            record.status = "error"
            record.error = str(exc)
            await self.bus.publish_outbound(
                SparkBotOutboundMessage(
                    channel=record.origin_channel,
                    chat_id=record.origin_chat_id,
                    content=f"BTW failed ({record.id}): {exc}",
                    metadata={"side_task_id": record.id, "side_task_label": record.label},
                )
            )
        finally:
            record.completed_at = datetime.now().isoformat()

    def _cleanup(self, task_id: str, _task: asyncio.Task[None]) -> None:
        self._running.pop(task_id, None)
        record = self.records.get(task_id)
        if record is None:
            return
        task_ids = self._session_tasks.get(record.session_key)
        if task_ids is not None:
            task_ids.discard(task_id)
            if not task_ids:
                self._session_tasks.pop(record.session_key, None)


class SparkBotTeamManager:
    """Persistent NG nano-team command/state and worker layer."""

    def __init__(
        self,
        workspace: Path,
        *,
        bus: SparkBotMessageBus | None = None,
        model: str | None = None,
        worker_max_iterations: int = 12,
        max_workers: int = 5,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        auto_start_workers: bool = True,
        tool_registry: ToolRegistry | None = None,
        auto_plan_tools: bool = True,
        max_planned_tool_calls: int = 2,
    ) -> None:
        self.workspace = workspace
        self.bus = bus
        self.model = model
        self.worker_max_iterations = worker_max_iterations
        self.max_workers = max(1, int(max_workers or 5))
        self.temperature = float(temperature if temperature is not None else 0.1)
        self.max_tokens = max(1, int(max_tokens or 4096))
        self.reasoning_effort = str(reasoning_effort).strip() if reasoning_effort else None
        self.auto_start_workers = auto_start_workers
        self.tool_registry = tool_registry
        self.auto_plan_tools = auto_plan_tools
        self.max_planned_tool_calls = max(0, max_planned_tool_calls)
        self.teams_dir = workspace / "teams"
        self.teams_dir.mkdir(parents=True, exist_ok=True)
        self._active_by_session: dict[str, SparkBotTeamRuntime] = {}
        self._runtime_lock = asyncio.Lock()

    def _llm_kwargs(
        self,
        model: str | None,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max(1, int(max_tokens or self.max_tokens)),
            "temperature": self.temperature if temperature is None else temperature,
        }
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        return kwargs

    def is_active(self, session_key: str) -> bool:
        runtime = self._runtime(session_key, auto_attach=False)
        return runtime is not None and runtime.state.status not in _TEAM_FINISHED_STATUSES

    def has_unfinished_run(self, session_key: str) -> bool:
        if self.is_active(session_key):
            return True
        return self._latest_unfinished_dir(session_key) is not None

    def has_pending_approval(self, session_key: str) -> bool:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return False
        return any(task.status == "awaiting_approval" for task in self._load_tasks(runtime))

    def get_team_dir(self, session_key: str) -> Path | None:
        runtime = self._runtime(session_key, auto_attach=False)
        return runtime.run_dir if runtime is not None else None

    def get_team_state(self, session_key: str) -> SparkBotTeamState | None:
        runtime = self._runtime(session_key, auto_attach=False)
        return runtime.state if runtime is not None else None

    async def start_or_route_goal(self, session_key: str, goal: str) -> str:
        goal = goal.strip()
        if not goal:
            return "Please provide a team goal."
        async with self._runtime_lock:
            runtime = self._runtime(session_key, auto_attach=True)
            if runtime is not None:
                return self._route_instruction(runtime, goal)

            plan = self._fallback_plan(goal)
            runtime = self._create_runtime_from_plan(session_key, plan)
            self._active_by_session[session_key] = runtime
            self._append_event(runtime, "team_started", f"Started nano team for goal: {goal}")
            self._ensure_workers(runtime)
            return (
                f"Nano team started: `{runtime.state.team_id}` "
                f"({len(runtime.state.members)} workers).\n"
                "Use `/team status`, `/team log`, `/team stop`."
            )

    async def stop_mode(self, session_key: str, *, with_snapshot: bool = False) -> str:
        async with self._runtime_lock:
            runtime = self._runtime(session_key, auto_attach=False)
            if runtime is None:
                return "No active team."
            await self._cancel_worker_tasks(runtime)
            tasks = self._load_tasks(runtime)
            completed = bool(tasks) and all(task.status == "completed" for task in tasks)
            runtime.state.status = "completed" if completed else "stopped"
            runtime.state.updated_at = _team_timestamp()
            for member in runtime.state.members:
                member.status = "stopped"
            self._save_state(runtime)
            self._append_event(
                runtime,
                "team_stopped",
                f"Stopped team with status {runtime.state.status}",
            )
            self._active_by_session.pop(session_key, None)
            if not with_snapshot:
                return f"Team `{runtime.state.team_id}` stopped."
            return self._snapshot_text(runtime)

    async def cancel_by_session(self, session_key: str) -> int:
        async with self._runtime_lock:
            runtime = self._runtime(session_key, auto_attach=False)
            if runtime is None:
                return 0
            runtime.state.status = "stopped"
            runtime.state.updated_at = _team_timestamp()
            for member in runtime.state.members:
                member.status = "stopped"
            await self._cancel_worker_tasks(runtime)
            self._save_state(runtime)
            self._append_event(runtime, "team_cancelled", "Cancelled team runtime")
            self._active_by_session.pop(session_key, None)
            return 1

    def status_text(self, session_key: str) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "No active nano team. Start with `/team <goal>`."
        tasks = self._load_tasks(runtime)
        completed = sum(1 for task in tasks if task.status == "completed")
        active = sum(1 for task in tasks if task.status in {"planning", "in_progress"})
        pending_approval = [task for task in tasks if task.status == "awaiting_approval"]
        member_text = (
            ", ".join(f"{member.name}={member.status}" for member in runtime.state.members)
            or "none"
        )
        lines = [
            f"Team `{runtime.state.team_id}` - {runtime.state.status}",
            f"Mission: {runtime.state.mission or '(none)'}",
            f"Members: {member_text}",
            (
                f"Tasks: {completed}/{len(tasks)} completed - "
                f"{active} active - {len(pending_approval)} awaiting approval"
            ),
        ]
        if pending_approval:
            approvals = ", ".join(task.id for task in pending_approval[:5])
            lines.append(f"Approval queue: {approvals}")
            lines.append("Approve with `/team approve <id>` or `/team reject <id> <reason>`.")
        recent = self._recent_updates(runtime, n=1)
        if recent:
            lines.append(f"Recent: {recent[-1]}")
        return "\n".join(lines)

    def log_text(self, session_key: str, n: int = 20) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None or not runtime.events_path.exists():
            return "No team logs."
        rendered: list[str] = []
        for line in runtime.events_path.read_text(encoding="utf-8").splitlines()[-n:]:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            rendered.append(
                f"- [{event.get('ts', '?')}] "
                f"{event.get('kind', 'event')}: {event.get('message', '')}"
            )
        return "\n".join(rendered) or "No team logs."

    async def create(
        self,
        session_key: str,
        team_id: str,
        members: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        notes: str = "",
        *,
        mission: str = "",
    ) -> str:
        async with self._runtime_lock:
            if self._runtime(session_key, auto_attach=False) is not None:
                return "Error: active team already exists for this session"
            plan = {
                "mission": mission or team_id,
                "members": members,
                "tasks": tasks,
                "notes": notes,
            }
            runtime = self._create_runtime_from_plan(session_key, plan, team_id=team_id)
            self._active_by_session[session_key] = runtime
            self._append_event(runtime, "team_created", "Created team via internal API")
            self._ensure_workers(runtime)
            return f"Team '{runtime.state.team_id}' started with {len(runtime.state.members)} teammates."

    async def resume(self, session_key: str, team_id: str) -> str:
        async with self._runtime_lock:
            if self._runtime(session_key, auto_attach=False) is not None:
                return "Error: active team already exists for this session"
            for run_dir in self._iter_session_runs(session_key):
                cfg = run_dir / "config.json"
                if not cfg.exists():
                    continue
                state = self._load_state(cfg)
                if state.team_id != team_id and state.run_id != team_id:
                    continue
                state.status = "active"
                state.updated_at = _team_timestamp()
                runtime = SparkBotTeamRuntime(session_key, run_dir, state)
                self._save_state(runtime)
                self._active_by_session[session_key] = runtime
                self._append_event(runtime, "team_resumed", f"Resumed team {team_id}")
                self._ensure_workers(runtime)
                return f"Resumed team '{state.team_id}'."
            return f"Error: team '{team_id}' not found"

    async def shutdown(self, session_key: str) -> str:
        return await self.stop_mode(session_key)

    def approve_for_session(self, session_key: str, task_id: str) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "Error: no active team"
        updated = self._update_task(runtime, task_id, status="in_progress")
        if updated is None:
            return f"Error: task {task_id} not found"
        self._append_event(runtime, "task_approved", f"Approved task {task_id}")
        self._ensure_workers(runtime)
        return f"Updated task {task_id} to in_progress"

    def reject_for_session(self, session_key: str, task_id: str, reason: str) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "Error: no active team"
        updated = self._update_task(runtime, task_id, status="planning", result=reason)
        if updated is None:
            return f"Error: task {task_id} not found"
        self._append_event(runtime, "task_rejected", f"Rejected task {task_id}: {reason[:100]}")
        self._ensure_workers(runtime)
        return f"Updated task {task_id} to planning"

    def request_changes_for_session(
        self,
        session_key: str,
        task_id: str,
        instruction: str,
    ) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "Error: no active team"
        updated = self._update_task(runtime, task_id, status="planning", result=instruction)
        if updated is None:
            return f"Error: task {task_id} not found"
        self._append_event(
            runtime,
            "task_change_requested",
            f"Requested changes on {task_id}: {instruction[:100]}",
        )
        self._ensure_workers(runtime)
        return f"Requested changes for {task_id}."

    def handle_approval_reply(self, session_key: str, text: str) -> str | None:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return None
        pending = [task for task in self._load_tasks(runtime) if task.status == "awaiting_approval"]
        if not pending:
            return None
        task_id = self._extract_task_id(text, [task.id for task in pending])
        if not task_id:
            return (
                "I found pending approvals but could not map your reply to a task. "
                "Please mention the task id."
            )
        lowered = text.lower()
        approve_hit = any(
            token in lowered
            for token in ("approve", "approved", "accept", "ok", "批准", "同意", "通过", "可以")
        )
        reject_hit = any(
            token in lowered for token in ("reject", "decline", "deny", "拒绝", "驳回")
        )
        change_hit = any(
            token in lowered
            for token in ("manual", "change", "revise", "adjust", "修改", "调整", "补充", "变更")
        )
        feedback = self._clean_feedback(text, task_id)
        if approve_hit and not reject_hit and not change_hit:
            return self.approve_for_session(session_key, task_id)
        if reject_hit and not change_hit:
            if not feedback:
                return "I can reject it, but I still need a reason."
            return self.reject_for_session(session_key, task_id, feedback)
        if change_hit or reject_hit:
            if not feedback:
                return "I can request changes, but I still need guidance text."
            return self.request_changes_for_session(session_key, task_id, feedback)
        return (
            "I detected approval context but could not infer intent. "
            "Reply with approve/reject/change + task id."
        )

    def render_board(self, session_key: str) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "No active team."
        return self._render_board(runtime)

    def list_members(self, session_key: str) -> list[str]:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return []
        return [runtime.state.lead] + [member.name for member in runtime.state.members]

    def get_member_snapshot(self, session_key: str, name: str) -> dict[str, Any] | None:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return None
        tasks = self._load_tasks(runtime)
        if name == runtime.state.lead:
            return {
                "name": runtime.state.lead,
                "role": "team leader",
                "status": "active",
                "task": None,
                "recent_messages": self._recent_mail_for(runtime, runtime.state.lead),
            }
        member = next((item for item in runtime.state.members if item.name == name), None)
        if member is None:
            return None
        current = next(
            (
                task
                for task in tasks
                if task.owner == name
                and task.status in {"planning", "awaiting_approval", "in_progress"}
            ),
            None,
        )
        return {
            "name": member.name,
            "role": member.role,
            "status": member.status,
            "task": asdict(current) if current is not None else None,
            "recent_messages": self._recent_mail_for(runtime, name),
        }

    def get_board_snapshot(self, session_key: str) -> dict[str, Any] | None:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return None
        tasks = self._load_tasks(runtime)
        approvals = [asdict(task) for task in tasks if task.status == "awaiting_approval"]
        members = [
            {
                "name": member.name,
                "role": member.role,
                "status": member.status,
                "task": self._current_task_label(tasks, member.name),
            }
            for member in runtime.state.members
        ]
        return {
            "team_id": runtime.state.team_id,
            "run_id": runtime.state.run_id,
            "status": runtime.state.status,
            "members": [{"name": runtime.state.lead, "role": "team leader"}] + members,
            "tasks": [asdict(task) for task in tasks],
            "approvals": approvals,
            "approval_focus": approvals[0] if approvals else None,
            "recent_messages": [asdict(mail) for mail in self._load_mail(runtime)[-5:]],
            "recent_updates": self._recent_updates(runtime),
        }

    def add_task(self, session_key: str, task: dict[str, Any]) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "Error: no active team"
        tasks = self._load_tasks(runtime)
        spec = dict(task)
        spec.setdefault("id", self._next_task_id(tasks))
        new_task = SparkBotTeamTask.from_json(spec)
        tasks.append(new_task)
        self._save_tasks(runtime, tasks)
        self._append_event(runtime, "task_added", f"Added task {new_task.id}: {new_task.title}")
        self._ensure_workers(runtime)
        return f"Added task {new_task.id}"

    async def message_worker(self, session_key: str, to: str, content: str) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "Error: no active team"
        self._append_mail(
            runtime,
            SparkBotTeamMail(
                id=str(uuid.uuid4())[:8],
                from_agent=runtime.state.lead,
                to_agent=to,
                content=content,
            ),
        )
        self._append_event(runtime, "lead_message", f"Lead -> {to}: {content[:120]}")
        return f"Sent message to {to}"

    async def stop_all(self) -> None:
        runtimes = list(self._active_by_session.values())
        for runtime in runtimes:
            await self._cancel_worker_tasks(runtime)
        self._active_by_session.clear()

    def _route_instruction(self, runtime: SparkBotTeamRuntime, instruction: str) -> str:
        normalized = instruction.strip()
        if not normalized:
            return "Please provide an instruction."
        if self._looks_risky(normalized) and not normalized.lower().startswith("confirm "):
            runtime.state.status = "paused"
            runtime.state.updated_at = _team_timestamp()
            self._save_state(runtime)
            self._append_event(
                runtime, "risk_gate", f"Paused risky instruction: {normalized[:140]}"
            )
            return (
                "Risk gate paused this instruction because it may be destructive.\n"
                "Re-send with `/team confirm <instruction>` to continue."
            )
        if normalized.lower().startswith("confirm "):
            normalized = normalized[8:].strip()
            runtime.state.status = "active"
            runtime.state.updated_at = _team_timestamp()
            self._save_state(runtime)

        tasks = self._load_tasks(runtime)
        task = SparkBotTeamTask(
            id=self._next_task_id(tasks),
            title=self._title_from_instruction(normalized),
            description=normalized,
            owner=self._default_owner(runtime),
        )
        tasks.append(task)
        self._save_tasks(runtime, tasks)
        self._append_event(runtime, "task_added", f"{task.id}: {task.title}")
        self._ensure_workers(runtime)
        return f"Queued 1 task(s): {task.id}."

    def _create_runtime_from_plan(
        self,
        session_key: str,
        plan: dict[str, Any],
        *,
        team_id: str | None = None,
    ) -> SparkBotTeamRuntime:
        run_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        run_dir = self._session_dir(session_key) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        members = self._normalize_members(plan.get("members"))
        tasks = self._normalize_tasks(plan.get("tasks"), members)
        state = SparkBotTeamState(
            team_id=team_id or f"nano-{run_id[-6:]}",
            run_id=run_id,
            mission=str(plan.get("mission") or team_id or ""),
            members=members,
            status="active",
            session_key=session_key,
        )
        runtime = SparkBotTeamRuntime(session_key=session_key, run_dir=run_dir, state=state)
        self._save_state(runtime)
        self._save_tasks(runtime, tasks)
        (run_dir / "NOTES.md").write_text(
            str(plan.get("notes") or "# Team Notes\n- Keep changes minimal and reliable.\n"),
            encoding="utf-8",
        )
        return runtime

    def _runtime(
        self,
        session_key: str,
        *,
        auto_attach: bool = False,
    ) -> SparkBotTeamRuntime | None:
        runtime = self._active_by_session.get(session_key)
        if runtime is not None:
            if runtime.state.status not in _TEAM_FINISHED_STATUSES:
                return runtime
            self._active_by_session.pop(session_key, None)
        if auto_attach:
            return self._auto_attach(session_key)
        return None

    def _auto_attach(self, session_key: str) -> SparkBotTeamRuntime | None:
        run_dir = self._latest_unfinished_dir(session_key)
        if run_dir is None:
            return None
        state = self._load_state(run_dir / "config.json")
        runtime = SparkBotTeamRuntime(session_key=session_key, run_dir=run_dir, state=state)
        self._active_by_session[session_key] = runtime
        self._append_event(runtime, "team_auto_attach", f"Auto-attached run {state.run_id}")
        self._ensure_workers(runtime)
        return runtime

    def _latest_unfinished_dir(self, session_key: str) -> Path | None:
        for run_dir in self._iter_session_runs(session_key):
            cfg = run_dir / "config.json"
            if not cfg.exists():
                continue
            try:
                state = self._load_state(cfg)
            except Exception:
                continue
            if state.status not in _TEAM_FINISHED_STATUSES:
                return run_dir
        return None

    def _iter_session_runs(self, session_key: str) -> list[Path]:
        base = self._session_dir(session_key)
        if not base.exists():
            return []
        return sorted((path for path in base.iterdir() if path.is_dir()), reverse=True)

    def _session_dir(self, session_key: str) -> Path:
        path = self.teams_dir / self._safe_filename(session_key)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save_state(self, runtime: SparkBotTeamRuntime) -> None:
        runtime.config_path.write_text(
            json.dumps(asdict(runtime.state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _load_state(path: Path) -> SparkBotTeamState:
        return SparkBotTeamState.from_json(json.loads(path.read_text(encoding="utf-8")))

    def _load_tasks(self, runtime: SparkBotTeamRuntime) -> list[SparkBotTeamTask]:
        if not runtime.tasks_path.exists():
            return []
        try:
            data = json.loads(runtime.tasks_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        return [SparkBotTeamTask.from_json(item) for item in data if isinstance(item, dict)]

    def _save_tasks(
        self,
        runtime: SparkBotTeamRuntime,
        tasks: list[SparkBotTeamTask],
    ) -> None:
        runtime.tasks_path.write_text(
            json.dumps([asdict(task) for task in tasks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        runtime.state.updated_at = _team_timestamp()
        self._save_state(runtime)

    def _update_task(
        self,
        runtime: SparkBotTeamRuntime,
        task_id: str,
        **fields: Any,
    ) -> SparkBotTeamTask | None:
        tasks = self._load_tasks(runtime)
        for task in tasks:
            if task.id != task_id:
                continue
            for key, value in fields.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            self._save_tasks(runtime, tasks)
            return task
        return None

    def _append_event(self, runtime: SparkBotTeamRuntime, kind: str, message: str) -> None:
        runtime.run_dir.mkdir(parents=True, exist_ok=True)
        record = {"ts": _team_timestamp(), "kind": kind, "message": message}
        with runtime.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_mail(self, runtime: SparkBotTeamRuntime) -> list[SparkBotTeamMail]:
        if not runtime.mailbox_path.exists():
            return []
        mail: list[SparkBotTeamMail] = []
        for line in runtime.mailbox_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                mail.append(SparkBotTeamMail.from_json(data))
        return mail

    def _append_mail(self, runtime: SparkBotTeamRuntime, mail: SparkBotTeamMail) -> None:
        mails = self._load_mail(runtime)[-199:]
        mails.append(mail)
        runtime.mailbox_path.write_text(
            "\n".join(json.dumps(asdict(item), ensure_ascii=False) for item in mails) + "\n",
            encoding="utf-8",
        )

    def _recent_mail_for(
        self,
        runtime: SparkBotTeamRuntime,
        agent_name: str,
        n: int = 5,
    ) -> list[dict[str, Any]]:
        recent = [
            mail
            for mail in self._load_mail(runtime)
            if mail.to_agent in {agent_name, "*"} or mail.from_agent == agent_name
        ][-n:]
        return [asdict(mail) for mail in recent]

    def _render_board(self, runtime: SparkBotTeamRuntime) -> str:
        tasks = self._load_tasks(runtime)
        if not tasks:
            return "No team tasks."
        member_lines = (
            "\n".join(
                (
                    f"- {member.name}: {member.role} ({member.status}) "
                    f"[{self._current_task_label(tasks, member.name)}]"
                )
                for member in runtime.state.members
            )
            or "- none"
        )
        task_lines = "\n".join(
            (
                f"| {task.id} | {task.title} | {task.owner or '-'} | "
                f"{task.status} | {', '.join(task.depends_on) or '-'} | "
                f"{self._task_tool_summary(task)} | {self._task_artifact_summary(task)} |"
            )
            for task in tasks
        )
        return (
            "## Members\n"
            f"{member_lines}\n\n"
            "## Tasks\n"
            "| ID | Title | Owner | Status | Depends | Tools | Artifacts |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            f"{task_lines}"
        )

    @staticmethod
    def _task_tool_summary(task: SparkBotTeamTask) -> str:
        if not task.tool_results:
            return "-"
        latest = task.tool_results[-1]
        latest_tool = str(latest.get("tool") or "tool")
        run_label = "run" if len(task.tool_results) == 1 else "runs"
        failures = sum(1 for result in task.tool_results if not result.get("success", True))
        if failures:
            return f"{latest_tool} ({len(task.tool_results)} {run_label}, {failures} failed)"
        return f"{latest_tool} ({len(task.tool_results)} {run_label})"

    @staticmethod
    def _task_artifact_summary(task: SparkBotTeamTask) -> str:
        if not task.artifacts:
            return "-"
        labels: list[str] = []
        for artifact in task.artifacts[:3]:
            label = (
                artifact.get("filename")
                or artifact.get("title")
                or artifact.get("file")
                or artifact.get("path")
                or artifact.get("url")
            )
            if label:
                labels.append(Path(str(label)).name)
        if not labels:
            return f"{len(task.artifacts)} item(s)"
        if len(task.artifacts) > len(labels):
            labels.append(f"+{len(task.artifacts) - len(labels)} more")
        return ", ".join(labels)

    def _snapshot_text(self, runtime: SparkBotTeamRuntime) -> str:
        return (
            f"## Team: {runtime.state.team_id}\n"
            f"- Mission: {runtime.state.mission or '(none)'}\n"
            f"- Run ID: {runtime.state.run_id}\n"
            f"- Status: {runtime.state.status}\n\n"
            f"{self._render_board(runtime)}"
        )

    def _recent_updates(self, runtime: SparkBotTeamRuntime, n: int = 4) -> list[str]:
        if not runtime.events_path.exists():
            return []
        updates: list[str] = []
        for line in reversed(runtime.events_path.read_text(encoding="utf-8").splitlines()):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = str(event.get("message") or "").strip()
            if message:
                updates.append(message)
            if len(updates) >= n:
                break
        updates.reverse()
        return updates

    async def worker_action(
        self,
        session_key: str,
        worker_name: str,
        action: str,
        **kwargs: Any,
    ) -> str:
        runtime = self._runtime(session_key, auto_attach=True)
        if runtime is None:
            return "Error: no active team"
        if action == "board":
            return self._render_board(runtime)
        if action == "claim":
            return self._claim_task(runtime, kwargs.get("task_id") or "", worker_name)
        if action == "complete":
            return self._complete_task(
                runtime,
                kwargs.get("task_id") or "",
                worker_name,
                kwargs.get("result") or "",
            )
        if action == "submit_plan":
            return self._submit_plan(
                runtime,
                kwargs.get("task_id") or "",
                worker_name,
                kwargs.get("plan") or "",
            )
        if action == "mail_send":
            to_agent = str(kwargs.get("to") or "")
            content = str(kwargs.get("content") or "")
            self._append_mail(
                runtime,
                SparkBotTeamMail(
                    id=str(uuid.uuid4())[:8],
                    from_agent=worker_name,
                    to_agent=to_agent,
                    content=content,
                ),
            )
            self._append_event(
                runtime, "worker_message", f"{worker_name} -> {to_agent}: {content[:120]}"
            )
            return f"Sent message to {to_agent}"
        if action == "mail_read":
            unread = self._read_unread_mail(runtime, worker_name)
            return (
                "\n".join(f"- [{mail.from_agent}] {mail.content}" for mail in unread)
                or "No unread messages."
            )
        if action == "mail_broadcast":
            content = str(kwargs.get("content") or "")
            self._append_mail(
                runtime,
                SparkBotTeamMail(
                    id=str(uuid.uuid4())[:8],
                    from_agent=worker_name,
                    to_agent="*",
                    content=content,
                ),
            )
            self._append_event(runtime, "worker_broadcast", f"{worker_name}: {content[:120]}")
            return "Broadcast sent"
        if action == "run_tool":
            tool_name = str(kwargs.get("tool_name") or kwargs.get("name") or "")
            arguments = kwargs.get("arguments") or kwargs.get("args") or {}
            if not isinstance(arguments, dict):
                return "Error: arguments must be an object"
            return await self._execute_team_tool(
                runtime,
                worker_name,
                tool_name,
                arguments,
                task_id=str(kwargs.get("task_id") or ""),
            )
        return f"Error: unknown action '{action}'"

    def _ensure_workers(self, runtime: SparkBotTeamRuntime) -> None:
        if not self.auto_start_workers:
            return
        if runtime.state.status in _TEAM_FINISHED_STATUSES:
            return
        active = 0
        for member in runtime.state.members:
            if member.status == "stopped":
                continue
            if active >= self.max_workers:
                break
            self._ensure_worker(runtime, member.name)
            active += 1

    def _ensure_worker(self, runtime: SparkBotTeamRuntime, worker_name: str) -> None:
        running = runtime.worker_tasks.get(worker_name)
        if running is not None and not running.done():
            return
        member = next((item for item in runtime.state.members if item.name == worker_name), None)
        if member is None or member.status == "stopped":
            return
        task = asyncio.create_task(
            self._run_worker(runtime.session_key, worker_name),
            name=f"SparkBot:team:{runtime.state.run_id}:{worker_name}",
        )
        runtime.worker_tasks[worker_name] = task
        task.add_done_callback(
            lambda done, key=runtime.session_key, worker=worker_name: self._cleanup_worker(
                key, worker, done
            )
        )

    def _cleanup_worker(
        self,
        session_key: str,
        worker_name: str,
        _task: asyncio.Task[None],
    ) -> None:
        runtime = self._active_by_session.get(session_key)
        if runtime is None:
            return
        runtime.worker_tasks.pop(worker_name, None)

    async def _cancel_worker_tasks(self, runtime: SparkBotTeamRuntime) -> int:
        tasks = [task for task in runtime.worker_tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        runtime.worker_tasks.clear()
        return len(tasks)

    async def _run_worker(self, session_key: str, worker_name: str) -> None:
        runtime = self._active_by_session.get(session_key)
        if runtime is None or runtime.state.status in _TEAM_FINISHED_STATUSES:
            return
        member = next((item for item in runtime.state.members if item.name == worker_name), None)
        if member is None:
            return
        self._set_member_status(runtime, worker_name, "working")
        final_result = "No claimable task."
        current: SparkBotTeamTask | None = None
        try:
            for _ in range(max(1, self.worker_max_iterations)):
                runtime = self._active_by_session.get(session_key)
                if runtime is None or runtime.state.status in _TEAM_FINISHED_STATUSES:
                    return
                current = self._get_current_task(runtime, worker_name)
                if current is None:
                    claimable = self._get_claimable_task(runtime, worker_name)
                    if claimable is None:
                        final_result = "No claimable task."
                        break
                    claim_result = self._claim_task(runtime, claimable.id, worker_name)
                    self._append_event(runtime, "task_claimed", claim_result)
                    current = self._get_current_task(runtime, worker_name)
                if current is None:
                    break
                if current.status == "awaiting_approval":
                    final_result = current.plan or "Awaiting approval."
                    self._set_member_status(runtime, worker_name, "waiting_approval")
                    await self._maybe_emit_approval_prompt(runtime, current)
                    break
                if current.requires_approval and current.status == "planning":
                    plan = await self._build_task_plan(runtime, member, current)
                    final_result = plan
                    self._submit_plan(runtime, current.id, worker_name, plan)
                    current = self._get_current_task(runtime, worker_name)
                    self._set_member_status(runtime, worker_name, "waiting_approval")
                    await self._maybe_emit_approval_prompt(runtime, current)
                    break
                if current.status in {"planning", "pending"}:
                    self._claim_task(runtime, current.id, worker_name)
                    current = self._get_current_task(runtime, worker_name)
                if current is not None and current.status == "in_progress":
                    final_result = await self._complete_task_with_llm(runtime, member, current)
                    complete_result = self._complete_task(
                        runtime, current.id, worker_name, final_result
                    )
                    self._append_event(runtime, "task_completed", complete_result)
                    await self._emit_team_update(
                        runtime,
                        f"Team lead: {worker_name} completed `{current.id}: {current.title}`.",
                    )
                    current = None
                    self._ensure_workers(runtime)
                    continue
                break
            else:
                final_result = f"Reached worker max iterations ({self.worker_max_iterations})."
            self._set_member_status(runtime, worker_name, "idle")
            self._append_event(runtime, "worker_update", f"{worker_name}: {final_result[:160]}")
        except asyncio.CancelledError:
            self._set_member_status(runtime, worker_name, "stopped")
            raise
        except Exception as exc:
            logger.exception("SparkBot team worker '%s' failed", worker_name)
            self._set_member_status(runtime, worker_name, "stopped")
            await self._emit_team_update(runtime, f"Team worker {worker_name} failed: {exc}")

    def _claim_task(
        self,
        runtime: SparkBotTeamRuntime,
        task_id: str,
        worker_name: str,
    ) -> str:
        tasks = self._load_tasks(runtime)
        for task in tasks:
            if task.id != task_id:
                continue
            if task.owner and task.owner != worker_name:
                return f"Error: task {task_id} is already owned by {task.owner}"
            if task.status not in {"pending", "planning"}:
                return f"Error: task {task_id} is not claimable (status: {task.status})"
            if not self._deps_met(task, tasks):
                return f"Error: task {task_id} is blocked by dependencies"
            task.owner = worker_name
            task.status = "planning" if task.requires_approval else "in_progress"
            self._save_tasks(runtime, tasks)
            return f"Claimed task {task_id}"
        return f"Error: task {task_id} not found"

    def _submit_plan(
        self,
        runtime: SparkBotTeamRuntime,
        task_id: str,
        worker_name: str,
        plan: str,
    ) -> str:
        task = self._update_task(
            runtime,
            task_id,
            owner=worker_name,
            status="awaiting_approval",
            plan=plan,
        )
        if task is None:
            return f"Error: task {task_id} not found"
        self._append_event(
            runtime, "task_plan_submitted", f"{worker_name} submitted plan for {task_id}"
        )
        return f"Submitted plan for {task_id}"

    def _complete_task(
        self,
        runtime: SparkBotTeamRuntime,
        task_id: str,
        worker_name: str,
        result: str,
    ) -> str:
        task = self._update_task(
            runtime,
            task_id,
            owner=worker_name,
            status="completed",
            result=result,
        )
        if task is None:
            return f"Error: task {task_id} not found"
        return f"Updated task {task_id} to completed"

    def _get_current_task(
        self,
        runtime: SparkBotTeamRuntime,
        worker_name: str,
    ) -> SparkBotTeamTask | None:
        for task in self._load_tasks(runtime):
            if task.owner == worker_name and task.status in {
                "planning",
                "awaiting_approval",
                "in_progress",
            }:
                return task
        return None

    def _get_claimable_task(
        self,
        runtime: SparkBotTeamRuntime,
        worker_name: str,
    ) -> SparkBotTeamTask | None:
        tasks = self._load_tasks(runtime)
        for task in tasks:
            if task.status not in {"pending", "planning"}:
                continue
            if task.owner and task.owner != worker_name:
                continue
            if self._deps_met(task, tasks):
                return task
        return None

    @staticmethod
    def _deps_met(task: SparkBotTeamTask, tasks: list[SparkBotTeamTask]) -> bool:
        completed = {item.id for item in tasks if item.status == "completed"}
        return all(dep in completed for dep in task.depends_on)

    def _read_unread_mail(
        self,
        runtime: SparkBotTeamRuntime,
        agent_name: str,
    ) -> list[SparkBotTeamMail]:
        mails = self._load_mail(runtime)
        unread: list[SparkBotTeamMail] = []
        for mail in mails:
            if mail.to_agent not in {agent_name, "*"} or agent_name in mail.read_by:
                continue
            mail.read_by.append(agent_name)
            unread.append(mail)
        runtime.mailbox_path.write_text(
            "\n".join(json.dumps(asdict(item), ensure_ascii=False) for item in mails)
            + ("\n" if mails else ""),
            encoding="utf-8",
        )
        return unread

    async def _run_task_tools(
        self,
        runtime: SparkBotTeamRuntime,
        member: SparkBotTeamMember,
        task: SparkBotTeamTask,
    ) -> str:
        calls = self._normalize_tool_calls(task)
        if not calls:
            return ""
        rendered: list[str] = []
        for call in calls:
            tool_name = call["name"]
            arguments = call["arguments"]
            record = await self._execute_team_tool_record(
                runtime,
                member.name,
                tool_name,
                arguments,
                task_id=task.id,
            )
            self._append_tool_records_to_task(runtime, task.id, [record])
            rendered.append(f"### {tool_name}\n{record['content']}")
        return "Tool results:\n\n" + "\n\n".join(rendered)

    async def _plan_task_tools(
        self,
        runtime: SparkBotTeamRuntime,
        member: SparkBotTeamMember,
        task: SparkBotTeamTask,
    ) -> list[dict[str, Any]]:
        if not self.auto_plan_tools or self.max_planned_tool_calls <= 0:
            return []
        tools_text = self._tool_definitions_for_prompt()
        if not tools_text:
            return []
        prompt = (
            "# Tool Planning\n\n"
            "You are deciding whether a SparkBot team worker should call NG tools "
            "before completing a task. Return strict JSON only.\n\n"
            "Schema:\n"
            '{"tool_calls":[{"name":"tool_name","arguments":{}}]}\n\n'
            "Rules:\n"
            "- Return an empty list when the task can be completed from reasoning alone.\n"
            f"- Use at most {self.max_planned_tool_calls} tool call(s).\n"
            "- Use only tools listed below.\n"
            "- Put executable Python in code_execution.arguments.code when needed.\n"
            "- Put search questions in web_search.arguments.query, rag.arguments.query, "
            "or paper_search.arguments.query.\n\n"
            f"Mission: {runtime.state.mission}\n"
            f"Worker: {member.name} ({member.role})\n"
            f"Task: {task.id} - {task.title}\n"
            f"Description: {task.description or task.title}\n\n"
            f"Available tools:\n{tools_text}"
        )
        try:
            raw = await llm_complete(
                prompt=prompt,
                **self._llm_kwargs(
                    member.model or self.model,
                    max_tokens=min(self.max_tokens, 1000),
                    temperature=0.1,
                ),
            )
        except Exception:
            return []
        return self._parse_tool_plan(raw)

    def _tool_definitions_for_prompt(self) -> str:
        registry = self.tool_registry or get_tool_registry()
        definitions: list[Any] = []
        get_definitions = getattr(registry, "get_definitions", None)
        if callable(get_definitions):
            try:
                definitions = list(get_definitions())
            except Exception:
                definitions = []
        if definitions:
            lines: list[str] = []
            for definition in definitions:
                name = getattr(definition, "name", "")
                description = getattr(definition, "description", "")
                parameters = getattr(definition, "parameters", []) or []
                param_names = ", ".join(getattr(param, "name", "") for param in parameters)
                lines.append(f"- {name}: {description} Args: {param_names}".strip())
            return "\n".join(lines)
        list_tools = getattr(registry, "list_tools", None)
        if callable(list_tools):
            try:
                names = [str(name) for name in list_tools()]
            except Exception:
                names = []
            if names:
                return "\n".join(f"- {name}" for name in names)
        return "\n".join(
            [
                "- code_execution: run Python code for computation or verification. Args: code, intent",
                "- web_search: search the web. Args: query",
                "- rag: search a knowledge base. Args: query, kb_name",
                "- reason: ask a dedicated reasoning helper. Args: query, context",
                "- brainstorm: explore possibilities. Args: topic, context",
                "- paper_search: search arXiv papers. Args: query, max_results",
            ]
        )

    def _parse_tool_plan(self, raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, (dict, list)):
            parsed = raw
        else:
            parsed = extract_json_from_text(str(raw))
        if isinstance(parsed, dict):
            calls_raw = parsed.get("tool_calls") or parsed.get("toolCalls") or []
            if not calls_raw and (parsed.get("name") or parsed.get("tool")):
                calls_raw = [parsed]
        elif isinstance(parsed, list):
            calls_raw = parsed
        else:
            return []
        calls: list[dict[str, Any]] = []
        for item in calls_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("tool") or item.get("tool_name") or "").strip()
            if not name:
                continue
            arguments = item.get("arguments") or item.get("args") or {}
            if not isinstance(arguments, dict):
                arguments = {"query": str(arguments)}
            calls.append({"name": name, "arguments": dict(arguments)})
            if len(calls) >= self.max_planned_tool_calls:
                break
        return calls

    def _normalize_tool_calls(self, task: SparkBotTeamTask) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for raw in task.tool_calls:
            tool_name = str(
                raw.get("name") or raw.get("tool") or raw.get("tool_name") or ""
            ).strip()
            if not tool_name:
                continue
            arguments = raw.get("arguments") or raw.get("args") or {}
            if not isinstance(arguments, dict):
                arguments = {"query": str(arguments)}
            calls.append({"name": tool_name, "arguments": dict(arguments)})
        return calls

    async def _execute_team_tool(
        self,
        runtime: SparkBotTeamRuntime,
        worker_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        task_id: str = "",
    ) -> str:
        record = await self._execute_team_tool_record(
            runtime,
            worker_name,
            tool_name,
            arguments,
            task_id=task_id,
        )
        if task_id:
            self._append_tool_records_to_task(runtime, task_id, [record])
        return str(record.get("content") or "")

    async def _execute_team_tool_record(
        self,
        runtime: SparkBotTeamRuntime,
        worker_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        task_id: str = "",
    ) -> dict[str, Any]:
        tool_name = tool_name.strip()
        if not tool_name:
            return {
                "id": str(uuid.uuid4())[:8],
                "tool": "",
                "worker": worker_name,
                "task_id": task_id,
                "arguments": {},
                "success": False,
                "content": "Error: tool_name is required",
                "error": "tool_name is required",
                "sources": [],
                "metadata": {},
                "artifacts": [],
                "started_at": _team_timestamp(),
                "finished_at": _team_timestamp(),
            }
        registry = self.tool_registry or get_tool_registry()
        args = self._tool_arguments_with_defaults(runtime, worker_name, task_id, arguments)
        started_at = _team_timestamp()
        self._append_event(
            runtime,
            "tool_started",
            f"{worker_name} running {tool_name}{f' for {task_id}' if task_id else ''}",
        )
        try:
            result = await registry.execute(tool_name, **args)
        except Exception as exc:
            self._append_event(runtime, "tool_failed", f"{tool_name}: {exc}")
            return {
                "id": str(uuid.uuid4())[:8],
                "tool": tool_name,
                "worker": worker_name,
                "task_id": task_id,
                "arguments": self._json_safe(args),
                "success": False,
                "content": f"Error: {tool_name} failed: {exc}",
                "error": str(exc),
                "sources": [],
                "metadata": {},
                "artifacts": [],
                "started_at": started_at,
                "finished_at": _team_timestamp(),
            }
        content = self._tool_result_content(result)
        record = {
            "id": str(uuid.uuid4())[:8],
            "tool": tool_name,
            "worker": worker_name,
            "task_id": task_id,
            "arguments": self._json_safe(args),
            "success": self._tool_result_success(result),
            "content": content,
            "error": "" if self._tool_result_success(result) else content,
            "sources": self._json_safe(self._tool_result_sources(result)),
            "metadata": self._json_safe(self._tool_result_metadata(result)),
            "artifacts": self._json_safe(self._extract_tool_artifacts(tool_name, result)),
            "started_at": started_at,
            "finished_at": _team_timestamp(),
        }
        self._append_event(runtime, "tool_completed", f"{tool_name}: {content[:160]}")
        return record

    def _tool_arguments_with_defaults(
        self,
        runtime: SparkBotTeamRuntime,
        worker_name: str,
        task_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        args = dict(arguments)
        worker_dir = runtime.run_dir / "workers" / self._safe_filename(worker_name)
        worker_dir.mkdir(parents=True, exist_ok=True)
        args.setdefault("workspace_dir", str(worker_dir))
        args.setdefault("feature", "SparkBot_team")
        args.setdefault("session_id", runtime.session_key)
        args.setdefault("turn_id", runtime.state.run_id)
        if task_id:
            args.setdefault("task_id", task_id)
        return args

    @staticmethod
    def _tool_result_content(result: Any) -> str:
        if isinstance(result, ToolResult):
            return result.content
        if isinstance(result, dict):
            return str(result.get("content") or result.get("answer") or result)
        return str(result)

    @staticmethod
    def _tool_result_success(result: Any) -> bool:
        if isinstance(result, ToolResult):
            return bool(result.success)
        if isinstance(result, dict):
            if "success" in result:
                return bool(result.get("success"))
            if "exit_code" in result:
                return result.get("exit_code") == 0
        return True

    @staticmethod
    def _tool_result_sources(result: Any) -> list[dict[str, Any]]:
        if isinstance(result, ToolResult):
            return [dict(item) for item in result.sources if isinstance(item, dict)]
        if isinstance(result, dict):
            sources = result.get("sources") or []
            return (
                [dict(item) for item in sources if isinstance(item, dict)]
                if isinstance(sources, list)
                else []
            )
        return []

    @staticmethod
    def _tool_result_metadata(result: Any) -> dict[str, Any]:
        if isinstance(result, ToolResult):
            return dict(result.metadata or {})
        if isinstance(result, dict):
            metadata = result.get("metadata")
            if isinstance(metadata, dict):
                return dict(metadata)
            return dict(result)
        return {}

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._json_safe(item) for item in value]
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            return str(value)

    @classmethod
    def _extract_tool_artifacts(cls, tool_name: str, result: Any) -> list[dict[str, Any]]:
        metadata = cls._tool_result_metadata(result)
        sources = cls._tool_result_sources(result)
        records: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(record: dict[str, Any]) -> None:
            identifier = str(record.get("path") or record.get("file") or record.get("url") or "")
            record_type = str(record.get("type") or "artifact")
            if not identifier:
                return
            key = (record_type, identifier)
            if key in seen:
                return
            seen.add(key)
            record.setdefault("tool", tool_name)
            records.append(cls._json_safe(record))

        source_file = metadata.get("source_file")
        if source_file:
            add(
                {
                    "type": "source",
                    "path": str(source_file),
                    "filename": Path(str(source_file)).name,
                }
            )

        output_log = metadata.get("output_log")
        if output_log:
            add(
                {
                    "type": "log",
                    "path": str(output_log),
                    "filename": Path(str(output_log)).name,
                }
            )

        artifact_names = metadata.get("artifacts") or []
        artifact_paths = metadata.get("artifact_paths") or []
        if not isinstance(artifact_names, list):
            artifact_names = []
        if not isinstance(artifact_paths, list):
            artifact_paths = []
        for index, path in enumerate(artifact_paths):
            filename = (
                str(artifact_names[index]) if index < len(artifact_names) else Path(str(path)).name
            )
            add({"type": "artifact", "path": str(path), "filename": filename})

        for item in sources:
            file_value = item.get("file")
            url_value = item.get("url")
            if file_value:
                add(
                    {
                        "type": str(item.get("type") or "source"),
                        "file": str(file_value),
                        "title": item.get("title") or Path(str(file_value)).name,
                    }
                )
            elif url_value:
                add(
                    {
                        "type": str(item.get("type") or "source"),
                        "url": str(url_value),
                        "title": item.get("title") or str(url_value),
                    }
                )

        return records

    @classmethod
    def _compact_tool_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        compact = dict(record)
        content = str(compact.get("content") or "")
        if len(content) > 6000:
            compact["content"] = f"{content[:6000]}\n...[truncated]"
        error = str(compact.get("error") or "")
        if len(error) > 2000:
            compact["error"] = f"{error[:2000]}\n...[truncated]"
        return cls._json_safe(compact)

    def _append_tool_records_to_task(
        self,
        runtime: SparkBotTeamRuntime,
        task_id: str,
        records: list[dict[str, Any]],
    ) -> None:
        if not task_id or not records:
            return
        tasks = self._load_tasks(runtime)
        for task in tasks:
            if task.id != task_id:
                continue
            compact_records = [self._compact_tool_record(record) for record in records]
            task.tool_results.extend(compact_records)
            artifact_keys = {
                str(item.get("path") or item.get("file") or item.get("url") or "")
                for item in task.artifacts
                if isinstance(item, dict)
            }
            for record in compact_records:
                for artifact in record.get("artifacts") or []:
                    if not isinstance(artifact, dict):
                        continue
                    key = str(
                        artifact.get("path") or artifact.get("file") or artifact.get("url") or ""
                    )
                    if not key or key in artifact_keys:
                        continue
                    artifact_keys.add(key)
                    task.artifacts.append(dict(artifact))
                if not record.get("success", True):
                    task.last_error = str(record.get("error") or record.get("content") or "")
            self._save_tasks(runtime, tasks)
            return

    async def _build_task_plan(
        self,
        runtime: SparkBotTeamRuntime,
        member: SparkBotTeamMember,
        task: SparkBotTeamTask,
    ) -> str:
        prompt = (
            "You are a teammate in a small SparkBot nano-team. "
            "Draft a concise implementation plan for approval.\n\n"
            f"Mission: {runtime.state.mission}\n"
            f"Worker: {member.name} ({member.role})\n"
            f"Task: {task.id} - {task.title}\n"
            f"Description: {task.description or task.title}\n"
        )
        try:
            return await llm_complete(
                prompt=prompt,
                **self._llm_kwargs(
                    member.model or self.model,
                    max_tokens=min(self.max_tokens, 1400),
                    temperature=0.1,
                ),
            )
        except Exception:
            return f"Plan for {task.id}: analyze the task, make the smallest reliable change, and report results."

    async def _complete_task_with_llm(
        self,
        runtime: SparkBotTeamRuntime,
        member: SparkBotTeamMember,
        task: SparkBotTeamTask,
    ) -> str:
        tool_result = await self._run_task_tools(runtime, member, task)
        if tool_result:
            return tool_result
        planned_calls = await self._plan_task_tools(runtime, member, task)
        if planned_calls:
            task.tool_calls = planned_calls
            self._update_task(runtime, task.id, tool_calls=planned_calls)
            tool_result = await self._run_task_tools(runtime, member, task)
            if tool_result:
                return await self._summarize_task_with_tool_results(
                    runtime,
                    member,
                    task,
                    tool_result,
                )
        prompt = (
            "You are a teammate in a small SparkBot nano-team. Complete the task "
            "as a concise textual work product. Do not claim filesystem edits unless "
            "the surrounding runtime explicitly performed them.\n\n"
            f"Mission: {runtime.state.mission}\n"
            f"Worker: {member.name} ({member.role})\n"
            f"Task: {task.id} - {task.title}\n"
            f"Description: {task.description or task.title}\n"
            f"Board:\n{self._render_board(runtime)}"
        )
        try:
            return await llm_complete(
                prompt=prompt,
                **self._llm_kwargs(member.model or self.model),
            )
        except Exception:
            return (
                f"{member.name} completed {task.id}: {task.title}. "
                f"Summary: {task.description or task.title}"
            )

    async def _summarize_task_with_tool_results(
        self,
        runtime: SparkBotTeamRuntime,
        member: SparkBotTeamMember,
        task: SparkBotTeamTask,
        tool_result: str,
    ) -> str:
        prompt = (
            "You are a teammate in a small SparkBot nano-team. Use the tool results "
            "below to complete the task. Return a concise final work product.\n\n"
            f"Mission: {runtime.state.mission}\n"
            f"Worker: {member.name} ({member.role})\n"
            f"Task: {task.id} - {task.title}\n"
            f"Description: {task.description or task.title}\n\n"
            f"{tool_result}"
        )
        try:
            summary = await llm_complete(
                prompt=prompt,
                **self._llm_kwargs(
                    member.model or self.model,
                    max_tokens=min(self.max_tokens, 1000),
                    temperature=0.1,
                ),
            )
        except Exception:
            return tool_result
        return summary or tool_result

    async def _maybe_emit_approval_prompt(
        self,
        runtime: SparkBotTeamRuntime,
        task: SparkBotTeamTask | None,
    ) -> None:
        if task is None or task.status != "awaiting_approval":
            return
        if task.id in runtime.prompted_approvals:
            return
        runtime.prompted_approvals.add(task.id)
        plan = (task.plan or "").strip() or "No plan submitted."
        await self._emit_team_update(
            runtime,
            (
                f"Approval needed for `{task.id}: {task.title}` by `{task.owner or 'unknown'}`.\n"
                f"Plan: {plan[:260]}\n\n"
                "Reply naturally with approve/reject/change and include the task id."
            ),
        )

    async def _emit_team_update(self, runtime: SparkBotTeamRuntime, text: str) -> None:
        self._append_event(runtime, "lead_user_sync", text)
        if self.bus is None:
            return
        channel, chat_id = (
            runtime.session_key.split(":", 1)
            if ":" in runtime.session_key
            else ("team", runtime.session_key)
        )
        await self.bus.publish_outbound(
            SparkBotOutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=text,
                metadata={"team_text": True, "team_event": True},
            )
        )

    def _set_member_status(
        self,
        runtime: SparkBotTeamRuntime,
        worker_name: str,
        status: str,
    ) -> None:
        for member in runtime.state.members:
            if member.name == worker_name:
                member.status = status
                break
        runtime.state.updated_at = _team_timestamp()
        self._save_state(runtime)

    @staticmethod
    def _normalize_members(raw_members: Any) -> list[SparkBotTeamMember]:
        members: list[SparkBotTeamMember] = []
        if isinstance(raw_members, list):
            for item in raw_members:
                if not isinstance(item, dict):
                    continue
                member = SparkBotTeamMember.from_json(item)
                if member.name and all(existing.name != member.name for existing in members):
                    members.append(member)
        if not members:
            members = [
                SparkBotTeamMember(name="researcher", role="research and analysis"),
                SparkBotTeamMember(name="builder", role="execution and synthesis"),
            ]
        return members[:5]

    def _normalize_tasks(
        self,
        raw_tasks: Any,
        members: list[SparkBotTeamMember],
    ) -> list[SparkBotTeamTask]:
        tasks: list[SparkBotTeamTask] = []
        used: set[str] = set()
        if isinstance(raw_tasks, list):
            for item in raw_tasks:
                if not isinstance(item, dict):
                    continue
                task = SparkBotTeamTask.from_json(item)
                if not task.id or task.id in used:
                    task.id = self._next_task_id(tasks)
                if not task.title:
                    task.title = "Task"
                if task.owner and task.owner not in {member.name for member in members}:
                    task.owner = None
                used.add(task.id)
                tasks.append(task)
        if not tasks:
            tasks = [
                SparkBotTeamTask(
                    id="t1",
                    title="Analyze the request",
                    owner=members[0].name if members else None,
                ),
                SparkBotTeamTask(
                    id="t2",
                    title="Execute and report",
                    owner=members[-1].name if members else None,
                    depends_on=["t1"],
                ),
            ]
        return tasks

    @staticmethod
    def _fallback_plan(goal: str) -> dict[str, Any]:
        return {
            "mission": goal,
            "members": [
                {"name": "researcher", "role": "research and analysis", "model": None},
                {"name": "builder", "role": "execution and synthesis", "model": None},
            ],
            "tasks": [
                {
                    "id": "t1",
                    "title": "Analyze the request",
                    "description": f"Break down the objective: {goal}",
                    "owner": "researcher",
                    "depends_on": [],
                    "requires_approval": False,
                },
                {
                    "id": "t2",
                    "title": "Execute and report",
                    "description": "Implement the solution and summarize concrete outcomes.",
                    "owner": "builder",
                    "depends_on": ["t1"],
                    "requires_approval": False,
                },
            ],
            "notes": "# Team Notes\n- Keep changes minimal and reliable.\n",
        }

    @staticmethod
    def _next_task_id(tasks: list[SparkBotTeamTask]) -> str:
        numbers = []
        for task in tasks:
            if task.id.startswith("t") and task.id[1:].isdigit():
                numbers.append(int(task.id[1:]))
        return f"t{(max(numbers) if numbers else 0) + 1}"

    @staticmethod
    def _safe_filename(value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
        return safe[:80] or "session"

    @staticmethod
    def _title_from_instruction(instruction: str) -> str:
        first_line = instruction.splitlines()[0].strip()
        return first_line[:80] or "Follow-up instruction"

    @staticmethod
    def _default_owner(runtime: SparkBotTeamRuntime) -> str | None:
        if not runtime.state.members:
            return None
        return runtime.state.members[-1].name

    @staticmethod
    def _current_task_label(tasks: list[SparkBotTeamTask], owner: str) -> str:
        for task in tasks:
            if task.owner == owner and task.status in {
                "planning",
                "awaiting_approval",
                "in_progress",
            }:
                return f"{task.id}: {task.title}"
        return "-"

    @staticmethod
    def _looks_risky(text: str) -> bool:
        lowered = text.lower()
        tokens = (
            "rm -rf",
            "delete",
            "drop table",
            "truncate",
            "reset --hard",
            "format disk",
            "wipe",
            "shutdown",
            "destroy",
        )
        return any(token in lowered for token in tokens)

    @staticmethod
    def _extract_task_id(text: str, pending_ids: list[str]) -> str | None:
        matched = re.search(r"\b[tT]\d+\b", text)
        if matched:
            candidate = matched.group(0).lower()
            for pending_id in pending_ids:
                if pending_id.lower() == candidate:
                    return pending_id
        return pending_ids[0] if len(pending_ids) == 1 else None

    @staticmethod
    def _clean_feedback(text: str, task_id: str) -> str:
        cleaned = re.sub(rf"\b{re.escape(task_id)}\b", "", text, flags=re.IGNORECASE)
        for token in (
            "approve",
            "approved",
            "accept",
            "ok",
            "批准",
            "同意",
            "通过",
            "可以",
            "reject",
            "decline",
            "deny",
            "拒绝",
            "驳回",
            "manual",
            "change",
            "revise",
            "adjust",
            "修改",
            "调整",
            "补充",
            "变更",
        ):
            cleaned = re.sub(token, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" \t\r\n:,.")


class SparkBotTeamTool(BaseTool):
    """NG tool facade for lead-side nano-team orchestration."""

    def __init__(self, manager: SparkBotTeamManager, session_key: str = "web:web") -> None:
        self._manager = manager
        self._default_session_key = session_key
        self._session_key_var: ContextVar[str] = ContextVar(
            f"SparkBot_team_session_key_{id(self)}",
            default=session_key,
        )

    def set_context(
        self,
        session_key: str | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        if session_key is None and channel and chat_id:
            session_key = f"{channel}:{chat_id}"
        self._session_key_var.set(session_key or self._default_session_key)

    def _session_key(self) -> str:
        return self._session_key_var.get() or self._default_session_key

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="team",
            description="Create, resume, inspect, and control SparkBot nano-team runs.",
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Team action.",
                    enum=[
                        "create",
                        "resume",
                        "shutdown",
                        "board",
                        "approve",
                        "reject",
                        "message",
                        "add_task",
                    ],
                ),
                ToolParameter(
                    name="team_id", type="string", description="Team or run id.", required=False
                ),
                ToolParameter(
                    name="members",
                    type="array",
                    description="Optional member specs.",
                    required=False,
                ),
                ToolParameter(
                    name="tasks", type="array", description="Optional task specs.", required=False
                ),
                ToolParameter(
                    name="notes", type="string", description="Shared notes.", required=False
                ),
                ToolParameter(
                    name="mission", type="string", description="Team mission.", required=False
                ),
                ToolParameter(
                    name="task_id", type="string", description="Task id.", required=False
                ),
                ToolParameter(
                    name="reason", type="string", description="Rejection reason.", required=False
                ),
                ToolParameter(
                    name="to", type="string", description="Message recipient.", required=False
                ),
                ToolParameter(
                    name="content", type="string", description="Message content.", required=False
                ),
                ToolParameter(
                    name="task", type="object", description="Task to add.", required=False
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action") or "")
        session_key = self._session_key()
        if action == "create":
            content = await self._manager.create(
                session_key,
                str(kwargs.get("team_id") or "team"),
                list(kwargs.get("members") or []),
                list(kwargs.get("tasks") or []),
                str(kwargs.get("notes") or ""),
                mission=str(kwargs.get("mission") or ""),
            )
        elif action == "resume":
            content = await self._manager.resume(
                session_key,
                str(kwargs.get("team_id") or ""),
            )
        elif action == "shutdown":
            content = await self._manager.shutdown(session_key)
        elif action == "board":
            content = self._manager.render_board(session_key)
        elif action == "approve":
            content = self._manager.approve_for_session(
                session_key,
                str(kwargs.get("task_id") or ""),
            )
        elif action == "reject":
            content = self._manager.reject_for_session(
                session_key,
                str(kwargs.get("task_id") or ""),
                str(kwargs.get("reason") or "Rejected"),
            )
        elif action == "message":
            content = await self._manager.message_worker(
                session_key,
                str(kwargs.get("to") or ""),
                str(kwargs.get("content") or ""),
            )
        elif action == "add_task":
            task = kwargs.get("task") or {}
            content = self._manager.add_task(session_key, task if isinstance(task, dict) else {})
        else:
            content = f"Error: unknown action '{action}'"
        return ToolResult(content=content, metadata={"action": action})


class SparkBotTeamWorkerTool(BaseTool):
    """NG tool facade for worker-side board and mailbox actions."""

    def __init__(self, manager: SparkBotTeamManager, worker_name: str, session_key: str) -> None:
        self._manager = manager
        self._worker_name = worker_name
        self._session_key = session_key

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="team_worker",
            description="Team coordination. Actions: board, claim, complete, submit_plan, mail_send, mail_read, mail_broadcast.",
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Worker action.",
                    enum=[
                        "board",
                        "claim",
                        "complete",
                        "submit_plan",
                        "mail_send",
                        "mail_read",
                        "mail_broadcast",
                        "run_tool",
                    ],
                ),
                ToolParameter(
                    name="task_id", type="string", description="Task id.", required=False
                ),
                ToolParameter(
                    name="result", type="string", description="Completion result.", required=False
                ),
                ToolParameter(
                    name="plan", type="string", description="Approval plan.", required=False
                ),
                ToolParameter(
                    name="to", type="string", description="Message recipient.", required=False
                ),
                ToolParameter(
                    name="content", type="string", description="Message content.", required=False
                ),
                ToolParameter(
                    name="tool_name", type="string", description="NG tool name.", required=False
                ),
                ToolParameter(
                    name="arguments", type="object", description="Tool arguments.", required=False
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action") or "")
        payload = dict(kwargs)
        payload.pop("action", None)
        content = await self._manager.worker_action(
            self._session_key,
            self._worker_name,
            action,
            **payload,
        )
        return ToolResult(
            content=content,
            metadata={"action": action, "worker": self._worker_name},
            success=not content.startswith("Error:"),
        )


class SparkBotMessageTool(BaseTool):
    """Agent tool for sending outbound messages during a turn."""

    def __init__(self, bus: SparkBotMessageBus) -> None:
        self._bus = bus
        self._channel_var: ContextVar[str] = ContextVar(
            f"SparkBot_message_channel_{id(self)}",
            default="web",
        )
        self._chat_id_var: ContextVar[str] = ContextVar(
            f"SparkBot_message_chat_id_{id(self)}",
            default="web",
        )
        self._session_key_var: ContextVar[str] = ContextVar(
            f"SparkBot_message_session_key_{id(self)}",
            default="web:web",
        )
        self._sent_in_turn_var: ContextVar[bool] = ContextVar(
            f"SparkBot_message_sent_{id(self)}",
            default=False,
        )

    def set_context(self, channel: str, chat_id: str, session_key: str) -> None:
        self._channel_var.set(channel)
        self._chat_id_var.set(chat_id)
        self._session_key_var.set(session_key)
        self._sent_in_turn_var.set(False)

    @property
    def sent_in_turn(self) -> bool:
        return self._sent_in_turn_var.get()

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="message",
            description="Send a message to the current user or to a specific SparkBot channel/chat.",
            parameters=[
                ToolParameter(
                    name="content", type="string", description="Message content to send."
                ),
                ToolParameter(
                    name="channel",
                    type="string",
                    description="Optional target channel; defaults to the current channel.",
                    required=False,
                ),
                ToolParameter(
                    name="chat_id",
                    type="string",
                    description="Optional target chat id; defaults to the current chat.",
                    required=False,
                ),
                ToolParameter(
                    name="media",
                    type="array",
                    description="Optional attachment paths; stored in message metadata.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        content = str(kwargs.get("content") or "")
        channel = str(kwargs.get("channel") or self._channel_var.get() or "")
        chat_id = str(
            kwargs.get("chat_id") or kwargs.get("chatId") or self._chat_id_var.get() or ""
        )
        if not content:
            return ToolResult(content="Error: content is required", success=False)
        if not channel or not chat_id:
            return ToolResult(content="Error: No target channel/chat specified", success=False)

        media_raw = kwargs.get("media") or []
        media = (
            [str(item) for item in media_raw] if isinstance(media_raw, list) else [str(media_raw)]
        )
        await self._bus.publish_outbound(
            SparkBotOutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=content,
                media=media,
                metadata={
                    "agent_tool": "message",
                    "session_key": self._session_key_var.get(),
                    "media": media,
                },
            )
        )
        if channel == self._channel_var.get() and chat_id == self._chat_id_var.get():
            self._sent_in_turn_var.set(True)
        media_info = f" with {len(media)} attachment(s)" if media else ""
        return ToolResult(
            content=f"Message sent to {channel}:{chat_id}{media_info}",
            metadata={"channel": channel, "chat_id": chat_id, "media": media},
        )


class SparkBotSpawnTool(BaseTool):
    """Agent tool for spawning background SparkBot side tasks."""

    def __init__(self, manager: SparkBotSideTaskManager) -> None:
        self._manager = manager
        self._channel_var: ContextVar[str] = ContextVar(
            f"SparkBot_spawn_channel_{id(self)}",
            default="web",
        )
        self._chat_id_var: ContextVar[str] = ContextVar(
            f"SparkBot_spawn_chat_id_{id(self)}",
            default="web",
        )
        self._session_key_var: ContextVar[str] = ContextVar(
            f"SparkBot_spawn_session_key_{id(self)}",
            default="web:web",
        )

    def set_context(self, channel: str, chat_id: str, session_key: str) -> None:
        self._channel_var.set(channel)
        self._chat_id_var.set(chat_id)
        self._session_key_var.set(session_key)

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="spawn",
            description=(
                "Spawn a background SparkBot task for work that can finish later and report back."
            ),
            parameters=[
                ToolParameter(
                    name="task",
                    type="string",
                    description="Task instruction for the background worker.",
                ),
                ToolParameter(
                    name="label",
                    type="string",
                    description="Optional short task label.",
                    required=False,
                    default="spawn",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        instruction = str(kwargs.get("task") or kwargs.get("instruction") or "").strip()
        if not instruction:
            return ToolResult(content="Error: task is required", success=False)
        label = str(kwargs.get("label") or "spawn")
        content = await self._manager.spawn(
            instruction=instruction,
            label=label,
            origin_channel=self._channel_var.get(),
            origin_chat_id=self._chat_id_var.get(),
            session_key=self._session_key_var.get(),
        )
        return ToolResult(
            content=content,
            metadata={
                "label": label,
                "channel": self._channel_var.get(),
                "chat_id": self._chat_id_var.get(),
                "session_key": self._session_key_var.get(),
            },
        )


class SparkBotCronTool(BaseTool):
    """Agent tool for scheduling and managing SparkBot cron jobs."""

    def __init__(self, cron_provider: Callable[[], SparkBotCronService | None]) -> None:
        self._cron_provider = cron_provider
        self._channel_var: ContextVar[str] = ContextVar(
            f"SparkBot_cron_channel_{id(self)}",
            default="web",
        )
        self._chat_id_var: ContextVar[str] = ContextVar(
            f"SparkBot_cron_chat_id_{id(self)}",
            default="web",
        )
        self._session_key_var: ContextVar[str] = ContextVar(
            f"SparkBot_cron_session_key_{id(self)}",
            default="web:web",
        )
        self._in_cron_context: ContextVar[bool] = ContextVar(
            f"SparkBot_cron_in_context_{id(self)}",
            default=False,
        )

    def set_context(self, channel: str, chat_id: str, session_key: str) -> None:
        self._channel_var.set(channel)
        self._chat_id_var.set(chat_id)
        self._session_key_var.set(session_key)

    def set_cron_context(self, active: bool) -> Any:
        return self._in_cron_context.set(active)

    def reset_cron_context(self, token: Any) -> None:
        self._in_cron_context.reset(token)

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="cron",
            description="Schedule reminders or background SparkBot turns. Actions: add, list, remove, run.",
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Cron action.",
                    enum=["add", "list", "remove", "run"],
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Reminder/task message for add.",
                    required=False,
                ),
                ToolParameter(
                    name="every_seconds",
                    type="integer",
                    description="Recurring interval in seconds for add.",
                    required=False,
                ),
                ToolParameter(
                    name="cron_expr",
                    type="string",
                    description="Cron expression such as '0 9 * * *' for add.",
                    required=False,
                ),
                ToolParameter(
                    name="tz",
                    type="string",
                    description="IANA timezone for cron expressions.",
                    required=False,
                ),
                ToolParameter(
                    name="at",
                    type="string",
                    description="ISO datetime for one-time jobs.",
                    required=False,
                ),
                ToolParameter(
                    name="job_id",
                    type="string",
                    description="Job id for remove/run.",
                    required=False,
                ),
                ToolParameter(
                    name="include_disabled",
                    type="boolean",
                    description="Include disabled jobs when listing.",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        cron = self._cron_provider()
        if cron is None:
            return ToolResult(content="Cron service is not available.", success=False)
        action = str(kwargs.get("action") or "").strip().lower()
        if action == "add":
            return self._add_job(cron, kwargs)
        if action == "list":
            return self._list_jobs(cron, kwargs)
        if action in {"remove", "rm"}:
            return self._remove_job(cron, kwargs)
        if action == "run":
            return await self._run_job(cron, kwargs)
        return ToolResult(content=f"Error: unknown cron action '{action}'", success=False)

    def _add_job(self, cron: SparkBotCronService, kwargs: dict[str, Any]) -> ToolResult:
        if self._in_cron_context.get():
            return ToolResult(
                content="Error: cannot schedule new jobs from within a cron job execution",
                success=False,
            )
        message = str(kwargs.get("message") or "").strip()
        if not message:
            return ToolResult(content="Error: message is required for add", success=False)

        every_seconds = kwargs.get("every_seconds", kwargs.get("everySeconds"))
        cron_expr = kwargs.get("cron_expr", kwargs.get("cronExpr"))
        at = kwargs.get("at")
        tz = kwargs.get("tz")
        delete_after_run = False
        try:
            if every_seconds is not None:
                seconds = int(every_seconds)
                if seconds <= 0:
                    return ToolResult(
                        content="Error: every_seconds must be positive", success=False
                    )
                schedule = SparkBotCronSchedule(kind="every", every_ms=seconds * 1000)
            elif cron_expr:
                schedule = SparkBotCronSchedule(
                    kind="cron", expr=str(cron_expr), tz=str(tz) if tz else None
                )
            elif at:
                dt = datetime.fromisoformat(str(at))
                schedule = SparkBotCronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
                delete_after_run = True
            else:
                return ToolResult(
                    content="Error: either every_seconds, cron_expr, or at is required",
                    success=False,
                )
            job = cron.add_job(
                name=message[:30],
                schedule=schedule,
                message=message,
                deliver=True,
                channel=self._channel_var.get(),
                to=self._chat_id_var.get(),
                delete_after_run=delete_after_run,
            )
        except ValueError as exc:
            return ToolResult(content=f"Error: {exc}", success=False)
        return ToolResult(
            content=f"Created job '{job.name}' (id: {job.id})",
            metadata={"job_id": job.id, "schedule": job.schedule.kind},
        )

    @staticmethod
    def _list_jobs(cron: SparkBotCronService, kwargs: dict[str, Any]) -> ToolResult:
        include_disabled = bool(
            kwargs.get("include_disabled", kwargs.get("includeDisabled", False))
        )
        jobs = cron.list_jobs(include_disabled=include_disabled)
        if not jobs:
            return ToolResult(content="No scheduled jobs.", metadata={"jobs": 0})
        lines: list[str] = []
        for job in jobs:
            state = "enabled" if job.enabled else "disabled"
            lines.append(f"- {job.name} (id: {job.id}, {job.schedule.kind}, {state})")
        return ToolResult(
            content="Scheduled jobs:\n" + "\n".join(lines),
            metadata={"jobs": len(jobs)},
        )

    @staticmethod
    def _remove_job(cron: SparkBotCronService, kwargs: dict[str, Any]) -> ToolResult:
        job_id = str(kwargs.get("job_id") or kwargs.get("jobId") or "").strip()
        if not job_id:
            return ToolResult(content="Error: job_id is required for remove", success=False)
        if cron.remove_job(job_id):
            return ToolResult(content=f"Removed job {job_id}", metadata={"job_id": job_id})
        return ToolResult(
            content=f"Job {job_id} not found", success=False, metadata={"job_id": job_id}
        )

    @staticmethod
    async def _run_job(cron: SparkBotCronService, kwargs: dict[str, Any]) -> ToolResult:
        job_id = str(kwargs.get("job_id") or kwargs.get("jobId") or "").strip()
        if not job_id:
            return ToolResult(content="Error: job_id is required for run", success=False)
        ok = await cron.run_job(job_id, force=True)
        return ToolResult(
            content=f"Ran job {job_id}" if ok else f"Job {job_id} not found",
            success=ok,
            metadata={"job_id": job_id},
        )


class SparkBotAgentLoop:
    """NG-owned direct/chat loop used by web and channel-facing SparkBot paths."""

    def __init__(
        self,
        *,
        config: BotConfig,
        bus: SparkBotMessageBus,
        workspace: Path,
        default_session_key: str,
        record_exchange: ExchangeRecorder | None = None,
        shared_memory_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.workspace = workspace
        self.default_session_key = default_session_key
        self.model = config.model
        self.cron_service: SparkBotCronService | None = None
        self.context = SparkBotWorkspaceContext(workspace, shared_memory_dir=shared_memory_dir)
        self.agent_tools = build_sparkbot_agent_tool_registry(workspace, config.tools)
        self.agent_tool_max_iterations = max(1, int(config.agent.max_tool_iterations or 4))
        self.agent_tool_call_limit = max(1, int(config.agent.tool_call_limit or 5))
        self.agent_max_tokens = max(1, int(config.agent.max_tokens or 8192))
        self.agent_context_window_tokens = max(0, int(config.agent.context_window_tokens or 0))
        self.session_history_limit = self._session_history_limit(config.agent)
        self.agent_temperature = float(
            config.agent.temperature if config.agent.temperature is not None else 0.1
        )
        self.agent_reasoning_effort = (
            str(config.agent.reasoning_effort).strip() if config.agent.reasoning_effort else None
        )
        self.side_tasks = SparkBotSideTaskManager(
            bus=bus,
            context=self.context,
            fallback_persona=config.persona or config.name,
            model=config.model,
        )
        self.team = SparkBotTeamManager(
            workspace,
            bus=bus,
            model=config.model,
            worker_max_iterations=max(1, int(config.agent.team_worker_max_iterations or 25)),
            max_workers=max(1, int(config.agent.team_max_workers or 5)),
            temperature=self.agent_temperature,
            max_tokens=self.agent_max_tokens,
            reasoning_effort=self.agent_reasoning_effort,
        )
        self._agent_message_tool = SparkBotMessageTool(bus)
        self._agent_spawn_tool = SparkBotSpawnTool(self.side_tasks)
        self._agent_cron_tool = SparkBotCronTool(lambda: self.cron_service)
        self._agent_team_tool = SparkBotTeamTool(self.team, session_key=default_session_key)
        self._register_agent_runtime_tools()
        self._mcp_servers = dict(config.tools.mcp_servers)
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._record_exchange = record_exchange
        self._stopping = asyncio.Event()
        self._active_tasks: dict[str, list[asyncio.Task]] = {}

    def _register_agent_runtime_tools(self) -> None:
        for tool in (
            self._agent_message_tool,
            self._agent_spawn_tool,
            self._agent_cron_tool,
            self._agent_team_tool,
        ):
            self.agent_tools.register(tool)

    def _llm_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.agent_max_tokens,
            "temperature": self.agent_temperature,
        }
        if self.agent_reasoning_effort:
            kwargs["reasoning_effort"] = self.agent_reasoning_effort
        return kwargs

    @staticmethod
    def _session_history_limit(agent_config: SparkBotAgentConfig) -> int:
        if agent_config.memory_window is not None:
            return max(0, int(agent_config.memory_window))
        context_window = max(0, int(agent_config.context_window_tokens or 0))
        if 0 < context_window < 65_536:
            return max(1, min(24, context_window // 2_000))
        return 24

    def _prepare_agent_tools_for_turn(
        self,
        *,
        channel: str,
        chat_id: str,
        session_key: str,
    ) -> None:
        self._agent_message_tool.set_context(channel, chat_id, session_key)
        self._agent_spawn_tool.set_context(channel, chat_id, session_key)
        self._agent_cron_tool.set_context(channel, chat_id, session_key)
        self._agent_team_tool.set_context(session_key=session_key)

    def set_agent_cron_context(self, active: bool) -> Any:
        return self._agent_cron_tool.set_cron_context(active)

    def reset_agent_cron_context(self, token: Any) -> None:
        self._agent_cron_tool.reset_cron_context(token)

    async def _connect_mcp(self) -> None:
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        stack = AsyncExitStack()
        await stack.__aenter__()
        try:
            status = await connect_mcp_servers(self._mcp_servers, self.agent_tools, stack)
            if status.get("connected"):
                self._mcp_stack = stack
                self._mcp_connected = True
            else:
                await stack.aclose()
        except BaseException:
            logger.exception("Failed to connect SparkBot MCP servers")
            await stack.aclose()
        finally:
            self._mcp_connecting = False

    async def close_mcp(self) -> None:
        if self._mcp_stack is None:
            return
        try:
            await self._mcp_stack.aclose()
        except (RuntimeError, BaseExceptionGroup):
            logger.debug("Ignored MCP cleanup error", exc_info=True)
        finally:
            self._mcp_stack = None
            self._mcp_connected = False

    async def run(self) -> None:
        while not self._stopping.is_set():
            msg = await self.bus.consume_inbound()
            if self._stopping.is_set() or msg.metadata.get("_stop"):
                break
            session_key = self._session_key(msg.channel, msg.chat_id, msg.session_key)
            command = msg.content.strip().lower()
            if command == "/stop":
                await self._handle_stop_command(msg, session_key)
                continue
            task = asyncio.create_task(
                self._dispatch_inbound(msg, session_key),
                name=f"SparkBot:agent:{session_key}",
            )
            self._active_tasks.setdefault(session_key, []).append(task)
            task.add_done_callback(lambda done, key=session_key: self._forget_task(key, done))

    async def _dispatch_inbound(
        self,
        msg: SparkBotInboundMessage,
        session_key: str,
    ) -> None:
        try:
            response = await self.process_direct(
                msg.content,
                session_key=session_key,
                channel=msg.channel,
                chat_id=msg.chat_id,
                media=msg.media,
                attachments=msg.attachments,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("SparkBot agent loop failed for session '%s'", session_key)
            response = "Sorry, I encountered an error."
        await self.bus.publish_outbound(
            SparkBotOutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response,
            )
        )

    async def _handle_stop_command(
        self,
        msg: SparkBotInboundMessage,
        session_key: str,
    ) -> None:
        tasks = self._active_tasks.pop(session_key, [])
        cancelled = 0
        for task in tasks:
            if not task.done():
                task.cancel()
                cancelled += 1
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        cancelled += await self.side_tasks.cancel_by_session(session_key)
        cancelled += await self.team.cancel_by_session(session_key)
        await self.bus.publish_outbound(
            SparkBotOutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"Stopped {cancelled} task(s)." if cancelled else "No active task to stop.",
            )
        )

    def _forget_task(self, session_key: str, task: asyncio.Task) -> None:
        tasks = self._active_tasks.get(session_key)
        if not tasks:
            return
        if task in tasks:
            tasks.remove(task)
        if not tasks:
            self._active_tasks.pop(session_key, None)

    def _session_key(
        self,
        channel: str,
        chat_id: str,
        explicit: str | None = None,
    ) -> str:
        return explicit or self.default_session_key or f"{channel}:{chat_id}"

    async def _publish_command_response(
        self,
        *,
        channel: str,
        chat_id: str,
        content: str,
    ) -> None:
        await self.bus.publish_outbound(
            SparkBotOutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=content,
            )
        )

    async def process_direct(
        self,
        content: str,
        *,
        session_key: str | None = None,
        channel: str = "web",
        chat_id: str = "web",
        media: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        session_key = self._session_key(channel, chat_id, session_key)
        command_response = await self._handle_command(
            content,
            channel=channel,
            chat_id=chat_id,
            session_key=session_key,
        )
        if command_response is not None:
            if self._record_exchange is not None:
                self._record_exchange(channel, chat_id, content, command_response)
            return command_response
        if on_progress:
            await on_progress("Thinking...")
        prompt = self._build_prompt(
            content,
            channel=channel,
            chat_id=chat_id,
            media=media,
            attachments=attachments,
        )
        self._prepare_agent_tools_for_turn(
            channel=channel,
            chat_id=chat_id,
            session_key=session_key,
        )
        try:
            response = await self._complete_with_agent_tools(
                prompt,
                session_key=session_key,
                image_blocks=build_image_content_blocks(
                    media=media,
                    attachments=attachments,
                    workspace=self.workspace,
                ),
                on_progress=on_progress,
            )
        except Exception:
            response = f"{self.config.name}: {content}"
        if self._record_exchange is not None:
            self._record_exchange(channel, chat_id, content, response)
        return response

    async def _handle_command(
        self,
        content: str,
        *,
        channel: str,
        chat_id: str,
        session_key: str,
    ) -> str | None:
        raw = content.strip()
        command = raw.lower()
        if not command.startswith("/"):
            if self.team.is_active(session_key):
                approval_reply = self.team.handle_approval_reply(session_key, raw)
                if approval_reply:
                    return approval_reply
                return (
                    "Team mode is active. Supported input:\n"
                    "- /team <instruction|status|log|approve|reject|manual|stop>\n"
                    "- /btw <instruction>"
                )
            return None
        if command == "/help":
            return "\n".join(
                [
                    "SparkBot commands:",
                    "/new - Start a new conversation",
                    "/stop - Stop the current running channel task",
                    "/restart - Restart by stopping and starting the bot",
                    "/team <goal> - Start or instruct nano team mode",
                    "/team status - Show nano team state",
                    "/team log [n] - Show detailed collaboration logs",
                    "/team approve <task_id> - Approve a pending task",
                    "/team reject <task_id> <reason> - Reject a pending task",
                    "/team manual <task_id> <instruction> - Send change request",
                    "/team stop - Stop nano team mode",
                    "/btw <instruction> - Run a background side task",
                    "/btw status - Show side task status",
                    "/cron add every <seconds> <message>",
                    "/cron add at <iso-datetime> <message>",
                    '/cron add cron "<expr>" [tz=<iana>] <message>',
                    "/cron list",
                    "/cron remove <job_id>",
                    "/cron run <job_id>",
                    "/help - Show available commands",
                ]
            )
        if command == "/new":
            if not self._archive_session_for_new(chat_id, channel=channel):
                return "Memory archival failed, session not cleared. Please try again."
            self._clear_session(chat_id)
            return "New session started."
        if command == "/stop":
            cancelled = await self.side_tasks.cancel_by_session(session_key)
            cancelled += await self.team.cancel_by_session(session_key)
            return f"Stopped {cancelled} task(s)." if cancelled else "No active task to stop."
        if command == "/restart":
            return "Restart requested. Stop and start the bot to restart this NG instance."
        if command == "/team":
            return self._team_usage()
        if command.startswith("/teams "):
            raw = "/team " + raw[7:].strip()
            command = raw.lower()
        if command.startswith("/team "):
            return await self._handle_team_command(raw, channel=channel, session_key=session_key)
        if command.startswith("/btw"):
            return await self._handle_btw_command(
                raw,
                channel=channel,
                chat_id=chat_id,
                session_key=session_key,
            )
        if command.startswith("/cron"):
            return await self._handle_cron_command(raw, channel=channel, chat_id=chat_id)
        if self.team.is_active(session_key):
            approval_reply = self.team.handle_approval_reply(session_key, raw)
            if approval_reply:
                return approval_reply
            return (
                "Team mode is active. Supported input:\n"
                "- /team <instruction|status|log|approve|reject|manual|stop>\n"
                "- /btw <instruction>"
            )
        return None

    @staticmethod
    def _team_usage() -> str:
        return (
            "Usage:\n"
            "/team <goal>\n"
            "/team status\n"
            "/team log [n]\n"
            "/team approve <task_id>\n"
            "/team reject <task_id> <reason>\n"
            "/team manual <task_id> <instruction>\n"
            "/team stop"
        )

    async def _handle_team_command(
        self,
        raw: str,
        *,
        channel: str,
        session_key: str,
    ) -> str:
        instruction = raw[6:].strip()
        if not instruction:
            return self._team_usage()
        parts = instruction.split(maxsplit=2)
        action = parts[0].lower() if parts else ""
        if action == "status":
            return self.team.status_text(session_key)
        if action == "log":
            n = 20
            if len(parts) > 1:
                try:
                    n = max(1, min(200, int(parts[1])))
                except ValueError:
                    n = 20
            return self.team.log_text(session_key, n=n)
        if action == "stop":
            return await self.team.stop_mode(session_key, with_snapshot=channel == "cli")
        if action == "approve":
            task_id = parts[1] if len(parts) > 1 else ""
            if not task_id:
                return "Usage: /team approve <task_id>"
            return self.team.approve_for_session(session_key, task_id)
        if action == "reject":
            task_id = parts[1] if len(parts) > 1 else ""
            reason = parts[2] if len(parts) > 2 else ""
            if not task_id or not reason.strip():
                return "Usage: /team reject <task_id> <reason>"
            return self.team.reject_for_session(session_key, task_id, reason.strip())
        if action == "manual":
            task_id = parts[1] if len(parts) > 1 else ""
            instruction_text = parts[2] if len(parts) > 2 else ""
            if not task_id or not instruction_text.strip():
                return "Usage: /team manual <task_id> <instruction>"
            return self.team.request_changes_for_session(
                session_key,
                task_id,
                instruction_text.strip(),
            )
        return await self.team.start_or_route_goal(session_key, instruction)

    async def _handle_btw_command(
        self,
        raw: str,
        *,
        channel: str,
        chat_id: str,
        session_key: str,
    ) -> str:
        instruction = raw[4:].strip()
        if not instruction:
            return "Usage: /btw <instruction>"
        if instruction.lower() == "status":
            return self.side_tasks.status_text()
        return await self.side_tasks.spawn(
            instruction=instruction,
            label="btw",
            origin_channel=channel,
            origin_chat_id=chat_id,
            session_key=session_key,
        )

    async def _handle_cron_command(
        self,
        raw: str,
        *,
        channel: str,
        chat_id: str,
    ) -> str:
        if self.cron_service is None:
            return "Cron service is not available."
        try:
            tokens = shlex.split(raw)
        except ValueError as exc:
            return f"Invalid cron command: {exc}"
        if len(tokens) == 1 or (len(tokens) > 1 and tokens[1].lower() == "help"):
            return (
                "Cron commands:\n"
                "/cron add every <seconds> <message>\n"
                "/cron add at <iso-datetime> <message>\n"
                '/cron add cron "<expr>" [tz=<iana>] <message>\n'
                "/cron list\n"
                "/cron remove <job_id>\n"
                "/cron run <job_id>"
            )

        action = tokens[1].lower()
        if action == "list":
            jobs = self.cron_service.list_jobs(include_disabled=True)
            if not jobs:
                return "No scheduled jobs."
            lines = []
            for job in jobs:
                state = "enabled" if job.enabled else "disabled"
                lines.append(f"- {job.name} (id: {job.id}, {job.schedule.kind}, {state})")
            return "Scheduled jobs:\n" + "\n".join(lines)

        if action in {"remove", "rm"}:
            if len(tokens) < 3:
                return "Usage: /cron remove <job_id>"
            return (
                f"Removed job {tokens[2]}"
                if self.cron_service.remove_job(tokens[2])
                else f"Job {tokens[2]} not found"
            )

        if action == "run":
            if len(tokens) < 3:
                return "Usage: /cron run <job_id>"
            ok = await self.cron_service.run_job(tokens[2], force=True)
            return f"Ran job {tokens[2]}" if ok else f"Job {tokens[2]} not found"

        if action == "add":
            return self._add_cron_job_from_tokens(tokens, channel=channel, chat_id=chat_id)

        return f"Unknown cron action: {action}"

    def _add_cron_job_from_tokens(
        self,
        tokens: list[str],
        *,
        channel: str,
        chat_id: str,
    ) -> str:
        assert self.cron_service is not None
        if len(tokens) < 5:
            return (
                "Usage: /cron add every <seconds> <message> | "
                "/cron add at <iso-datetime> <message> | "
                '/cron add cron "<expr>" [tz=<iana>] <message>'
            )
        schedule_kind = tokens[2].lower()
        delete_after_run = False
        try:
            if schedule_kind == "every":
                seconds = int(tokens[3])
                if seconds <= 0:
                    return "Error: seconds must be positive"
                schedule = SparkBotCronSchedule(kind="every", every_ms=seconds * 1000)
                message_tokens = tokens[4:]
            elif schedule_kind == "at":
                dt = datetime.fromisoformat(tokens[3])
                schedule = SparkBotCronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
                delete_after_run = True
                message_tokens = tokens[4:]
            elif schedule_kind == "cron":
                expr = tokens[3]
                tz = None
                message_start = 4
                if len(tokens) > 4 and tokens[4].startswith("tz="):
                    tz = tokens[4].split("=", 1)[1]
                    message_start = 5
                elif len(tokens) > 5 and tokens[4] == "--tz":
                    tz = tokens[5]
                    message_start = 6
                schedule = SparkBotCronSchedule(kind="cron", expr=expr, tz=tz)
                message_tokens = tokens[message_start:]
            else:
                return "Error: schedule kind must be every, at, or cron"
        except ValueError as exc:
            return f"Error: invalid schedule value ({exc})"
        message = " ".join(message_tokens).strip()
        if not message:
            return "Error: message is required"
        try:
            job = self.cron_service.add_job(
                name=message[:30],
                schedule=schedule,
                message=message,
                deliver=True,
                channel=channel,
                to=chat_id,
                delete_after_run=delete_after_run,
            )
        except ValueError as exc:
            return f"Error: {exc}"
        return f"Created job '{job.name}' (id: {job.id})"

    def _clear_session(self, chat_id: str) -> None:
        session_path = self.workspace / "sessions" / f"{chat_id or 'web'}.jsonl"
        try:
            session_path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            logger.exception("Failed to clear SparkBot session file '%s'", session_path)

    def _archive_session_for_new(self, chat_id: str, *, channel: str) -> bool:
        session_path = self.workspace / "sessions" / f"{chat_id or 'web'}.jsonl"
        if not session_path.exists():
            return True
        messages = self._read_archiveable_session_messages(session_path)
        if not messages:
            return True
        archive_path = self._memory_history_path()
        entry = self._format_session_archive(messages, chat_id=chat_id, channel=channel)
        try:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with archive_path.open("a", encoding="utf-8") as handle:
                handle.write(entry.rstrip() + "\n\n")
            return True
        except OSError:
            logger.exception("Failed to archive SparkBot session before /new: %s", session_path)
            return False

    def _memory_history_path(self) -> Path:
        if self.context.shared_memory_dir is not None:
            return self.context.shared_memory_dir / "SUMMARY.md"
        return self.workspace / "memory" / "HISTORY.md"

    @staticmethod
    def _read_archiveable_session_messages(session_path: Path) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        try:
            lines = session_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return messages
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("_type") == "metadata":
                continue
            role = str(item.get("role") or "").lower()
            content = item.get("content")
            if role in {"user", "assistant"} and content:
                messages.append(
                    {
                        "role": role,
                        "content": content,
                        "timestamp": item.get("timestamp") or "",
                    }
                )
        return messages

    @staticmethod
    def _format_session_archive(
        messages: list[dict[str, Any]],
        *,
        chat_id: str,
        channel: str,
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"[{now}] [SESSION ROLLOVER] {channel}:{chat_id or 'web'} ({len(messages)} messages)"
        ]
        for item in messages:
            role = str(item.get("role") or "message").upper()
            timestamp = str(item.get("timestamp") or "")[:16]
            content = item.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            content = content.strip()
            if len(content) > 2000:
                content = content[:2000] + "\n...[truncated]"
            prefix = f"{timestamp} " if timestamp else ""
            lines.append(f"{prefix}{role}: {content}")
        return "\n".join(lines)

    async def stop(self) -> None:
        self._stopping.set()
        await self.side_tasks.stop_all()
        await self.team.stop_all()
        await self.close_mcp()
        await self.bus.publish_inbound(
            SparkBotInboundMessage(
                channel="system",
                sender_id="system",
                chat_id="system",
                content="",
                metadata={"_stop": True},
            )
        )

    def _build_prompt(
        self,
        content: str,
        *,
        channel: str,
        chat_id: str,
        media: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        persona = self.config.persona or self.config.name
        return self.context.build_prompt(
            user_message=content,
            channel=channel,
            chat_id=chat_id,
            fallback_persona=persona,
            history=self._load_session_history(chat_id),
            media=media,
            attachments=attachments,
        )

    def _load_session_history(
        self, chat_id: str, *, limit: int | None = None
    ) -> list[dict[str, Any]]:
        effective_limit = self.session_history_limit if limit is None else max(0, int(limit))
        if effective_limit <= 0:
            return []
        session_path = self.workspace / "sessions" / f"{chat_id or 'web'}.jsonl"
        if not session_path.exists():
            return []
        messages: list[dict[str, Any]] = []
        try:
            lines = session_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("_type") == "metadata":
                continue
            role = str(item.get("role") or "").lower()
            if role in {"user", "assistant"} and item.get("content"):
                messages.append({"role": role, "content": item.get("content")})
        sliced = messages[-effective_limit:]
        for index, item in enumerate(sliced):
            if item.get("role") == "user":
                return sliced[index:]
        return sliced

    async def _complete_with_agent_tools(
        self,
        base_prompt: str,
        *,
        session_key: str,
        image_blocks: list[dict[str, Any]] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        await self._connect_mcp()
        prompt = f"{base_prompt}\n\n{self._agent_tool_instructions()}"
        records: list[dict[str, Any]] = []
        for _iteration in range(self.agent_tool_max_iterations):
            raw = await self._complete_prompt(prompt, image_blocks=image_blocks)
            calls = self._parse_agent_tool_calls(raw)
            if not calls:
                return self._agent_final_response(raw)
            if on_progress:
                names = ", ".join(call["name"] for call in calls)
                await on_progress(f"Using tools: {names}")
            new_records = await self._execute_agent_tool_calls(
                calls,
                session_key=session_key,
            )
            records.extend(new_records)
            prompt = self._agent_tool_followup_prompt(base_prompt, records)
        return (
            "I ran the requested tools, but stopped before a final model response "
            "to avoid an infinite tool loop.\n\n"
            f"{self._render_agent_tool_records(records)}"
        )

    async def _complete_prompt(
        self,
        prompt: str,
        *,
        image_blocks: list[dict[str, Any]] | None = None,
    ) -> Any:
        if not image_blocks:
            return await llm_complete(prompt=prompt, **self._llm_kwargs())
        messages = [
            {
                "role": "user",
                "content": [
                    *image_blocks,
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        return await llm_complete(prompt=prompt, messages=messages, **self._llm_kwargs())

    def _agent_tool_instructions(self) -> str:
        definitions = [
            {
                "name": definition.name,
                "description": definition.description,
                "parameters": {
                    parameter.name: {
                        "type": parameter.type,
                        "description": parameter.description,
                        "required": parameter.required,
                    }
                    for parameter in definition.parameters
                },
            }
            for definition in self.agent_tools.get_definitions()
        ]
        return (
            "## Available SparkBot Tools\n"
            "You can use workspace tools, NG learning tools, and SparkBot runtime "
            "tools for messaging, background work, scheduling, and nano-team "
            "coordination. If a tool is needed, return strict "
            "JSON only using this shape:\n"
            '{"tool_calls":[{"name":"read_file","arguments":{"path":"USER.md"}}]}\n'
            "If no tool is needed, answer normally. After tool results are provided, "
            "answer normally and do not repeat the same tool call unless more work is required.\n\n"
            f"Tools:\n{json.dumps(definitions, ensure_ascii=False, indent=2)}"
        )

    def _agent_tool_followup_prompt(
        self,
        base_prompt: str,
        records: list[dict[str, Any]],
    ) -> str:
        return (
            f"{base_prompt}\n\n"
            "## SparkBot Tool Results\n"
            f"{self._render_agent_tool_records(records)}\n\n"
            "Use these tool results to answer the user. If another tool call is required, "
            "return strict JSON with tool_calls again; otherwise answer normally."
        )

    def _parse_agent_tool_calls(self, raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, (dict, list)):
            parsed = raw
        else:
            parsed = extract_json_from_text(str(raw))
        if isinstance(parsed, dict):
            calls_raw = parsed.get("tool_calls") or parsed.get("toolCalls") or []
            if not calls_raw and (
                parsed.get("name") or parsed.get("tool") or parsed.get("tool_name")
            ):
                calls_raw = [parsed]
        elif isinstance(parsed, list):
            calls_raw = parsed
        else:
            return []

        calls: list[dict[str, Any]] = []
        for item in calls_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("tool") or item.get("tool_name") or "").strip()
            if not name:
                continue
            arguments = item.get("arguments") or item.get("args") or {}
            if not isinstance(arguments, dict):
                arguments = {"query": str(arguments)}
            calls.append({"name": name, "arguments": dict(arguments)})
            if len(calls) >= self.agent_tool_call_limit:
                break
        return calls

    @staticmethod
    def _agent_final_response(raw: Any) -> str:
        if isinstance(raw, dict):
            final = raw.get("final") or raw.get("answer") or raw.get("content")
            return str(final) if final is not None else json.dumps(raw, ensure_ascii=False)
        if isinstance(raw, list):
            return json.dumps(raw, ensure_ascii=False)
        text = str(raw)
        parsed = extract_json_from_text(text)
        if isinstance(parsed, dict):
            final = parsed.get("final") or parsed.get("answer") or parsed.get("content")
            if final is not None and not (parsed.get("tool_calls") or parsed.get("toolCalls")):
                return str(final)
        return text

    async def _execute_agent_tool_calls(
        self,
        calls: list[dict[str, Any]],
        *,
        session_key: str,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for call in calls:
            record = await self._execute_agent_tool_record(call, session_key=session_key)
            records.append(record)
            self._append_agent_tool_log(record)
        return records

    async def _execute_agent_tool_record(
        self,
        call: dict[str, Any],
        *,
        session_key: str,
    ) -> dict[str, Any]:
        tool_name = str(call.get("name") or "").strip()
        arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        started_at = _team_timestamp()
        try:
            result = await self.agent_tools.execute(tool_name, **arguments)
        except Exception as exc:
            return {
                "id": str(uuid.uuid4())[:8],
                "session_key": session_key,
                "tool": tool_name,
                "arguments": self._json_safe(arguments),
                "success": False,
                "content": f"Error: {tool_name or 'tool'} failed: {exc}",
                "error": str(exc),
                "sources": [],
                "metadata": {},
                "started_at": started_at,
                "finished_at": _team_timestamp(),
            }
        content = result.content if isinstance(result, ToolResult) else str(result)
        success = bool(result.success) if isinstance(result, ToolResult) else True
        return {
            "id": str(uuid.uuid4())[:8],
            "session_key": session_key,
            "tool": tool_name,
            "arguments": self._json_safe(arguments),
            "success": success,
            "content": content,
            "error": "" if success else content,
            "sources": self._json_safe(result.sources if isinstance(result, ToolResult) else []),
            "metadata": self._json_safe(result.metadata if isinstance(result, ToolResult) else {}),
            "started_at": started_at,
            "finished_at": _team_timestamp(),
        }

    @staticmethod
    def _render_agent_tool_records(records: list[dict[str, Any]]) -> str:
        if not records:
            return "No tools were run."
        sections: list[str] = []
        for record in records:
            status = "ok" if record.get("success", True) else "error"
            content = str(record.get("content") or "")
            if len(content) > 6000:
                content = f"{content[:6000]}\n...[truncated]"
            sections.append(f"### {record.get('tool') or 'tool'} ({status})\n{content}")
        return "\n\n".join(sections)

    def _append_agent_tool_log(self, record: dict[str, Any]) -> None:
        try:
            logs_dir = self.workspace / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            with (logs_dir / "agent_tools.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(self._json_safe(record), ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Failed to append SparkBot agent tool log")

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._json_safe(item) for item in value]
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            return str(value)


class SparkBotInstance:
    def __init__(self, bot_id: str, config: BotConfig) -> None:
        self.bot_id = bot_id
        self.config = config
        self.started_at = datetime.now().isoformat()
        self.last_reload_error: str | None = None
        self.notify_queue: asyncio.Queue[str] = asyncio.Queue()
        self.tasks: list[asyncio.Task] = []
        self.reload_lock = asyncio.Lock()
        self.channel_manager = None
        self.agent_loop = None
        self.heartbeat = None
        self.cron_service = None
        self.channel_bindings: dict[str, str] = {}

    @property
    def running(self) -> bool:
        return True

    def to_dict(
        self,
        *,
        include_secrets: bool = False,
        mask_secrets: bool = False,
    ) -> dict[str, Any]:
        if include_secrets:
            channels: Any = self.config.channels
        elif mask_secrets:
            channels = mask_channel_secrets(self.config.channels)
        else:
            channels = list(self.config.channels.keys())
        return {
            "bot_id": self.bot_id,
            "name": self.config.name,
            "description": self.config.description,
            "persona": self.config.persona,
            "channels": channels,
            "model": self.config.model,
            "auto_start": self.config.auto_start,
            **(
                {
                    "tools": self.config.tools.model_dump(mode="json", by_alias=True),
                    "agent": self.config.agent.model_dump(mode="json", by_alias=True),
                    "heartbeat": self.config.heartbeat.model_dump(mode="json", by_alias=True),
                }
                if include_secrets
                else {}
            ),
            "running": True,
            "started_at": self.started_at,
            "last_reload_error": self.last_reload_error,
        }


class SparkBotManager:
    _MERGEABLE_FIELDS = (
        "name",
        "description",
        "persona",
        "channels",
        "model",
        "auto_start",
        "tools",
        "agent",
        "heartbeat",
    )

    def __init__(self) -> None:
        self._path_service = get_path_service()
        self._bots: dict[str, SparkBotInstance] = {}

    def _base_dir(self) -> Path:
        path = self._path_service.get_memory_dir() / "SparkBots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _safe_bot_id(self, bot_id: str) -> str:
        safe = "".join(ch for ch in bot_id if ch.isalnum() or ch in {"-", "_"}).strip()
        return safe or "bot"

    def _bot_dir(self, bot_id: str, *, create: bool = True) -> Path:
        safe = self._safe_bot_id(bot_id)
        path = self._base_dir() / (safe or "bot")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _legacy_sparkbot_dirs(self) -> tuple[Path, ...]:
        root = self._path_service.get_memory_dir().parent
        return (root / "sparkbot", root / "SparkBot", root / "SparkBot")

    def _workspace_dir(self, bot_id: str) -> Path:
        path = self._bot_dir(bot_id) / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _safe_skill_name(self, name: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name).strip("-_")
        return safe or "skill"

    def _workspace_skill_dir(self, bot_id: str, skill_name: str) -> Path:
        path = self._workspace_dir(bot_id) / "skills" / self._safe_skill_name(skill_name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _config_path(self, bot_id: str) -> Path:
        return self._bot_dir(bot_id) / "config.yaml"

    def _cron_service_for(self, bot_id: str) -> SparkBotCronService:
        instance = self._bots.get(bot_id)
        if instance is not None and instance.cron_service is not None:
            return instance.cron_service
        return SparkBotCronService(store_path=self._bot_dir(bot_id) / "cron" / "jobs.json")

    async def ensure_bot_running(self, bot_id: str) -> SparkBotInstance:
        """Start a saved bot if needed so background services can actually run."""
        instance = self._bots.get(bot_id)
        if instance is not None:
            return instance
        cfg = self.load_bot_config(bot_id)
        if cfg is None:
            raise ValueError(f"Bot not found: {bot_id}")
        return await self.start_bot(bot_id, cfg, persist_auto_start=False)

    @staticmethod
    def _cron_job_to_dict(job: SparkBotCronJob) -> dict[str, Any]:
        return SparkBotCronService._job_to_json(job)

    def list_cron_jobs(
        self,
        bot_id: str,
        *,
        include_disabled: bool = True,
    ) -> dict[str, Any]:
        cron = self._cron_service_for(bot_id)
        return {
            "status": cron.status(),
            "jobs": [
                self._cron_job_to_dict(job)
                for job in cron.list_jobs(include_disabled=include_disabled)
            ],
        }

    async def add_cron_job(
        self,
        bot_id: str,
        *,
        name: str,
        schedule: SparkBotCronSchedule,
        message: str,
        deliver: bool = True,
        channel: str | None = "web",
        to: str | None = "web",
        delete_after_run: bool = False,
    ) -> dict[str, Any]:
        instance = await self.ensure_bot_running(bot_id)
        cron = instance.cron_service or self._cron_service_for(bot_id)
        job = cron.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            channel=channel,
            to=to,
            delete_after_run=delete_after_run,
        )
        return self._cron_job_to_dict(job)

    async def set_cron_job_enabled(
        self, bot_id: str, job_id: str, enabled: bool
    ) -> dict[str, Any] | None:
        cron = self._cron_service_for(bot_id)
        job = cron.enable_job(job_id, enabled=enabled)
        if job is not None and enabled:
            instance = await self.ensure_bot_running(bot_id)
            if instance.cron_service is not None and instance.cron_service is not cron:
                job = instance.cron_service.enable_job(job_id, enabled=True)
        return self._cron_job_to_dict(job) if job else None

    def remove_cron_job(self, bot_id: str, job_id: str) -> bool:
        return self._cron_service_for(bot_id).remove_job(job_id)

    async def run_cron_job(self, bot_id: str, job_id: str) -> bool:
        instance = self._bots.get(bot_id)
        cron = instance.cron_service if instance is not None else None
        if cron is None:
            raise RuntimeError("Bot must be running to execute a cron job.")
        return await cron.run_job(job_id, force=True)

    def _maybe_migrate_legacy(self, bot_id: str) -> None:
        target = self._bot_dir(bot_id)
        target_config = target / "config.yaml"
        if target_config.exists():
            return
        safe = self._safe_bot_id(bot_id)
        for legacy_root in self._legacy_sparkbot_dirs():
            for legacy_dir in (legacy_root / safe, legacy_root / "bots" / safe):
                if legacy_dir.is_dir() and (legacy_dir / "config.yaml").exists():
                    self._move_legacy_bot_dir(legacy_dir, target)
                    return
            for legacy_yaml in (
                legacy_root / "bots" / f"{safe}.yaml",
                legacy_root / f"{safe}.yaml",
            ):
                if legacy_yaml.is_file() and not target_config.exists():
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(legacy_yaml), str(target_config))
                    return

    @staticmethod
    def _move_legacy_bot_dir(legacy_dir: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for item in legacy_dir.iterdir():
            destination = target / item.name
            if item.name == "memory":
                destination = target / "workspace" / "memory"
                destination.parent.mkdir(parents=True, exist_ok=True)
            SparkBotManager._move_path_merge(item, destination)

    @staticmethod
    def _move_path_merge(source: Path, destination: Path) -> None:
        if not destination.exists():
            shutil.move(str(source), str(destination))
            return
        if source.is_dir() and destination.is_dir():
            for child in source.iterdir():
                SparkBotManager._move_path_merge(child, destination / child.name)
            try:
                source.rmdir()
            except OSError:
                pass

    def _ensure_bot_workspace(self, bot_id: str, config: BotConfig | None = None) -> None:
        self._maybe_migrate_legacy(bot_id)
        bot_dir = self._bot_dir(bot_id)
        for subdir in ("workspace/skills", "workspace/memory", "cron", "logs", "media"):
            (bot_dir / subdir).mkdir(parents=True, exist_ok=True)
        workspace = self._workspace_dir(bot_id)
        self._seed_builtin_skills(workspace)
        for filename, default in _DEFAULT_TEMPLATES.items():
            path = workspace / filename
            if path.exists():
                continue
            if filename == "SOUL.md" and config is not None and config.persona:
                path.write_text(config.persona, encoding="utf-8")
            else:
                path.write_text(default, encoding="utf-8")

    @staticmethod
    def _seed_builtin_skills(workspace: Path) -> None:
        if not _BUILTIN_SKILLS_DIR.exists():
            return
        target_root = workspace / "skills"
        target_root.mkdir(parents=True, exist_ok=True)
        for skill_dir in _BUILTIN_SKILLS_DIR.iterdir():
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            target = target_root / skill_dir.name
            if target.exists():
                continue
            try:
                shutil.copytree(skill_dir, target)
            except OSError:
                logger.exception("Failed to seed SparkBot built-in skill '%s'", skill_dir.name)

    def load_bot_config(self, bot_id: str) -> BotConfig | None:
        self._maybe_migrate_legacy(bot_id)
        path = self._config_path(bot_id)
        if not path.exists():
            return None
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return BotConfig(**data)
        except Exception:
            return None

    def save_bot_config(
        self,
        bot_id: str,
        config: BotConfig,
        *,
        auto_start: bool | None = None,
    ) -> None:
        self._maybe_migrate_legacy(bot_id)
        path = self._config_path(bot_id)
        tmp = path.with_suffix(".yaml.tmp")
        data = config.model_dump(mode="json")
        if auto_start is not None:
            data["auto_start"] = auto_start
            config.auto_start = auto_start
        tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        tmp.replace(path)
        self._ensure_bot_workspace(bot_id, config)
        if config.persona:
            (self._workspace_dir(bot_id) / "SOUL.md").write_text(config.persona, encoding="utf-8")

    def merge_bot_config(self, bot_id: str, overrides: dict[str, Any]) -> BotConfig:
        base = self.load_bot_config(bot_id) or BotConfig(name=bot_id)
        for key in self._MERGEABLE_FIELDS:
            if key in overrides and overrides[key] is not None:
                value = overrides[key]
                if key == "tools":
                    value = SparkBotToolsConfig.model_validate(value)
                elif key == "agent":
                    value = SparkBotAgentConfig.model_validate(value)
                elif key == "heartbeat":
                    value = SparkBotHeartbeatConfig.model_validate(value)
                setattr(base, key, value)
        return base

    def seed_competition_demo_bot(
        self,
        bot_id: str = COMPETITION_DEMO_BOT_ID,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Create or refresh the stable SparkBot used for the competition demo."""

        safe_bot_id = self._safe_bot_id(bot_id)
        existing = self.load_bot_config(safe_bot_id)
        created = existing is None
        if created or overwrite:
            self.save_bot_config(
                safe_bot_id,
                build_competition_demo_bot_config(),
                auto_start=False,
            )
        else:
            self._ensure_bot_workspace(safe_bot_id, existing)

        written: list[str] = []
        skipped: list[str] = []
        for filename, content in _COMPETITION_DEMO_WORKSPACE_FILES.items():
            current = self.read_bot_file(safe_bot_id, filename)
            default = _DEFAULT_TEMPLATES.get(filename, "")
            should_write = created or overwrite or current in {None, "", default}
            if should_write:
                self.write_bot_file(safe_bot_id, filename, content)
                written.append(filename)
            else:
                skipped.append(filename)

        return {
            "bot_id": safe_bot_id,
            "created": created,
            "overwritten": overwrite,
            "workspace_files": written,
            "skipped_files": skipped,
        }

    @staticmethod
    def _apply_agent_tool_runtime_defaults(config: BotConfig) -> None:
        exec_config = config.tools.exec_config
        if exec_config.timeout == 60:
            exec_config.timeout = 300
        if not exec_config.path_append:
            exec_config.path_append = str(Path(sys.executable).parent)

    async def start_bot(
        self,
        bot_id: str,
        config: BotConfig | None = None,
        *,
        persist_auto_start: bool = True,
    ) -> SparkBotInstance:
        existing = self._bots.get(bot_id)
        if existing is not None:
            return existing

        cfg = config or self.load_bot_config(bot_id) or BotConfig(name=bot_id)
        self._apply_agent_tool_runtime_defaults(cfg)
        self.save_bot_config(bot_id, cfg, auto_start=True if persist_auto_start else None)
        instance = SparkBotInstance(bot_id, cfg)
        bus = SparkBotMessageBus()
        canonical_key = f"bot:{bot_id}"
        agent_loop = SparkBotAgentLoop(
            config=cfg,
            bus=bus,
            workspace=self._workspace_dir(bot_id),
            default_session_key=canonical_key,
            shared_memory_dir=self._path_service.get_memory_dir(),
            record_exchange=(
                lambda channel, chat_id, user, assistant: self._record_bot_exchange(
                    bot_id,
                    chat_id,
                    user,
                    assistant,
                    channel=channel,
                )
            ),
        )
        instance.agent_loop = agent_loop
        try:
            instance.channel_manager = self._build_channel_manager(cfg, bus, bot_id=bot_id)
        except Exception as exc:
            logger.exception("Failed to initialise channels for SparkBot '%s'", bot_id)
            instance.channel_manager = None
            instance.last_reload_error = f"{type(exc).__name__}: {exc}"

        instance.tasks.append(asyncio.create_task(agent_loop.run(), name=f"SparkBot:{bot_id}:loop"))
        instance.tasks.append(
            asyncio.create_task(
                self._outbound_router(bot_id, bus, instance),
                name=f"SparkBot:{bot_id}:router",
            )
        )
        heartbeat = SparkBotHeartbeatService(
            workspace=self._workspace_dir(bot_id),
            model=cfg.model,
            on_execute=(
                lambda tasks: agent_loop.process_direct(
                    tasks,
                    session_key=canonical_key,
                    channel="heartbeat",
                    chat_id="heartbeat",
                )
            ),
            on_notify=instance.notify_queue.put,
            interval_s=max(1, int(cfg.heartbeat.interval_s or 1)),
            enabled=cfg.heartbeat.enabled,
        )
        instance.heartbeat = heartbeat
        await heartbeat.start()
        if heartbeat.task is not None:
            instance.tasks.append(heartbeat.task)
        cron_service = SparkBotCronService(
            store_path=self._bot_dir(bot_id) / "cron" / "jobs.json",
            on_job=lambda job: self._run_cron_job(bot_id, instance, job),
        )
        instance.cron_service = cron_service
        agent_loop.cron_service = cron_service
        await cron_service.start()
        if cron_service.task is not None:
            instance.tasks.append(cron_service.task)
        if instance.channel_manager is not None:
            for channel_name, channel in getattr(instance.channel_manager, "channels", {}).items():
                start = getattr(channel, "start", None)
                if callable(start):
                    instance.tasks.append(
                        asyncio.create_task(
                            start(),
                            name=f"SparkBot:{bot_id}:ch:{channel_name}",
                        )
                    )
        self._bots[bot_id] = instance
        return instance

    async def _outbound_router(
        self,
        bot_id: str,
        bus: SparkBotMessageBus,
        instance: SparkBotInstance,
    ) -> None:
        """Route outbound messages to channels, web notifications, and NG events."""
        try:
            from sparkweave.events.event_bus import Event, EventType, get_event_bus

            event_bus = get_event_bus()
            while True:
                msg = await bus.consume_outbound()
                metadata = msg.metadata or {}
                is_progress = bool(metadata.get("_progress"))
                try:
                    channels_config = ChannelsConfig(**instance.config.channels)
                except Exception:
                    channels_config = ChannelsConfig()

                if is_progress:
                    is_tool_hint = bool(metadata.get("_tool_hint"))
                    if is_tool_hint and not channels_config.send_tool_hints:
                        continue
                    if not is_tool_hint and not channels_config.send_progress:
                        continue

                channel = self._get_channel(instance.channel_manager, msg.channel)
                if channel is not None:
                    try:
                        await channel.send(msg)
                    except Exception:
                        logger.exception(
                            "Failed to send SparkBot message to channel '%s' for bot '%s'",
                            msg.channel,
                            bot_id,
                        )

                if not is_progress:
                    if msg.chat_id:
                        instance.channel_bindings[msg.channel] = msg.chat_id
                    await instance.notify_queue.put(msg.content or "")
                    await event_bus.publish(
                        Event(
                            type=EventType.CAPABILITY_COMPLETE,
                            task_id=f"SparkBot:{bot_id}:{msg.channel}:{msg.chat_id}",
                            user_input="",
                            agent_output=msg.content or "",
                            metadata={
                                "source": "SparkBot",
                                "bot_id": bot_id,
                                "channel": msg.channel,
                                "chat_id": msg.chat_id,
                            },
                        )
                    )
        except asyncio.CancelledError:
            return
        except Exception as exc:
            instance.last_reload_error = f"{type(exc).__name__}: {exc}"
            logger.exception("SparkBot outbound router failed for bot '%s'", bot_id)

    async def _run_cron_job(
        self,
        bot_id: str,
        instance: SparkBotInstance,
        job: SparkBotCronJob,
    ) -> str | None:
        agent_loop = getattr(instance, "agent_loop", None)
        process_direct = getattr(agent_loop, "process_direct", None)
        if not callable(process_direct):
            return None
        channel_name = job.payload.channel or "cron"
        chat_id = job.payload.to or "cron"
        cron_context_token = None
        set_cron_context = getattr(agent_loop, "set_agent_cron_context", None)
        reset_cron_context = getattr(agent_loop, "reset_agent_cron_context", None)
        if callable(set_cron_context):
            cron_context_token = set_cron_context(True)
        try:
            response = await process_direct(
                job.payload.message,
                session_key=f"bot:{bot_id}",
                channel=channel_name,
                chat_id=chat_id,
            )
        finally:
            if cron_context_token is not None and callable(reset_cron_context):
                reset_cron_context(cron_context_token)
        if response and job.payload.deliver:
            await instance.notify_queue.put(response)
            channel = self._get_channel(instance.channel_manager, channel_name)
            if channel is not None:
                await channel.send(
                    SparkBotOutboundMessage(
                        channel=channel_name,
                        chat_id=chat_id,
                        content=response,
                    )
                )
        return response

    @staticmethod
    def _get_channel(manager: Any, name: str) -> Any | None:
        if manager is None:
            return None
        get_channel = getattr(manager, "get_channel", None)
        if callable(get_channel):
            return get_channel(name)
        channels = getattr(manager, "channels", None)
        if isinstance(channels, dict):
            return channels.get(name)
        return None

    async def auto_start_bots(self) -> list[SparkBotInstance]:
        """Start bots whose saved config opts into autostart or active cron."""
        started: list[SparkBotInstance] = []
        for bot_id in sorted(self._discover_bot_ids()):
            cfg = self.load_bot_config(bot_id)
            if cfg and (cfg.auto_start or self._has_enabled_cron_jobs(bot_id)):
                started.append(
                    await self.start_bot(bot_id, cfg, persist_auto_start=cfg.auto_start)
                )
        return started

    def _has_enabled_cron_jobs(self, bot_id: str) -> bool:
        try:
            cron = self._cron_service_for(bot_id)
            return any(job.enabled for job in cron.list_jobs(include_disabled=True))
        except Exception:
            logger.exception("Failed to inspect SparkBot cron jobs for '%s'", bot_id)
            return False

    async def stop_all(self) -> None:
        for bot_id in list(self._bots):
            await self.stop_bot(bot_id)

    async def stop_bot(self, bot_id: str) -> bool:
        instance = self._bots.get(bot_id)
        if instance is None:
            return False
        await self._teardown_channel_listeners(instance, bot_id)
        heartbeat = getattr(instance, "heartbeat", None)
        stop_heartbeat = getattr(heartbeat, "stop", None)
        if callable(stop_heartbeat):
            stop_heartbeat()
        cron_service = getattr(instance, "cron_service", None)
        stop_cron = getattr(cron_service, "stop", None)
        if callable(stop_cron):
            stop_cron()
        stop = getattr(instance.agent_loop, "stop", None)
        if callable(stop):
            result = stop()
            if asyncio.iscoroutine(result):
                await result
        for task in list(instance.tasks):
            if not task.done():
                task.cancel()
        for task in list(instance.tasks):
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        self.save_bot_config(bot_id, instance.config, auto_start=False)
        self._bots.pop(bot_id, None)
        return True

    async def destroy_bot(self, bot_id: str) -> bool:
        await self.stop_bot(bot_id)
        bot_dir = self._bot_dir(bot_id, create=False)
        if not bot_dir.exists():
            return False
        for child in sorted(bot_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        bot_dir.rmdir()
        return True

    def get_bot(self, bot_id: str) -> SparkBotInstance | None:
        return self._bots.get(bot_id)

    def list_bots(self) -> list[dict[str, Any]]:
        bot_ids = self._discover_bot_ids()
        bot_ids.update(self._bots)
        result = []
        for bot_id in sorted(bot_ids):
            instance = self._bots.get(bot_id)
            if instance:
                result.append(instance.to_dict(mask_secrets=False))
                continue
            cfg = self.load_bot_config(bot_id)
            if cfg:
                result.append(
                    {
                        "bot_id": bot_id,
                        "name": cfg.name,
                        "description": cfg.description,
                        "persona": cfg.persona,
                        "channels": list(cfg.channels.keys()),
                        "model": cfg.model,
                        "auto_start": cfg.auto_start,
                        "running": False,
                        "started_at": None,
                        "last_reload_error": None,
                    }
                )
        return result

    def _discover_bot_ids(self) -> set[str]:
        ids: set[str] = set()
        for bot_id in self._discover_legacy_bot_ids():
            self._maybe_migrate_legacy(bot_id)
        for path in self._base_dir().glob("*/config.yaml"):
            if path.parent.name not in _RESERVED_BOT_DIRS:
                ids.add(path.parent.name)
        return ids

    def _discover_legacy_bot_ids(self) -> set[str]:
        ids: set[str] = set()
        for legacy_root in self._legacy_sparkbot_dirs():
            for path in legacy_root.glob("*/config.yaml"):
                if path.parent.name not in _RESERVED_BOT_DIRS and path.parent.name != "bots":
                    ids.add(path.parent.name)
            legacy_bots = legacy_root / "bots"
            for path in legacy_bots.glob("*/config.yaml"):
                if path.parent.name not in _RESERVED_BOT_DIRS:
                    ids.add(path.parent.name)
            for path in legacy_bots.glob("*.yaml"):
                ids.add(path.stem)
            for path in legacy_root.glob("*.yaml"):
                ids.add(path.stem)
        return ids

    def get_recent_active_bots(self, limit: int = 3) -> list[dict[str, Any]]:
        active: list[tuple[float, dict[str, Any]]] = []
        for bot_id in self._discover_bot_ids() | set(self._bots):
            history_files = [self._history_path(bot_id)]
            sessions_dir = self._workspace_dir(bot_id) / "sessions"
            if sessions_dir.exists():
                history_files.extend(sessions_dir.glob("*.jsonl"))
            existing = [path for path in history_files if path.exists()]
            if not existing:
                continue
            newest = max(existing, key=lambda path: path.stat().st_mtime)
            preview = self._last_history_preview(newest)
            cfg = self.load_bot_config(bot_id)
            instance = self._bots.get(bot_id)
            active.append(
                (
                    newest.stat().st_mtime,
                    {
                        "bot_id": bot_id,
                        "name": cfg.name if cfg else bot_id,
                        "running": bool(instance),
                        "last_message": preview[:200],
                        "updated_at": datetime.fromtimestamp(newest.stat().st_mtime).isoformat(),
                    },
                )
            )
        active.sort(key=lambda item: item[0], reverse=True)
        return [item for _mtime, item in active[:limit]]

    @staticmethod
    def _last_history_preview(path: Path) -> str:
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("_type") == "metadata":
                continue
            content = item.get("assistant") or item.get("content") or item.get("user")
            if content:
                return str(content)
        return ""

    async def reload_channels(self, bot_id: str) -> dict[str, Any]:
        instance = self._bots.get(bot_id)
        if not instance:
            raise RuntimeError("Bot not running")
        async with instance.reload_lock:
            await self._teardown_channel_listeners(instance, bot_id)
            try:
                bus = getattr(instance.agent_loop, "bus", None)
                channel_manager = self._build_channel_manager(
                    instance.config,
                    bus,
                    bot_id=bot_id,
                )
            except Exception as exc:
                instance.channel_manager = None
                instance.last_reload_error = f"{type(exc).__name__}: {exc}"
                raise

            instance.channel_manager = channel_manager
            instance.last_reload_error = None
            if channel_manager is not None:
                for channel_name, channel in getattr(channel_manager, "channels", {}).items():
                    start = getattr(channel, "start", None)
                    if callable(start):
                        task = asyncio.create_task(
                            start(),
                            name=f"SparkBot:{bot_id}:ch:{channel_name}",
                        )
                        instance.tasks.append(task)
            return {"bot_id": bot_id, "reloaded": True}

    def _build_channel_manager(
        self,
        config: BotConfig,
        bus: Any,
        *,
        bot_id: str,
    ) -> Any | None:
        """Build an NG-owned channel manager for enabled channel configs."""
        _ = bot_id
        if not config.channels:
            return None
        channels_config = ChannelsConfig(**config.channels)
        manager = SparkBotChannelManager(channels_config, bus)
        if not manager.channels:
            return None
        return manager

    async def _teardown_channel_listeners(
        self,
        instance: SparkBotInstance,
        bot_id: str,
    ) -> None:
        """Cancel channel listener tasks and stop the current channel manager."""
        prefix = f"SparkBot:{bot_id}:ch:"
        channel_tasks = [
            task for task in instance.tasks if (task.get_name() or "").startswith(prefix)
        ]
        for task in channel_tasks:
            if not task.done():
                task.cancel()
        for task in channel_tasks:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        instance.tasks = [task for task in instance.tasks if task not in channel_tasks]

        manager = instance.channel_manager
        stop_all = getattr(manager, "stop_all", None)
        if callable(stop_all):
            result = stop_all()
            if asyncio.iscoroutine(result):
                await result
        instance.channel_manager = None
        instance.channel_bindings.clear()

    def list_bot_skills(self, bot_id: str) -> list[dict[str, Any]]:
        self._ensure_bot_workspace(bot_id, self.load_bot_config(bot_id))
        workspace = self._workspace_dir(bot_id)
        loader = SparkBotSkillsLoader(workspace)
        skills: list[dict[str, Any]] = []
        for skill in loader.list_skills(filter_unavailable=False):
            metadata = loader.get_skill_metadata(skill["name"]) or {}
            nested = SparkBotSkillsLoader._nested_skill_metadata(metadata)
            item = {
                "name": skill["name"],
                "source": skill["source"],
                "path": skill["path"],
                "editable": skill["source"] == "workspace",
                "available": loader._check_requirements(metadata),
                "description": str(metadata.get("description") or skill["name"]),
                "always": bool(metadata.get("always") is True or nested.get("always") is True),
            }
            missing = loader._missing_requirements(metadata)
            if missing:
                item["missing_requirements"] = missing
            skills.append(item)
        return skills

    def read_bot_skill(self, bot_id: str, skill_name: str) -> dict[str, Any] | None:
        self._ensure_bot_workspace(bot_id, self.load_bot_config(bot_id))
        safe_name = self._safe_skill_name(skill_name)
        loader = SparkBotSkillsLoader(self._workspace_dir(bot_id))
        content = loader.load_skill(safe_name)
        if content is None:
            return None
        summaries = {item["name"]: item for item in self.list_bot_skills(bot_id)}
        summary = summaries.get(
            safe_name, {"name": safe_name, "source": "workspace", "editable": True}
        )
        return {**summary, "content": content}

    def write_bot_skill(self, bot_id: str, skill_name: str, content: str) -> dict[str, Any]:
        safe_name = self._safe_skill_name(skill_name)
        if not content.strip():
            raise ValueError("Skill content is required")
        if len(content) > MAX_SPARKBOT_SKILL_TEXT_CHARS:
            raise ValueError(f"Skill content exceeds {MAX_SPARKBOT_SKILL_TEXT_CHARS} characters")
        if "SKILL" not in content[:400].upper() and not content.lstrip().startswith("---"):
            content = f"# {safe_name}\n\n{content.strip()}\n"
        skill_dir = self._workspace_skill_dir(bot_id, safe_name)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        return self.read_bot_skill(bot_id, safe_name) or {
            "name": safe_name,
            "source": "workspace",
            "editable": True,
            "available": True,
            "description": safe_name,
            "content": content,
        }

    def upload_bot_skill(
        self,
        bot_id: str,
        *,
        filename: str,
        content: bytes,
        skill_name: str | None = None,
    ) -> dict[str, Any]:
        if not content:
            raise ValueError("Uploaded skill file is empty")
        if len(content) > MAX_SPARKBOT_SKILL_UPLOAD_BYTES:
            raise ValueError(
                f"Uploaded skill file exceeds {MAX_SPARKBOT_SKILL_UPLOAD_BYTES // 1024 // 1024}MB"
            )
        safe_filename = Path(filename or "skill.md").name
        if safe_filename.lower().endswith(".zip"):
            return self._upload_bot_skill_zip(
                bot_id,
                filename=safe_filename,
                content=content,
                skill_name=skill_name,
            )
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Skill file must be UTF-8 text or a zip archive") from exc
        if len(text) > MAX_SPARKBOT_SKILL_TEXT_CHARS:
            raise ValueError(f"Skill content exceeds {MAX_SPARKBOT_SKILL_TEXT_CHARS} characters")
        inferred_name = skill_name or Path(safe_filename).stem or "skill"
        if safe_filename.lower() == "skill.md":
            inferred_name = skill_name or "uploaded-skill"
        return self.write_bot_skill(bot_id, inferred_name, text)

    def _upload_bot_skill_zip(
        self,
        bot_id: str,
        *,
        filename: str,
        content: bytes,
        skill_name: str | None = None,
    ) -> dict[str, Any]:
        try:
            from io import BytesIO

            archive = zipfile.ZipFile(BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid skill zip archive") from exc

        members = [item for item in archive.infolist() if not item.is_dir()]
        skill_files = [
            PurePosixPath(item.filename)
            for item in members
            if PurePosixPath(item.filename).name == "SKILL.md"
        ]
        if not skill_files:
            raise ValueError("Skill zip must contain a SKILL.md file")
        skill_file = sorted(skill_files, key=lambda path: len(path.parts))[0]
        if len(members) > MAX_SPARKBOT_SKILL_ZIP_FILES:
            raise ValueError(
                f"Skill zip cannot contain more than {MAX_SPARKBOT_SKILL_ZIP_FILES} files"
            )
        total_uncompressed = 0
        for item in members:
            if item.flag_bits & 0x1:
                raise ValueError("Encrypted skill zip entries are not supported")
            total_uncompressed += int(item.file_size or 0)
            if (
                PurePosixPath(item.filename) == skill_file
                and item.file_size > MAX_SPARKBOT_SKILL_TEXT_CHARS
            ):
                raise ValueError(
                    f"Skill content exceeds {MAX_SPARKBOT_SKILL_TEXT_CHARS} characters"
                )
            if item.file_size > MAX_SPARKBOT_SKILL_ZIP_FILE_BYTES:
                raise ValueError(
                    f"Skill zip file '{Path(item.filename).name}' exceeds "
                    f"{MAX_SPARKBOT_SKILL_ZIP_FILE_BYTES // 1024 // 1024}MB"
                )
        if total_uncompressed > MAX_SPARKBOT_SKILL_ZIP_TOTAL_BYTES:
            raise ValueError(
                "Skill zip uncompressed size exceeds "
                f"{MAX_SPARKBOT_SKILL_ZIP_TOTAL_BYTES // 1024 // 1024}MB"
            )
        prefix_parts = skill_file.parts[:-1]
        inferred_name = skill_name or (prefix_parts[-1] if prefix_parts else Path(filename).stem)
        safe_name = self._safe_skill_name(inferred_name)
        target_dir = self._workspace_skill_dir(bot_id, safe_name)
        target_root = target_dir.resolve()

        for item in members:
            source_path = PurePosixPath(item.filename)
            if prefix_parts and source_path.parts[: len(prefix_parts)] != prefix_parts:
                continue
            rel_parts = (
                source_path.parts[len(prefix_parts) :] if prefix_parts else source_path.parts
            )
            if not rel_parts or any(
                part in {"", ".", ".."} or "\\" in part or ":" in part for part in rel_parts
            ):
                continue
            target = target_dir.joinpath(*rel_parts)
            target_resolved = target.resolve()
            if target_resolved != target_root and target_root not in target_resolved.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))

        skill_md = target_dir / "SKILL.md"
        if not skill_md.exists():
            raise ValueError("Skill zip extraction did not produce SKILL.md")
        return self.read_bot_skill(bot_id, safe_name) or {
            "name": safe_name,
            "source": "workspace",
            "editable": True,
            "available": True,
            "description": safe_name,
            "content": skill_md.read_text(encoding="utf-8"),
        }

    def read_all_bot_files(self, bot_id: str) -> dict[str, str]:
        self._ensure_bot_workspace(bot_id, self.load_bot_config(bot_id))
        workspace = self._workspace_dir(bot_id)
        return {
            filename: (workspace / filename).read_text(encoding="utf-8")
            if (workspace / filename).exists()
            else ""
            for filename in _EDITABLE_WORKSPACE_FILES
        }

    def read_bot_file(self, bot_id: str, filename: str) -> str | None:
        if filename not in _EDITABLE_WORKSPACE_FILES:
            return None
        self._ensure_bot_workspace(bot_id, self.load_bot_config(bot_id))
        path = self._workspace_dir(bot_id) / filename
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_bot_file(self, bot_id: str, filename: str, content: str) -> bool:
        if filename not in _EDITABLE_WORKSPACE_FILES:
            return False
        if len(content) > MAX_SPARKBOT_WORKSPACE_FILE_CHARS:
            raise ValueError(
                f"Workspace file content exceeds {MAX_SPARKBOT_WORKSPACE_FILE_CHARS} characters"
            )
        path = self._workspace_dir(bot_id) / filename
        path.write_text(content, encoding="utf-8")
        if filename == "SOUL.md":
            cfg = self.load_bot_config(bot_id)
            if cfg is not None:
                cfg.persona = content
                self.save_bot_config(bot_id, cfg)
        return True

    def _history_path(self, bot_id: str) -> Path:
        return self._bot_dir(bot_id) / "history.jsonl"

    @staticmethod
    def _write_session_messages(
        session_path: Path,
        *,
        key: str,
        channel: str,
        messages: list[dict[str, Any]],
        timestamp: str,
    ) -> None:
        existing: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        if session_path.exists():
            for line in session_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("_type") == "metadata":
                    metadata = item
                else:
                    existing.append(item)

        created_at = str(metadata.get("created_at") or timestamp)
        last_consolidated = int(metadata.get("last_consolidated") or 0)
        metadata_line = {
            "_type": "metadata",
            "key": key,
            "channel": channel,
            "created_at": created_at,
            "updated_at": timestamp,
            "metadata": metadata.get("metadata")
            if isinstance(metadata.get("metadata"), dict)
            else {},
            "last_consolidated": last_consolidated,
        }
        with session_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for item in [*existing, *messages]:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _record_bot_exchange(
        self,
        bot_id: str,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        *,
        channel: str = "web",
    ) -> None:
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "channel": channel,
            "chat_id": chat_id,
            "user": user_content,
            "assistant": assistant_content,
        }
        with self._history_path(bot_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        sessions_dir = self._workspace_dir(bot_id) / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_path = sessions_dir / f"{chat_id or 'web'}.jsonl"
        self._write_session_messages(
            session_path,
            key=f"{channel}:{chat_id or 'web'}",
            channel=channel,
            timestamp=timestamp,
            messages=[
                {
                    "timestamp": timestamp,
                    "role": "user",
                    "content": user_content,
                    "channel": channel,
                    "chat_id": chat_id,
                },
                {
                    "timestamp": timestamp,
                    "role": "assistant",
                    "content": assistant_content,
                    "channel": channel,
                    "chat_id": chat_id,
                },
            ],
        )

    def get_bot_history(self, bot_id: str, limit: int = 100) -> list[dict[str, Any]]:
        candidates = [self._history_path(bot_id)]
        sessions_dir = self._workspace_dir(bot_id) / "sessions"
        if sessions_dir.exists():
            candidates.extend(sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime))
        items: list[dict[str, Any]] = []
        for path in candidates:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("_type") == "metadata":
                    continue
                if {"user", "assistant"} & item.keys() or item.get("role") in {"user", "assistant"}:
                    items.append(item)
        return items[-limit:]

    async def send_message(
        self,
        bot_id: str,
        content: str,
        *,
        chat_id: str = "web",
        media: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        on_progress: Any | None = None,
    ) -> str:
        instance = self._bots.get(bot_id)
        if not instance:
            raise RuntimeError("Bot not running")
        process_direct = getattr(instance.agent_loop, "process_direct", None)
        if callable(process_direct):
            response = await process_direct(
                content,
                session_key=f"bot:{bot_id}",
                channel="web",
                chat_id=chat_id,
                media=media,
                attachments=attachments,
                on_progress=on_progress,
            )
        else:
            if on_progress:
                await on_progress("Thinking...")
            prompt = (
                f"Persona:\n{instance.config.persona or instance.config.name}\n\nUser:\n{content}"
            )
            try:
                response = await llm_complete(prompt=prompt, model=instance.config.model)
            except Exception:
                response = f"{instance.config.name}: {content}"
            self._record_bot_exchange(bot_id, chat_id, content, response)

        if instance.channel_manager and response:
            for channel_name, bound_chat_id in list(instance.channel_bindings.items()):
                channel = self._get_channel(instance.channel_manager, channel_name)
                if channel is None:
                    continue
                try:
                    await channel.send(
                        SparkBotOutboundMessage(
                            channel=channel_name,
                            chat_id=bound_chat_id,
                            content=response,
                        )
                    )
                except Exception:
                    logger.exception(
                        "Failed to forward SparkBot web reply to channel '%s' for bot '%s'",
                        channel_name,
                        bot_id,
                    )
        return response

    def list_souls(self) -> list[dict[str, Any]]:
        self._seed_default_souls()
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self._souls_dir().glob("*.json")
        ]

    def get_soul(self, soul_id: str) -> dict[str, Any] | None:
        self._seed_default_souls()
        path = self._souls_dir() / f"{soul_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def create_soul(self, soul_id: str, name: str, content: str) -> dict[str, Any]:
        soul = {"id": soul_id, "name": name, "content": content}
        (self._souls_dir() / f"{soul_id}.json").write_text(
            json.dumps(soul, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return soul

    def update_soul(
        self,
        soul_id: str,
        name: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any] | None:
        soul = self.get_soul(soul_id)
        if soul is None:
            return None
        if name is not None:
            soul["name"] = name
        if content is not None:
            soul["content"] = content
        (self._souls_dir() / f"{soul_id}.json").write_text(
            json.dumps(soul, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return soul

    def delete_soul(self, soul_id: str) -> bool:
        path = self._souls_dir() / f"{soul_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def _souls_dir(self) -> Path:
        path = self._base_dir() / "souls"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _seed_default_souls(self) -> None:
        souls_dir = self._souls_dir()
        for soul in _DEFAULT_SOULS:
            path = souls_dir / f"{soul['id']}.json"
            if path.exists():
                continue
            path.write_text(
                json.dumps(soul, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


_manager: SparkBotManager | None = None


def get_sparkbot_manager() -> SparkBotManager:
    global _manager
    if _manager is None:
        _manager = SparkBotManager()
    return _manager


__all__ = [
    "BotConfig",
    "ChannelConfigModel",
    "ChannelsConfig",
    "COMPETITION_DEMO_BOT_ID",
    "DISCORD_API_BASE",
    "DISCORD_MAX_ATTACHMENT_BYTES",
    "DISCORD_MAX_MESSAGE_LEN",
    "DiscordChannel",
    "DiscordConfig",
    "DingTalkChannel",
    "DingTalkConfig",
    "EmailChannel",
    "EmailConfig",
    "FeishuChannel",
    "FeishuConfig",
    "MatrixChannel",
    "MatrixConfig",
    "MochatChannel",
    "MochatConfig",
    "MochatGroupRule",
    "MochatMentionConfig",
    "QQChannel",
    "QQConfig",
    "SlackChannel",
    "SlackConfig",
    "SlackDMConfig",
    "TELEGRAM_MAX_MESSAGE_LEN",
    "TELEGRAM_REPLY_CONTEXT_MAX_LEN",
    "TelegramChannel",
    "TelegramConfig",
    "WebConfig",
    "SparkBotAgentLoop",
    "SparkBotChannel",
    "SparkBotChannelManager",
    "SparkBotCronTool",
    "SparkBotCronJob",
    "SparkBotCronJobState",
    "SparkBotCronPayload",
    "SparkBotCronSchedule",
    "SparkBotCronService",
    "SparkBotCronStore",
    "SparkBotHeartbeatService",
    "SparkBotInboundMessage",
    "SparkBotInstance",
    "SparkBotManager",
    "SparkBotMessageTool",
    "SparkBotMessageBus",
    "SparkBotMCPServerConfig",
    "SparkBotOutboundMessage",
    "SparkBotSkillsLoader",
    "SparkBotSideTaskManager",
    "SparkBotSideTaskRecord",
    "SparkBotSpawnTool",
    "SparkBotTeamMail",
    "SparkBotTeamManager",
    "SparkBotTeamMember",
    "SparkBotTeamRuntime",
    "SparkBotTeamState",
    "SparkBotTeamTask",
    "SparkBotTeamTool",
    "SparkBotTeamWorkerTool",
    "SparkBotToolsConfig",
    "SparkBotWorkspaceContext",
    "WecomChannel",
    "WecomConfig",
    "WhatsAppChannel",
    "WhatsAppConfig",
    "_channel_config_model",
    "_is_secret_field",
    "_sparkbot_media_dir",
    "build_competition_demo_bot_config",
    "discover_builtin_channels",
    "get_sparkbot_manager",
    "mask_channel_secrets",
]
