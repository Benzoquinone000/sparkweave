"""NG-owned SparkBot manager with the legacy API surface."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
import html
import imaplib
import json
import logging
import mimetypes
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import smtplib
import ssl
import sys
import threading
import time
from typing import Any, Awaitable, Callable, Literal
import unicodedata
from urllib.parse import unquote, urlparse
import uuid

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
import yaml

from sparkweave.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.paths import get_path_service
from sparkweave.tools.registry import ToolRegistry, get_tool_registry
from sparkweave.sparkbot.mcp import connect_mcp_servers
from sparkweave.sparkbot.media import build_image_content_blocks
from sparkweave.sparkbot.tools import build_sparkbot_agent_tool_registry
from sparkweave.utils.json_parser import extract_json_from_text

logger = logging.getLogger(__name__)

_EDITABLE_WORKSPACE_FILES = ("SOUL.md", "USER.md", "TOOLS.md", "AGENTS.md", "HEARTBEAT.md")
_RESERVED_BOT_DIRS = {"souls", "_souls", "workspace", "media", "cron", "logs", "sessions"}
_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parents[1] / "sparkbot" / "skills"
_PROMPT_FILE_MAX_CHARS = 12_000
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
DISCORD_MAX_MESSAGE_LEN = 2000
TELEGRAM_MAX_MESSAGE_LEN = 4000
TELEGRAM_REPLY_CONTEXT_MAX_LEN = TELEGRAM_MAX_MESSAGE_LEN

_DEFAULT_TEMPLATES = {
    "SOUL.md": "# Soul\n\nI am SparkBot, a personal learning companion.\n",
    "USER.md": "# User\n\nKeep track of the learner's preferences, goals, and context here.\n",
    "TOOLS.md": "# Tools\n\nUse SparkWeave capabilities, knowledge bases, and local files responsibly.\n",
    "AGENTS.md": "# Agent Notes\n\nWork carefully, explain clearly, and preserve user privacy.\n",
    "HEARTBEAT.md": "# Heartbeat\n\nReview reminders and proactive learning opportunities here.\n",
}

_DEFAULT_SOULS = [
    {
        "id": "default-sparkbot",
        "name": "Default SparkBot",
        "content": (
            "# Soul\n\nI am SparkBot, a personal learning companion.\n\n"
            "I explain clearly, remember useful context, and adapt to the learner."
        ),
    },
    {
        "id": "math-tutor",
        "name": "Math Tutor",
        "content": (
            "# Soul\n\nI am a patient math tutor.\n\n"
            "I break problems into steps, ask good questions, and verify final answers."
        ),
    },
    {
        "id": "research-helper",
        "name": "Research Helper",
        "content": (
            "# Soul\n\nI help explore research topics in depth.\n\n"
            "I decompose broad questions, compare evidence, and cite sources when possible."
        ),
    },
]


def _is_secret_field(name: str) -> bool:
    lowered = name.lower()
    return any(
        hint in lowered
        for hint in ("token", "password", "secret", "api_key", "apikey", "encrypt_key")
    )


def mask_channel_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_field(str(key)) and isinstance(item, str) and item:
                masked[key] = "***"
            else:
                masked[key] = mask_channel_secrets(item)
        return masked
    if isinstance(value, list):
        return [mask_channel_secrets(item) for item in value]
    return value


class SparkBotConfigModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SparkBotMCPServerConfig(SparkBotConfigModel):
    """MCP server connection config accepted from old and NG bot configs."""

    type: Literal["stdio", "sse", "streamableHttp"] | None = None
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    tool_timeout: int = 30
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])


class SparkBotWebSearchConfig(SparkBotConfigModel):
    """Web search config accepted from old SparkBot configs."""

    provider: str = "brave"
    api_key: str = ""
    base_url: str = ""
    max_results: int = 5


class SparkBotWebToolsConfig(SparkBotConfigModel):
    """Web tool config accepted from old SparkBot configs."""

    proxy: str | None = None
    search: SparkBotWebSearchConfig = Field(default_factory=SparkBotWebSearchConfig)
    fetch_max_chars: int = 50_000


class SparkBotExecToolConfig(SparkBotConfigModel):
    """Shell exec config accepted from old SparkBot configs."""

    timeout: int = 60
    path_append: str = ""


class SparkBotToolsConfig(SparkBotConfigModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    web: SparkBotWebToolsConfig = Field(default_factory=SparkBotWebToolsConfig)
    exec_config: SparkBotExecToolConfig = Field(
        default_factory=SparkBotExecToolConfig,
        alias="exec",
        serialization_alias="exec",
    )
    restrict_to_workspace: bool = True
    mcp_servers: dict[str, SparkBotMCPServerConfig] = Field(default_factory=dict)


class SparkBotAgentConfig(SparkBotConfigModel):
    max_tool_iterations: int = 4
    tool_call_limit: int = 5
    max_tokens: int = 8192
    context_window_tokens: int = 65_536
    temperature: float = 0.1
    reasoning_effort: str | None = None
    memory_window: int | None = Field(default=None, exclude=True)
    team_max_workers: int = 5
    team_worker_max_iterations: int = 25


class SparkBotHeartbeatConfig(SparkBotConfigModel):
    enabled: bool = True
    interval_s: int = 30 * 60


class BotConfig(SparkBotConfigModel):
    name: str
    description: str = ""
    persona: str = ""
    channels: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    auto_start: bool = False
    tools: SparkBotToolsConfig = Field(default_factory=SparkBotToolsConfig)
    agent: SparkBotAgentConfig = Field(default_factory=SparkBotAgentConfig)
    heartbeat: SparkBotHeartbeatConfig = Field(default_factory=SparkBotHeartbeatConfig)


class ChannelConfigModel(SparkBotConfigModel):
    pass


class TelegramConfig(ChannelConfigModel):
    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    proxy: str | None = None
    reply_to_message: bool = False
    group_policy: Literal["open", "mention"] = "mention"


class SlackDMConfig(ChannelConfigModel):
    enabled: bool = True
    policy: str = "open"
    allow_from: list[str] = Field(default_factory=list)
    webhook_url: str = ""


class SlackConfig(ChannelConfigModel):
    enabled: bool = False
    mode: str = "socket"
    webhook_path: str = "/slack/events"
    bot_token: str = ""
    app_token: str = ""
    user_token_read_only: bool = True
    reply_in_thread: bool = True
    react_emoji: str = "eyes"
    allow_from: list[str] = Field(default_factory=list)
    group_policy: str = "mention"
    group_allow_from: list[str] = Field(default_factory=list)
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class DiscordConfig(ChannelConfigModel):
    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    guild_id: str = ""
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377
    group_policy: Literal["mention", "open"] = "mention"


class DingTalkConfig(ChannelConfigModel):
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    allow_from: list[str] = Field(default_factory=list)


class EmailConfig(ChannelConfigModel):
    enabled: bool = False
    consent_granted: bool = False
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""
    auto_reply_enabled: bool = True
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)


class FeishuConfig(ChannelConfigModel):
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    react_emoji: str = "THUMBSUP"
    group_policy: Literal["open", "mention"] = "mention"


class MatrixConfig(ChannelConfigModel):
    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token: str = ""
    user_id: str = ""
    device_id: str = ""
    e2ee_enabled: bool = True
    sync_stop_grace_seconds: int = 2
    max_media_bytes: int = 20 * 1024 * 1024
    allow_from: list[str] = Field(default_factory=list)
    group_policy: Literal["open", "mention", "allowlist"] = "open"
    group_allow_from: list[str] = Field(default_factory=list)
    allow_room_mentions: bool = False


class MochatMentionConfig(ChannelConfigModel):
    require_in_groups: bool = False


class MochatGroupRule(ChannelConfigModel):
    require_mention: bool = False


class MochatConfig(ChannelConfigModel):
    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"
    reply_delay_ms: int = 120000


class QQConfig(ChannelConfigModel):
    enabled: bool = False
    app_id: str = ""
    secret: str = ""
    allow_from: list[str] = Field(default_factory=list)
    msg_format: Literal["plain", "markdown"] = "plain"


class WecomConfig(ChannelConfigModel):
    enabled: bool = False
    bot_id: str = ""
    secret: str = ""
    allow_from: list[str] = Field(default_factory=list)
    welcome_message: str = ""


class WhatsAppConfig(ChannelConfigModel):
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")

    send_progress: bool = True
    send_tool_hints: bool = False
    transcription_api_key: str = ""
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    qq: QQConfig = Field(default_factory=QQConfig)
    wecom: WecomConfig = Field(default_factory=WecomConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)


@dataclass(slots=True)
class SparkBotInboundMessage:
    channel: str
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_key: str | None = None


@dataclass(slots=True)
class SparkBotOutboundMessage:
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SparkBotMessageBus:
    """Small NG-owned bus that mirrors the old SparkBot inbound/outbound queues."""

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[SparkBotInboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[SparkBotOutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: SparkBotInboundMessage) -> None:
        await self.inbound.put(msg)

    async def consume_inbound(self) -> SparkBotInboundMessage:
        return await self.inbound.get()

    async def publish_outbound(self, msg: SparkBotOutboundMessage) -> None:
        await self.outbound.put(msg)

    async def consume_outbound(self) -> SparkBotOutboundMessage:
        return await self.outbound.get()


def _channel_config_model(channel_cls: type) -> type[BaseModel] | None:
    expected = channel_cls.__name__.replace("Channel", "") + "Config"
    candidate = globals().get(expected)
    if isinstance(candidate, type) and issubclass(candidate, BaseModel):
        return candidate
    return None


def _split_message(content: str, max_len: int) -> list[str]:
    if not content:
        return []
    if len(content) <= max_len:
        return [content]
    chunks: list[str] = []
    remaining = content
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        candidate = remaining[:max_len]
        split_at = candidate.rfind("\n")
        if split_at <= 0:
            split_at = candidate.rfind(" ")
        if split_at <= 0:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()
    return chunks


def _sparkbot_media_dir(channel: str) -> Path:
    path = get_path_service().project_root / "data" / "sparkbot" / "media" / channel
    path.mkdir(parents=True, exist_ok=True)
    return path


def _strip_markdown_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _render_markdown_table_box(table_lines: list[str]) -> str:
    def display_width(value: str) -> int:
        return sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in value)

    rows: list[list[str]] = []
    has_separator = False
    for line in table_lines:
        cells = [_strip_markdown_inline(cell) for cell in line.strip().strip("|").split("|")]
        if all(re.match(r"^:?-+:?$", cell) for cell in cells if cell):
            has_separator = True
            continue
        rows.append(cells)
    if not rows or not has_separator:
        return "\n".join(table_lines)

    columns = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (columns - len(row)))
    widths = [max(display_width(row[column]) for row in rows) for column in range(columns)]

    def render_row(cells: list[str]) -> str:
        return "  ".join(
            f"{cell}{' ' * (width - display_width(cell))}"
            for cell, width in zip(cells, widths)
        )

    output = [render_row(rows[0]), "  ".join("-" * width for width in widths)]
    output.extend(render_row(row) for row in rows[1:])
    return "\n".join(output)


def _markdown_to_telegram_html(text: str) -> str:
    if not text:
        return ""

    code_blocks: list[str] = []

    def save_code_block(match: re.Match) -> str:
        code_blocks.append(match.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    lines = text.split("\n")
    rebuilt: list[str] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*\|.+\|", lines[index]):
            table: list[str] = []
            while index < len(lines) and re.match(r"^\s*\|.+\|", lines[index]):
                table.append(lines[index])
                index += 1
            box = _render_markdown_table_box(table)
            if box != "\n".join(table):
                code_blocks.append(box)
                rebuilt.append(f"\x00CB{len(code_blocks) - 1}\x00")
            else:
                rebuilt.extend(table)
            continue
        rebuilt.append(lines[index])
        index += 1
    text = "\n".join(rebuilt)

    inline_codes: list[str] = []

    def save_inline_code(match: re.Match) -> str:
        inline_codes.append(match.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"^[-*]\s+", "- ", text, flags=re.MULTILINE)

    for index, code in enumerate(inline_codes):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{index}\x00", f"<code>{escaped}</code>")
    for index, code in enumerate(code_blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{index}\x00", f"<pre><code>{escaped}</code></pre>")
    return text


class SparkBotChannel:
    name = "base"
    display_name = "Base"
    transcription_api_key = ""

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        model = _channel_config_model(type(self))
        self.config = model.model_validate(config) if model is not None else config
        self.bus = bus
        self.sent_messages: list[SparkBotOutboundMessage] = []
        self._running = False
        self._stop_event = asyncio.Event()

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        model = _channel_config_model(cls)
        if model is None:
            return {"enabled": False}
        return model().model_dump(mode="json", by_alias=False)

    async def start(self) -> None:
        self._running = True
        self._stop_event.clear()
        await self._stop_event.wait()

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        self.sent_messages.append(msg)

    async def transcribe_audio(self, file_path: str | Path) -> str:
        """Transcribe an audio file via the NG transcription provider."""
        if not self.transcription_api_key:
            return ""
        try:
            from sparkweave.sparkbot.transcription import GroqTranscriptionProvider

            provider = GroqTranscriptionProvider(api_key=self.transcription_api_key)
            return await provider.transcribe(file_path)
        except Exception:
            logger.exception("Audio transcription failed for SparkBot channel '%s'", self.name)
            return ""

    def is_allowed(self, sender_id: str) -> bool:
        allow_from = getattr(self.config, "allow_from", None)
        if allow_from is None:
            return True
        if not allow_from:
            return False
        return "*" in allow_from or str(sender_id) in {str(item) for item in allow_from}

    async def _handle_message(
        self,
        *,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        session_key: str | None = None,
    ) -> bool:
        if not self.is_allowed(sender_id):
            return False
        resolved_media = self._normalize_media(media=media, attachments=attachments)
        await self.bus.publish_inbound(
            SparkBotInboundMessage(
                channel=self.name,
                sender_id=str(sender_id),
                chat_id=str(chat_id),
                content=content,
                media=resolved_media,
                attachments=attachments or [],
                metadata=metadata or {},
                session_key=session_key,
            )
        )
        return True

    @staticmethod
    def _normalize_media(
        *,
        media: list[str] | None,
        attachments: list[dict[str, Any]] | None,
    ) -> list[str]:
        result: list[str] = []
        for item in media or []:
            text = str(item).strip()
            if text:
                result.append(text)
        for attachment in attachments or []:
            if not isinstance(attachment, dict):
                continue
            raw = (
                attachment.get("path")
                or attachment.get("file_path")
                or attachment.get("filePath")
                or attachment.get("url")
                or attachment.get("uri")
                or attachment.get("file")
            )
            text = str(raw or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    @property
    def is_running(self) -> bool:
        return self._running


class TelegramChannel(SparkBotChannel):
    name = "telegram"
    display_name = "Telegram"

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._app: Any | None = None
        self._chat_ids: dict[str, int] = {}
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._media_group_buffers: dict[str, dict[str, Any]] = {}
        self._media_group_tasks: dict[str, asyncio.Task] = {}
        self._message_threads: dict[tuple[str, int], int] = {}
        self._bot_user_id: int | None = None
        self._bot_username: str | None = None

    def is_allowed(self, sender_id: str) -> bool:
        if super().is_allowed(sender_id):
            return True
        allow_from = getattr(self.config, "allow_from", [])
        if not allow_from or "*" in allow_from:
            return False
        sender_text = str(sender_id)
        if sender_text.count("|") != 1:
            return False
        sid, username = sender_text.split("|", 1)
        return (sid.isdigit() and sid in allow_from) or (bool(username) and username in allow_from)

    async def start(self) -> None:
        try:
            from telegram import BotCommand
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
            from telegram.request import HTTPXRequest
        except Exception:
            logger.warning(
                "Telegram channel requires python-telegram-bot; using in-memory channel"
            )
            await super().start()
            return
        if not self.config.token:
            logger.error("Telegram bot token not configured")
            await super().start()
            return

        self._running = True
        self._stop_event.clear()
        request = HTTPXRequest(
            connection_pool_size=16,
            pool_timeout=5.0,
            connect_timeout=30.0,
            read_timeout=30.0,
            proxy=self.config.proxy if self.config.proxy else None,
        )
        builder = Application.builder().token(self.config.token).request(request).get_updates_request(request)
        self._app = builder.build()
        self._app.add_error_handler(self._on_error)
        self._app.add_handler(CommandHandler("start", self._on_start))
        for command in ("new", "stop", "team", "btw", "restart"):
            self._app.add_handler(CommandHandler(command, self._forward_command))
        self._app.add_handler(CommandHandler("help", self._on_help))
        self._app.add_handler(
            MessageHandler(
                (
                    filters.TEXT
                    | filters.PHOTO
                    | filters.VOICE
                    | filters.AUDIO
                    | filters.Document.ALL
                )
                & ~filters.COMMAND,
                self._on_message,
            )
        )

        await self._app.initialize()
        await self._app.start()
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("new", "Start a new conversation"),
            BotCommand("stop", "Stop the current task"),
            BotCommand("team", "Start or control nano team mode"),
            BotCommand("btw", "Run an async side task"),
            BotCommand("help", "Show available commands"),
            BotCommand("restart", "Restart the bot"),
        ]
        try:
            await self._app.bot.set_my_commands(commands)
        except Exception:
            logger.exception("Failed to register Telegram commands")
        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)
        for task in self._media_group_tasks.values():
            task.cancel()
        self._media_group_tasks.clear()
        self._media_group_buffers.clear()
        if self._app is not None:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    @staticmethod
    def _get_media_type(path: str) -> str:
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if suffix in {"jpg", "jpeg", "png", "gif", "webp"}:
            return "photo"
        if suffix == "ogg":
            return "voice"
        if suffix in {"mp3", "m4a", "wav", "aac"}:
            return "audio"
        return "document"

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._app is None:
            logger.warning("Telegram bot not running; outbound message was not sent")
            await super().send(msg)
            return
        if not msg.metadata.get("_progress", False):
            self._stop_typing(msg.chat_id)
        try:
            chat_id = int(msg.chat_id)
        except (TypeError, ValueError):
            logger.error("Invalid Telegram chat_id: %s", msg.chat_id)
            return

        reply_to_message_id = msg.reply_to or msg.metadata.get("message_id")
        message_thread_id = msg.metadata.get("message_thread_id")
        if message_thread_id is None and reply_to_message_id is not None:
            try:
                reply_key = int(reply_to_message_id)
            except (TypeError, ValueError):
                reply_key = None
            if reply_key is not None:
                message_thread_id = self._message_threads.get((msg.chat_id, reply_key))
        thread_kwargs = {"message_thread_id": message_thread_id} if message_thread_id is not None else {}
        reply_parameters = self._build_reply_parameters(reply_to_message_id)

        sent_any = False
        for media_path in msg.media or []:
            if await self._send_media(chat_id, media_path, reply_parameters, thread_kwargs):
                sent_any = True

        is_progress = bool(msg.metadata.get("_progress", False))
        if msg.content and msg.content != "[empty message]":
            for chunk in _split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
                if is_progress:
                    await self._send_text(chat_id, chunk, reply_parameters, thread_kwargs)
                else:
                    await self._send_with_streaming(chat_id, chunk, reply_parameters, thread_kwargs)
                sent_any = True
        if sent_any:
            self.sent_messages.append(msg)

    @staticmethod
    def _build_reply_parameters(message_id: Any) -> Any | None:
        if not message_id:
            return None
        try:
            from telegram import ReplyParameters
        except Exception:
            return {"message_id": message_id, "allow_sending_without_reply": True}
        return ReplyParameters(
            message_id=message_id,
            allow_sending_without_reply=True,
        )

    async def _send_media(
        self,
        chat_id: int,
        media_path: str,
        reply_parameters: Any | None,
        thread_kwargs: dict[str, Any],
    ) -> bool:
        try:
            media_type = self._get_media_type(media_path)
            sender = {
                "photo": self._app.bot.send_photo,
                "voice": self._app.bot.send_voice,
                "audio": self._app.bot.send_audio,
            }.get(media_type, self._app.bot.send_document)
            parameter_name = (
                "photo"
                if media_type == "photo"
                else media_type if media_type in {"voice", "audio"} else "document"
            )
            with Path(media_path).open("rb") as handle:
                await sender(
                    chat_id=chat_id,
                    **{parameter_name: handle},
                    reply_parameters=reply_parameters,
                    **thread_kwargs,
                )
            return True
        except Exception:
            filename = Path(media_path).name
            logger.exception("Failed to send Telegram media '%s'", media_path)
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=f"[Failed to send: {filename}]",
                reply_parameters=reply_parameters,
                **thread_kwargs,
            )
            return False

    async def _send_text(
        self,
        chat_id: int,
        text: str,
        reply_parameters: Any | None = None,
        thread_kwargs: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=_markdown_to_telegram_html(text),
                parse_mode="HTML",
                reply_parameters=reply_parameters,
                **(thread_kwargs or {}),
            )
        except Exception:
            logger.exception("Telegram HTML send failed; falling back to plain text")
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_parameters=reply_parameters,
                **(thread_kwargs or {}),
            )

    async def _send_with_streaming(
        self,
        chat_id: int,
        text: str,
        reply_parameters: Any | None = None,
        thread_kwargs: dict[str, Any] | None = None,
    ) -> None:
        draft = getattr(self._app.bot, "send_message_draft", None)
        if callable(draft):
            draft_id = int(time.time() * 1000) % (2**31)
            try:
                step = max(len(text) // 8, 40)
                for index in range(step, len(text), step):
                    await draft(chat_id=chat_id, draft_id=draft_id, text=text[:index])
                    await asyncio.sleep(0.04)
                await draft(chat_id=chat_id, draft_id=draft_id, text=text)
                await asyncio.sleep(0.15)
            except Exception:
                logger.debug("Telegram draft streaming failed", exc_info=True)
        await self._send_text(chat_id, text, reply_parameters, thread_kwargs)

    async def _on_start(self, update: Any, context: Any) -> None:
        if not getattr(update, "message", None) or not getattr(update, "effective_user", None):
            return
        first_name = getattr(update.effective_user, "first_name", "")
        await update.message.reply_text(
            f"Hi {first_name}! I'm SparkBot.\n\n"
            "Send me a message and I'll respond.\n"
            "Type /help to see available commands."
        )

    async def _on_help(self, update: Any, context: Any) -> None:
        if not getattr(update, "message", None):
            return
        await update.message.reply_text(
            "SparkBot commands:\n"
            "/new - Start a new conversation\n"
            "/stop - Stop the current task\n"
            "/restart - Restart the bot\n"
            "/help - Show available commands"
        )

    @staticmethod
    def _sender_id(user: Any) -> str:
        sid = str(user.id)
        username = getattr(user, "username", None)
        return f"{sid}|{username}" if username else sid

    @staticmethod
    def _derive_topic_session_key(message: Any) -> str | None:
        message_thread_id = getattr(message, "message_thread_id", None)
        chat = getattr(message, "chat", None)
        if getattr(chat, "type", None) == "private" or message_thread_id is None:
            return None
        return f"telegram:{message.chat_id}:topic:{message_thread_id}"

    @staticmethod
    def _build_message_metadata(message: Any, user: Any) -> dict[str, Any]:
        reply = getattr(message, "reply_to_message", None)
        return {
            "message_id": message.message_id,
            "user_id": user.id,
            "username": getattr(user, "username", None),
            "first_name": getattr(user, "first_name", None),
            "is_group": getattr(message.chat, "type", None) != "private",
            "message_thread_id": getattr(message, "message_thread_id", None),
            "is_forum": bool(getattr(message.chat, "is_forum", False)),
            "reply_to_message_id": getattr(reply, "message_id", None) if reply else None,
        }

    @staticmethod
    def _extract_reply_context(message: Any) -> str | None:
        reply = getattr(message, "reply_to_message", None)
        if reply is None:
            return None
        text = getattr(reply, "text", None) or getattr(reply, "caption", None) or ""
        if len(text) > TELEGRAM_REPLY_CONTEXT_MAX_LEN:
            text = text[:TELEGRAM_REPLY_CONTEXT_MAX_LEN] + "..."
        return f"[Reply to: {text}]" if text else None

    async def _download_message_media(
        self,
        message: Any,
        *,
        add_failure_content: bool = False,
    ) -> tuple[list[str], list[str]]:
        media_file = None
        media_type = None
        if getattr(message, "photo", None):
            media_file = message.photo[-1]
            media_type = "image"
        elif getattr(message, "voice", None):
            media_file = message.voice
            media_type = "voice"
        elif getattr(message, "audio", None):
            media_file = message.audio
            media_type = "audio"
        elif getattr(message, "document", None):
            media_file = message.document
            media_type = "file"
        elif getattr(message, "video", None):
            media_file = message.video
            media_type = "video"
        elif getattr(message, "video_note", None):
            media_file = message.video_note
            media_type = "video"
        elif getattr(message, "animation", None):
            media_file = message.animation
            media_type = "animation"
        if media_file is None or self._app is None:
            return [], []
        try:
            file = await self._app.bot.get_file(media_file.file_id)
            extension = self._get_extension(
                str(media_type),
                getattr(media_file, "mime_type", None),
                getattr(media_file, "file_name", None),
            )
            unique_id = getattr(media_file, "file_unique_id", media_file.file_id)
            file_path = _sparkbot_media_dir("telegram") / f"{unique_id}{extension}"
            await file.download_to_drive(str(file_path))
            path_text = str(file_path)
            if media_type in {"voice", "audio"}:
                transcription = await self.transcribe_audio(file_path)
                if transcription:
                    return [path_text], [f"[transcription: {transcription}]"]
            return [path_text], [f"[{media_type}: {path_text}]"]
        except Exception:
            logger.exception("Failed to download Telegram media")
            if add_failure_content:
                return [], [f"[{media_type}: download failed]"]
            return [], []

    async def _ensure_bot_identity(self) -> tuple[int | None, str | None]:
        if self._bot_user_id is not None or self._bot_username is not None:
            return self._bot_user_id, self._bot_username
        if self._app is None:
            return None, None
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        return self._bot_user_id, self._bot_username

    @staticmethod
    def _has_mention_entity(
        text: str,
        entities: Any,
        bot_username: str,
        bot_id: int | None,
    ) -> bool:
        handle = f"@{bot_username}".lower()
        for entity in entities or []:
            entity_type = getattr(entity, "type", None)
            if entity_type == "text_mention":
                user = getattr(entity, "user", None)
                if user is not None and bot_id is not None and getattr(user, "id", None) == bot_id:
                    return True
                continue
            if entity_type != "mention":
                continue
            offset = getattr(entity, "offset", None)
            length = getattr(entity, "length", None)
            if offset is not None and length is not None and text[offset : offset + length].lower() == handle:
                return True
        return handle in text.lower()

    async def _is_group_message_for_bot(self, message: Any) -> bool:
        if message.chat.type == "private" or self.config.group_policy == "open":
            return True
        bot_id, bot_username = await self._ensure_bot_identity()
        if bot_username:
            if self._has_mention_entity(
                getattr(message, "text", None) or "",
                getattr(message, "entities", None),
                bot_username,
                bot_id,
            ):
                return True
            if self._has_mention_entity(
                getattr(message, "caption", None) or "",
                getattr(message, "caption_entities", None),
                bot_username,
                bot_id,
            ):
                return True
        reply_user = getattr(getattr(message, "reply_to_message", None), "from_user", None)
        return bool(bot_id and reply_user and getattr(reply_user, "id", None) == bot_id)

    def _remember_thread_context(self, message: Any) -> None:
        message_thread_id = getattr(message, "message_thread_id", None)
        if message_thread_id is None:
            return
        self._message_threads[(str(message.chat_id), message.message_id)] = message_thread_id
        if len(self._message_threads) > 1000:
            self._message_threads.pop(next(iter(self._message_threads)))

    async def _forward_command(self, update: Any, context: Any) -> None:
        if not getattr(update, "message", None) or not getattr(update, "effective_user", None):
            return
        message = update.message
        user = update.effective_user
        self._remember_thread_context(message)
        await self._handle_message(
            sender_id=self._sender_id(user),
            chat_id=str(message.chat_id),
            content=message.text or "",
            metadata=self._build_message_metadata(message, user),
            session_key=self._derive_topic_session_key(message),
        )

    async def _on_message(self, update: Any, context: Any) -> None:
        if not getattr(update, "message", None) or not getattr(update, "effective_user", None):
            return
        message = update.message
        user = update.effective_user
        sender_id = self._sender_id(user)
        chat_id = str(message.chat_id)
        self._remember_thread_context(message)
        self._chat_ids[sender_id] = message.chat_id

        if not await self._is_group_message_for_bot(message):
            return

        content_parts: list[str] = []
        media_paths: list[str] = []
        if getattr(message, "text", None):
            content_parts.append(message.text)
        if getattr(message, "caption", None):
            content_parts.append(message.caption)

        current_media, current_parts = await self._download_message_media(
            message,
            add_failure_content=True,
        )
        media_paths.extend(current_media)
        content_parts.extend(current_parts)

        reply = getattr(message, "reply_to_message", None)
        if reply is not None:
            reply_context = self._extract_reply_context(message)
            reply_media, reply_parts = await self._download_message_media(reply)
            if reply_media:
                media_paths = reply_media + media_paths
            tag = reply_context or (f"[Reply to: {reply_parts[0]}]" if reply_parts else None)
            if tag:
                content_parts.insert(0, tag)

        content = "\n".join(content_parts) if content_parts else "[empty message]"
        metadata = self._build_message_metadata(message, user)
        session_key = self._derive_topic_session_key(message)

        media_group_id = getattr(message, "media_group_id", None)
        if media_group_id:
            key = f"{chat_id}:{media_group_id}"
            if key not in self._media_group_buffers:
                self._media_group_buffers[key] = {
                    "sender_id": sender_id,
                    "chat_id": chat_id,
                    "contents": [],
                    "media": [],
                    "metadata": metadata,
                    "session_key": session_key,
                }
                self._start_typing(chat_id)
            buffer = self._media_group_buffers[key]
            if content and content != "[empty message]":
                buffer["contents"].append(content)
            buffer["media"].extend(media_paths)
            if key not in self._media_group_tasks:
                self._media_group_tasks[key] = asyncio.create_task(self._flush_media_group(key))
            return

        self._start_typing(chat_id)
        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media_paths,
            metadata=metadata,
            session_key=session_key,
        )

    async def _flush_media_group(self, key: str) -> None:
        try:
            await asyncio.sleep(0.6)
            buffer = self._media_group_buffers.pop(key, None)
            if not buffer:
                return
            content = "\n".join(buffer["contents"]) or "[empty message]"
            await self._handle_message(
                sender_id=buffer["sender_id"],
                chat_id=buffer["chat_id"],
                content=content,
                media=list(dict.fromkeys(buffer["media"])),
                metadata=buffer["metadata"],
                session_key=buffer.get("session_key"),
            )
        finally:
            self._media_group_tasks.pop(key, None)

    def _start_typing(self, chat_id: str) -> None:
        self._stop_typing(chat_id)
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _stop_typing(self, chat_id: str) -> None:
        task = self._typing_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, chat_id: str) -> None:
        try:
            while self._app is not None:
                await self._app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.debug("Telegram typing indicator stopped", exc_info=True)

    async def _on_error(self, update: object, context: Any) -> None:
        logger.error("Telegram error: %s", getattr(context, "error", None))

    @staticmethod
    def _get_extension(
        media_type: str,
        mime_type: str | None,
        filename: str | None = None,
    ) -> str:
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]
        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "file": ""}
        if ext := type_map.get(media_type, ""):
            return ext
        if filename:
            return "".join(Path(filename).suffixes)
        return ""


class SlackChannel(SparkBotChannel):
    name = "slack"
    display_name = "Slack"

    _TABLE_RE = re.compile(r"(?m)^\|.*\|$(?:\n\|[\s:|-]*\|$)(?:\n\|.*\|$)*")
    _CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
    _INLINE_CODE_RE = re.compile(r"`[^`]+`")
    _LEFTOVER_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
    _LEFTOVER_HEADER_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
    _BARE_URL_RE = re.compile(r"(?<![|<])(https?://\S+)")

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._web_client: Any | None = None
        self._socket_client: Any | None = None
        self._bot_user_id: str | None = None

    async def start(self) -> None:
        try:
            from slack_sdk.socket_mode.websockets import SocketModeClient
            from slack_sdk.web.async_client import AsyncWebClient
        except Exception as exc:
            raise RuntimeError("Slack channel requires slack-sdk.") from exc
        if not self.config.bot_token or not self.config.app_token:
            logger.error("Slack bot/app token not configured")
            return
        if self.config.mode != "socket":
            logger.error("Unsupported Slack mode: %s", self.config.mode)
            return

        self._running = True
        self._stop_event.clear()
        self._web_client = AsyncWebClient(token=self.config.bot_token)
        self._socket_client = SocketModeClient(
            app_token=self.config.app_token,
            web_client=self._web_client,
        )
        self._socket_client.socket_mode_request_listeners.append(self._on_socket_request)
        try:
            auth = await self._web_client.auth_test()
            self._bot_user_id = str(auth.get("user_id") or "") or None
        except Exception:
            logger.exception("Slack auth_test failed")

        await self._socket_client.connect()
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._socket_client is not None:
            close = getattr(self._socket_client, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._socket_client = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._web_client is None:
            logger.warning("Slack client not running; outbound message was not sent")
            return
        slack_meta = msg.metadata.get("slack", {}) if msg.metadata else {}
        thread_ts = slack_meta.get("thread_ts")
        channel_type = slack_meta.get("channel_type")
        thread_ts_param = thread_ts if thread_ts and channel_type != "im" else None

        if msg.content or not (msg.media or []):
            await self._web_client.chat_postMessage(
                channel=msg.chat_id,
                text=self._to_mrkdwn(msg.content) if msg.content else " ",
                thread_ts=thread_ts_param,
            )
        for media_path in msg.media or []:
            await self._web_client.files_upload_v2(
                channel=msg.chat_id,
                file=media_path,
                thread_ts=thread_ts_param,
            )
        self.sent_messages.append(msg)

    async def _on_socket_request(self, client: Any, req: Any) -> None:
        if getattr(req, "type", None) != "events_api":
            return
        response = self._socket_mode_response(getattr(req, "envelope_id", ""))
        if response is not None:
            await client.send_socket_mode_response(response)

        payload = getattr(req, "payload", None) or {}
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        event_type = event.get("type")
        if event_type not in {"message", "app_mention"}:
            return
        if event.get("subtype"):
            return
        sender_id = event.get("user")
        chat_id = event.get("channel")
        if not sender_id or not chat_id:
            return
        if self._bot_user_id and sender_id == self._bot_user_id:
            return

        text = str(event.get("text") or "")
        if event_type == "message" and self._bot_user_id and f"<@{self._bot_user_id}>" in text:
            return
        channel_type = str(event.get("channel_type") or "")
        if not self._is_allowed(str(sender_id), str(chat_id), channel_type):
            return
        if channel_type != "im" and not self._should_respond_in_channel(
            str(event_type),
            text,
            str(chat_id),
        ):
            return

        stripped_text = self._strip_bot_mention(text)
        thread_ts = event.get("thread_ts")
        if self.config.reply_in_thread and not thread_ts:
            thread_ts = event.get("ts")

        try:
            if self._web_client is not None and event.get("ts"):
                await self._web_client.reactions_add(
                    channel=chat_id,
                    name=self.config.react_emoji,
                    timestamp=event.get("ts"),
                )
        except Exception:
            logger.debug("Slack reactions_add failed", exc_info=True)

        session_key = f"slack:{chat_id}:{thread_ts}" if thread_ts and channel_type != "im" else None
        await self._handle_message(
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=stripped_text,
            metadata={
                "slack": {
                    "event": event,
                    "thread_ts": thread_ts,
                    "channel_type": channel_type,
                },
            },
            session_key=session_key,
        )

    @staticmethod
    def _socket_mode_response(envelope_id: str) -> Any | None:
        try:
            from slack_sdk.socket_mode.response import SocketModeResponse
        except Exception:
            return {"envelope_id": envelope_id}
        return SocketModeResponse(envelope_id=envelope_id)

    def _is_allowed(self, sender_id: str, chat_id: str, channel_type: str) -> bool:
        if channel_type == "im":
            if not self.config.dm.enabled:
                return False
            if self.config.dm.policy == "allowlist":
                return sender_id in self.config.dm.allow_from
            return True
        if self.config.group_policy == "allowlist":
            return chat_id in self.config.group_allow_from
        return True

    def _should_respond_in_channel(self, event_type: str, text: str, chat_id: str) -> bool:
        if self.config.group_policy == "open":
            return True
        if self.config.group_policy == "mention":
            if event_type == "app_mention":
                return True
            return self._bot_user_id is not None and f"<@{self._bot_user_id}>" in text
        if self.config.group_policy == "allowlist":
            return chat_id in self.config.group_allow_from
        return False

    def _strip_bot_mention(self, text: str) -> str:
        if not text or not self._bot_user_id:
            return text
        return re.sub(rf"<@{re.escape(self._bot_user_id)}>\s*", "", text).strip()

    @classmethod
    def _to_mrkdwn(cls, text: str) -> str:
        if not text:
            return ""
        text = cls._TABLE_RE.sub(cls._convert_table, text)
        try:
            from slackify_markdown import slackify_markdown
        except Exception:
            converted = text
        else:
            converted = slackify_markdown(text)
        return cls._fixup_mrkdwn(converted)

    @classmethod
    def _fixup_mrkdwn(cls, text: str) -> str:
        code_blocks: list[str] = []

        def save_code(match: re.Match) -> str:
            code_blocks.append(match.group(0))
            return f"\x00CB{len(code_blocks) - 1}\x00"

        text = cls._CODE_FENCE_RE.sub(save_code, text)
        text = cls._INLINE_CODE_RE.sub(save_code, text)
        text = cls._LEFTOVER_BOLD_RE.sub(r"*\1*", text)
        text = cls._LEFTOVER_HEADER_RE.sub(r"*\1*", text)
        text = cls._BARE_URL_RE.sub(lambda match: match.group(0).replace("&amp;", "&"), text)
        for index, block in enumerate(code_blocks):
            text = text.replace(f"\x00CB{index}\x00", block)
        return text.rstrip()

    @staticmethod
    def _convert_table(match: re.Match) -> str:
        lines = [line.strip() for line in match.group(0).strip().splitlines() if line.strip()]
        if len(lines) < 2:
            return match.group(0)
        headers = [header.strip() for header in lines[0].strip("|").split("|")]
        start = 2 if re.fullmatch(r"[|\s:\-]+", lines[1]) else 1
        rows: list[str] = []
        for line in lines[start:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells = (cells + [""] * len(headers))[: len(headers)]
            parts = [f"**{headers[index]}**: {cells[index]}" for index in range(len(headers)) if cells[index]]
            if parts:
                rows.append(" | ".join(parts))
        return "\n".join(rows)


class DiscordChannel(SparkBotChannel):
    name = "discord"
    display_name = "Discord"

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._ws: Any | None = None
        self._seq: int | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._http: Any | None = None
        self._bot_user_id: str | None = None

    async def start(self) -> None:
        if not self.config.token:
            logger.error("Discord bot token not configured")
            return
        try:
            import httpx
            import websockets
        except Exception as exc:
            raise RuntimeError("Discord channel requires httpx and websockets.") from exc

        self._running = True
        self._stop_event.clear()
        self._http = httpx.AsyncClient(timeout=30.0)
        while self._running:
            try:
                async with websockets.connect(self.config.gateway_url) as ws:
                    self._ws = ws
                    await self._gateway_loop()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Discord gateway connection failed")
                if self._running:
                    await asyncio.sleep(5)
            finally:
                self._ws = None

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()
        if self._ws is not None:
            close = getattr(self._ws, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._ws = None
        if self._http is not None:
            aclose = getattr(self._http, "aclose", None)
            if callable(aclose):
                result = aclose()
                if asyncio.iscoroutine(result):
                    await result
            self._http = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._http is None:
            logger.warning("Discord HTTP client not initialized; outbound message was not sent")
            return

        url = f"{DISCORD_API_BASE}/channels/{msg.chat_id}/messages"
        headers = {"Authorization": f"Bot {self.config.token}"}
        try:
            sent_media = False
            failed_media: list[str] = []
            for media_path in msg.media or []:
                if await self._send_file(url, headers, media_path, reply_to=msg.reply_to):
                    sent_media = True
                else:
                    failed_media.append(Path(media_path).name)

            chunks = _split_message(msg.content or "", DISCORD_MAX_MESSAGE_LEN)
            if not chunks and failed_media and not sent_media:
                chunks = _split_message(
                    "\n".join(f"[attachment: {name} - send failed]" for name in failed_media),
                    DISCORD_MAX_MESSAGE_LEN,
                )
            for index, chunk in enumerate(chunks):
                payload: dict[str, Any] = {"content": chunk}
                if index == 0 and msg.reply_to and not sent_media:
                    payload["message_reference"] = {"message_id": msg.reply_to}
                    payload["allowed_mentions"] = {"replied_user": False}
                if not await self._send_payload(url, headers, payload):
                    break
            if chunks or sent_media:
                self.sent_messages.append(msg)
        finally:
            await self._stop_typing(msg.chat_id)

    async def _send_payload(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> bool:
        for attempt in range(3):
            try:
                response = await self._http.post(url, headers=headers, json=payload)
                if getattr(response, "status_code", None) == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return True
            except Exception:
                if attempt == 2:
                    logger.exception("Error sending Discord payload")
                    return False
                await asyncio.sleep(1)
        return False

    async def _send_file(
        self,
        url: str,
        headers: dict[str, str],
        file_path: str,
        reply_to: str | None = None,
    ) -> bool:
        path = Path(file_path)
        if not path.is_file() or path.stat().st_size > DISCORD_MAX_ATTACHMENT_BYTES:
            return False

        payload_json: dict[str, Any] = {}
        if reply_to:
            payload_json["message_reference"] = {"message_id": reply_to}
            payload_json["allowed_mentions"] = {"replied_user": False}

        for attempt in range(3):
            try:
                with path.open("rb") as handle:
                    response = await self._http.post(
                        url,
                        headers=headers,
                        files={"files[0]": (path.name, handle, "application/octet-stream")},
                        data={
                            "payload_json": json.dumps(payload_json)
                        } if payload_json else {},
                    )
                if getattr(response, "status_code", None) == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return True
            except Exception:
                if attempt == 2:
                    logger.exception("Error sending Discord file '%s'", path.name)
                    return False
                await asyncio.sleep(1)
        return False

    async def _gateway_loop(self) -> None:
        if self._ws is None:
            return
        async for raw in self._ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from Discord gateway")
                continue
            if not isinstance(data, dict):
                continue

            op = data.get("op")
            event_type = data.get("t")
            seq = data.get("s")
            payload = data.get("d") if isinstance(data.get("d"), dict) else {}
            if seq is not None:
                self._seq = int(seq)

            if op == 10:
                await self._start_heartbeat(float(payload.get("heartbeat_interval", 45000)) / 1000)
                await self._identify()
            elif op == 0 and event_type == "READY":
                user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
                self._bot_user_id = str(user.get("id") or "") or None
            elif op == 0 and event_type == "MESSAGE_CREATE":
                await self._handle_message_create(payload)
            elif op in {7, 9}:
                break

    async def _identify(self) -> None:
        if self._ws is None:
            return
        payload = {
            "op": 2,
            "d": {
                "token": self.config.token,
                "intents": self.config.intents,
                "properties": {
                    "os": "sparkweave-ng",
                    "browser": "sparkweave-ng",
                    "device": "sparkweave-ng",
                },
            },
        }
        await self._ws.send(json.dumps(payload, ensure_ascii=False))

    async def _start_heartbeat(self, interval_s: float) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()

        async def heartbeat_loop() -> None:
            while self._running and self._ws is not None:
                try:
                    await self._ws.send(json.dumps({"op": 1, "d": self._seq}))
                except Exception:
                    logger.exception("Discord heartbeat failed")
                    return
                await asyncio.sleep(interval_s)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _handle_message_create(self, payload: dict[str, Any]) -> None:
        author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
        if author.get("bot"):
            return
        sender_id = str(author.get("id") or "")
        channel_id = str(payload.get("channel_id") or "")
        content = str(payload.get("content") or "")
        guild_id = payload.get("guild_id")
        if not sender_id or not channel_id:
            return
        if not self.is_allowed(sender_id):
            return
        if guild_id is not None and not self._should_respond_in_group(payload, content):
            return

        content_parts = [content] if content else []
        media_paths: list[str] = []
        for attachment in payload.get("attachments") or []:
            if not isinstance(attachment, dict):
                continue
            path = await self._download_attachment(attachment)
            if path:
                media_paths.append(str(path))
                content_parts.append(f"[attachment: {path}]")
            else:
                filename = attachment.get("filename") or "attachment"
                content_parts.append(f"[attachment: {filename} - download failed]")

        reply_to = (payload.get("referenced_message") or {}).get("id")
        await self._start_typing(channel_id)
        await self._handle_message(
            sender_id=sender_id,
            chat_id=channel_id,
            content="\n".join(part for part in content_parts if part) or "[empty message]",
            media=media_paths,
            metadata={
                "message_id": str(payload.get("id") or ""),
                "guild_id": guild_id,
                "reply_to": reply_to,
            },
        )

    async def _download_attachment(self, attachment: dict[str, Any]) -> Path | None:
        url = attachment.get("url")
        if not url or self._http is None:
            return None
        size = int(attachment.get("size") or 0)
        if size and size > DISCORD_MAX_ATTACHMENT_BYTES:
            return None
        try:
            filename = str(attachment.get("filename") or "attachment").replace("/", "_")
            file_id = str(attachment.get("id") or "file")
            target = _sparkbot_media_dir("discord") / f"{file_id}_{filename}"
            response = await self._http.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
            return target
        except Exception:
            logger.exception("Failed to download Discord attachment")
            return None

    def _should_respond_in_group(self, payload: dict[str, Any], content: str) -> bool:
        if self.config.group_policy == "open":
            return True
        if self.config.group_policy != "mention":
            return True
        if self._bot_user_id:
            mentions = payload.get("mentions") if isinstance(payload.get("mentions"), list) else []
            if any(str(mention.get("id")) == self._bot_user_id for mention in mentions):
                return True
            if f"<@{self._bot_user_id}>" in content or f"<@!{self._bot_user_id}>" in content:
                return True
        return False

    async def _start_typing(self, channel_id: str) -> None:
        await self._stop_typing(channel_id)
        if self._http is None:
            return

        async def typing_loop() -> None:
            url = f"{DISCORD_API_BASE}/channels/{channel_id}/typing"
            headers = {"Authorization": f"Bot {self.config.token}"}
            while self._running:
                try:
                    await self._http.post(url, headers=headers)
                except asyncio.CancelledError:
                    return
                except Exception:
                    return
                await asyncio.sleep(8)

        self._typing_tasks[channel_id] = asyncio.create_task(typing_loop())

    async def _stop_typing(self, channel_id: str) -> None:
        task = self._typing_tasks.pop(channel_id, None)
        if task is not None:
            task.cancel()


class DingTalkChannel(SparkBotChannel):
    name = "dingtalk"
    display_name = "DingTalk"
    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    _AUDIO_EXTS = {".amr", ".mp3", ".wav", ".ogg", ".m4a", ".aac"}
    _VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._client: Any | None = None
        self._http: Any | None = None
        self._access_token: str | None = None
        self._token_expiry: float = 0
        self._background_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        if not self.config.client_id or not self.config.client_secret:
            logger.warning("DingTalk credentials not configured; using in-memory channel")
            await super().start()
            return

        try:
            from dingtalk_stream import (
                AckMessage,
                CallbackHandler,
                Credential,
                DingTalkStreamClient,
            )
            from dingtalk_stream.chatbot import ChatbotMessage
            import httpx
        except Exception:
            logger.warning("DingTalk channel requires dingtalk-stream and httpx; using in-memory channel")
            await super().start()
            return

        self._running = True
        self._stop_event.clear()
        self._http = httpx.AsyncClient(timeout=30.0)
        credential = Credential(self.config.client_id, self.config.client_secret)
        self._client = DingTalkStreamClient(credential)
        channel = self

        class NGDingTalkHandler(CallbackHandler):
            async def process(self, message: Any) -> tuple[Any, str]:
                data = getattr(message, "data", None)
                if not isinstance(data, dict):
                    data = {}
                task = asyncio.create_task(channel._handle_stream_message(data))
                channel._background_tasks.add(task)
                task.add_done_callback(channel._background_tasks.discard)
                return AckMessage.STATUS_OK, "OK"

        self._client.register_callback_handler(ChatbotMessage.TOPIC, NGDingTalkHandler())
        while self._running:
            try:
                await self._client.start()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("DingTalk stream connection failed")
                if self._running:
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        if self._client is not None:
            for method_name in ("stop", "close"):
                method = getattr(self._client, method_name, None)
                if callable(method):
                    result = method()
                    if asyncio.iscoroutine(result):
                        await result
                    break
            self._client = None
        if self._http is not None:
            close = getattr(self._http, "aclose", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._http = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if not self.config.client_id or not self.config.client_secret:
            await super().send(msg)
            return

        token = await self._get_access_token()
        if not token:
            logger.warning("DingTalk access token unavailable; outbound message was not sent")
            return

        sent_any = False
        if msg.content and msg.content.strip():
            sent_any = await self._send_markdown_text(token, msg.chat_id, msg.content.strip())

        for media_ref in msg.media or []:
            if await self._send_media_ref(token, msg.chat_id, media_ref):
                sent_any = True
                continue
            filename = self._guess_filename(media_ref, self._guess_upload_type(media_ref))
            fallback = f"[Attachment send failed: {filename}]"
            if await self._send_markdown_text(token, msg.chat_id, fallback):
                sent_any = True

        if sent_any:
            self.sent_messages.append(msg)

    async def _get_access_token(self) -> str | None:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        http = await self._ensure_http()
        if http is None:
            return None

        try:
            response = await http.post(
                "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                json={
                    "appKey": self.config.client_id,
                    "appSecret": self.config.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("accessToken")
            if not token:
                return None
            self._access_token = str(token)
            self._token_expiry = time.time() + int(data.get("expireIn", 7200)) - 60
            return self._access_token
        except Exception:
            logger.exception("Failed to refresh DingTalk access token")
            return None

    async def _ensure_http(self) -> Any | None:
        if self._http is not None:
            return self._http
        try:
            import httpx
        except Exception:
            logger.warning("DingTalk channel requires httpx for REST calls")
            return None
        self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def _send_batch_message(
        self,
        token: str,
        chat_id: str,
        msg_key: str,
        msg_param: dict[str, Any],
    ) -> bool:
        http = await self._ensure_http()
        if http is None:
            return False

        headers = {"x-acs-dingtalk-access-token": token}
        if chat_id.startswith("group:"):
            url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
            payload = {
                "robotCode": self.config.client_id,
                "openConversationId": chat_id[6:],
                "msgKey": msg_key,
                "msgParam": json.dumps(msg_param, ensure_ascii=False),
            }
        else:
            url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
            payload = {
                "robotCode": self.config.client_id,
                "userIds": [chat_id],
                "msgKey": msg_key,
                "msgParam": json.dumps(msg_param, ensure_ascii=False),
            }

        try:
            response = await http.post(url, json=payload, headers=headers)
            if getattr(response, "status_code", 200) >= 400:
                return False
            try:
                data = response.json()
            except Exception:
                data = {}
            errcode = data.get("errcode")
            return errcode in (None, 0)
        except Exception:
            logger.exception("Error sending DingTalk message")
            return False

    async def _send_markdown_text(self, token: str, chat_id: str, content: str) -> bool:
        return await self._send_batch_message(
            token,
            chat_id,
            "sampleMarkdown",
            {"title": "SparkWeave Reply", "text": content},
        )

    async def _send_media_ref(self, token: str, chat_id: str, media_ref: str) -> bool:
        media_ref = (media_ref or "").strip()
        if not media_ref:
            return True

        upload_type = self._guess_upload_type(media_ref)
        if upload_type == "image" and self._is_http_url(media_ref):
            if await self._send_batch_message(
                token,
                chat_id,
                "sampleImageMsg",
                {"photoURL": media_ref},
            ):
                return True

        data, filename, content_type = await self._read_media_bytes(media_ref)
        if not data:
            return False
        filename = filename or self._guess_filename(media_ref, upload_type)
        media_id = await self._upload_media(token, data, upload_type, filename, content_type)
        if not media_id:
            return False

        if upload_type == "image":
            ok = await self._send_batch_message(
                token,
                chat_id,
                "sampleImageMsg",
                {"photoURL": media_id},
            )
            if ok:
                return True

        file_type = Path(filename).suffix.lower().lstrip(".") or "bin"
        if file_type == "jpeg":
            file_type = "jpg"
        return await self._send_batch_message(
            token,
            chat_id,
            "sampleFile",
            {"mediaId": media_id, "fileName": filename, "fileType": file_type},
        )

    async def _upload_media(
        self,
        token: str,
        data: bytes,
        media_type: str,
        filename: str,
        content_type: str | None,
    ) -> str | None:
        http = await self._ensure_http()
        if http is None:
            return None
        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        url = f"https://oapi.dingtalk.com/media/upload?access_token={token}&type={media_type}"
        try:
            response = await http.post(url, files={"media": (filename, data, mime)})
            if getattr(response, "status_code", 200) >= 400:
                return None
            try:
                payload = response.json()
            except Exception:
                payload = {}
            if payload.get("errcode", 0) != 0:
                return None
            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            media_id = (
                payload.get("media_id")
                or payload.get("mediaId")
                or result.get("media_id")
                or result.get("mediaId")
            )
            return str(media_id) if media_id else None
        except Exception:
            logger.exception("DingTalk media upload failed")
            return None

    async def _read_media_bytes(
        self,
        media_ref: str,
    ) -> tuple[bytes | None, str | None, str | None]:
        if not media_ref:
            return None, None, None
        if self._is_http_url(media_ref):
            http = await self._ensure_http()
            if http is None:
                return None, None, None
            try:
                response = await http.get(media_ref, follow_redirects=True)
                if getattr(response, "status_code", 200) >= 400:
                    return None, None, None
                content_type = (response.headers.get("content-type") or "").split(";")[0].strip()
                return (
                    response.content,
                    self._guess_filename(media_ref, self._guess_upload_type(media_ref)),
                    content_type or None,
                )
            except Exception:
                logger.exception("DingTalk media download failed")
                return None, None, None

        path = self._local_media_path(media_ref)
        if not path.is_file():
            return None, None, None
        data = await asyncio.to_thread(path.read_bytes)
        return data, path.name, mimetypes.guess_type(path.name)[0]

    async def _handle_stream_message(self, payload: dict[str, Any]) -> bool:
        content = self._extract_content(payload)
        if not content:
            return False

        sender_id = self._first_text(
            payload,
            "senderStaffId",
            "sender_staff_id",
            "senderId",
            "sender_id",
            "fromStaffId",
            "from_staff_id",
        )
        sender_name = (
            self._first_text(payload, "senderNick", "sender_nick", "senderName", "sender_name")
            or "Unknown"
        )
        conversation_type = self._first_text(payload, "conversationType", "conversation_type")
        conversation_id = self._first_text(
            payload,
            "conversationId",
            "conversation_id",
            "openConversationId",
            "open_conversation_id",
        )
        if not sender_id:
            return False

        is_group = bool(conversation_id and conversation_type == "2")
        chat_id = f"group:{conversation_id}" if is_group else sender_id
        return await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={
                "sender_name": sender_name,
                "platform": "dingtalk",
                "conversation_type": conversation_type,
                "conversation_id": conversation_id,
                "message_id": self._first_text(payload, "msgId", "msg_id", "messageId"),
            },
            session_key=f"dingtalk:{chat_id}",
        )

    @classmethod
    def _extract_content(cls, payload: dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, dict):
            content = str(text.get("content") or "").strip()
            if content:
                return content
        content = payload.get("content")
        if isinstance(content, dict):
            recognition = str(content.get("recognition") or "").strip()
            if recognition:
                return recognition
            plain = str(content.get("content") or "").strip()
            if plain:
                return plain
        if isinstance(content, str) and content.strip():
            return content.strip()
        extensions = payload.get("extensions")
        if isinstance(extensions, dict):
            nested = extensions.get("content")
            if isinstance(nested, dict):
                recognition = str(nested.get("recognition") or "").strip()
                if recognition:
                    return recognition
        return ""

    @staticmethod
    def _first_text(payload: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @staticmethod
    def _is_http_url(value: str) -> bool:
        return urlparse(value).scheme in {"http", "https"}

    def _guess_upload_type(self, media_ref: str) -> str:
        ext = Path(urlparse(media_ref).path).suffix.lower()
        if ext in self._IMAGE_EXTS:
            return "image"
        if ext in self._AUDIO_EXTS:
            return "voice"
        if ext in self._VIDEO_EXTS:
            return "video"
        return "file"

    def _guess_filename(self, media_ref: str, upload_type: str) -> str:
        name = os.path.basename(urlparse(media_ref).path)
        if name:
            return name
        return {
            "image": "image.jpg",
            "voice": "audio.amr",
            "video": "video.mp4",
        }.get(upload_type, "file.bin")

    @staticmethod
    def _local_media_path(media_ref: str) -> Path:
        if media_ref.startswith("file://"):
            parsed = urlparse(media_ref)
            path_text = unquote(parsed.path)
            if os.name == "nt" and re.match(r"^/[A-Za-z]:/", path_text):
                path_text = path_text[1:]
            return Path(path_text)
        return Path(os.path.expanduser(media_ref))


class EmailChannel(SparkBotChannel):
    name = "email"
    display_name = "Email"
    _IMAP_MONTHS = (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    _MAX_PROCESSED_UIDS = 100_000

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._last_subject_by_chat: dict[str, str] = {}
        self._last_message_id_by_chat: dict[str, str] = {}
        self._processed_uids: set[str] = set()

    async def start(self) -> None:
        if not self.config.consent_granted:
            logger.warning("Email channel disabled because consent_granted is false")
            return
        if not self._validate_config():
            return

        self._running = True
        self._stop_event.clear()
        poll_seconds = max(5, int(self.config.poll_interval_seconds))
        while self._running:
            try:
                inbound_items = await asyncio.to_thread(self._fetch_new_messages)
                for item in inbound_items:
                    sender = item["sender"]
                    subject = item.get("subject", "")
                    message_id = item.get("message_id", "")
                    if subject:
                        self._last_subject_by_chat[sender] = subject
                    if message_id:
                        self._last_message_id_by_chat[sender] = message_id
                    await self._handle_message(
                        sender_id=sender,
                        chat_id=sender,
                        content=item["content"],
                        metadata=item.get("metadata", {}),
                    )
            except Exception:
                logger.exception("Email polling failed")
            await asyncio.sleep(poll_seconds)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if not self.config.consent_granted:
            logger.warning("Email send skipped because consent_granted is false")
            return
        if not self.config.smtp_host:
            logger.warning("Email send skipped because smtp_host is not configured")
            return

        to_addr = msg.chat_id.strip()
        if not to_addr:
            logger.warning("Email send skipped because recipient is empty")
            return

        is_reply = to_addr in self._last_subject_by_chat
        force_send = bool((msg.metadata or {}).get("force_send"))
        if is_reply and not self.config.auto_reply_enabled and not force_send:
            return

        base_subject = self._last_subject_by_chat.get(to_addr, "SparkBot reply")
        subject = self._reply_subject(base_subject)
        if msg.metadata and isinstance(msg.metadata.get("subject"), str):
            override = msg.metadata["subject"].strip()
            if override:
                subject = override

        email_msg = EmailMessage()
        email_msg["From"] = (
            self.config.from_address
            or self.config.smtp_username
            or self.config.imap_username
        )
        email_msg["To"] = to_addr
        email_msg["Subject"] = subject
        email_msg.set_content(msg.content or "")

        in_reply_to = self._last_message_id_by_chat.get(to_addr)
        if in_reply_to:
            email_msg["In-Reply-To"] = in_reply_to
            email_msg["References"] = in_reply_to

        await asyncio.to_thread(self._smtp_send, email_msg)
        self.sent_messages.append(msg)

    def _validate_config(self) -> bool:
        required = {
            "imap_host": self.config.imap_host,
            "imap_username": self.config.imap_username,
            "imap_password": self.config.imap_password,
            "smtp_host": self.config.smtp_host,
            "smtp_username": self.config.smtp_username,
            "smtp_password": self.config.smtp_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            logger.error("Email channel missing config: %s", ", ".join(missing))
            return False
        return True

    def _smtp_send(self, msg: EmailMessage) -> None:
        timeout = 30
        if self.config.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=timeout,
            ) as smtp:
                smtp.login(self.config.smtp_username, self.config.smtp_password)
                smtp.send_message(msg)
            return

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=timeout) as smtp:
            if self.config.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(self.config.smtp_username, self.config.smtp_password)
            smtp.send_message(msg)

    def _fetch_new_messages(self) -> list[dict[str, Any]]:
        return self._fetch_messages(
            search_criteria=("UNSEEN",),
            mark_seen=self.config.mark_seen,
            dedupe=True,
            limit=0,
        )

    def fetch_messages_between_dates(
        self,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if end_date <= start_date:
            return []
        return self._fetch_messages(
            search_criteria=(
                "SINCE",
                self._format_imap_date(start_date),
                "BEFORE",
                self._format_imap_date(end_date),
            ),
            mark_seen=False,
            dedupe=False,
            limit=max(1, int(limit)),
        )

    def _fetch_messages(
        self,
        search_criteria: tuple[str, ...],
        mark_seen: bool,
        dedupe: bool,
        limit: int,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        mailbox = self.config.imap_mailbox or "INBOX"
        client = (
            imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
            if self.config.imap_use_ssl
            else imaplib.IMAP4(self.config.imap_host, self.config.imap_port)
        )

        try:
            client.login(self.config.imap_username, self.config.imap_password)
            status, _ = client.select(mailbox)
            if status != "OK":
                return messages
            status, data = client.search(None, *search_criteria)
            if status != "OK" or not data:
                return messages
            ids = data[0].split()
            if limit > 0 and len(ids) > limit:
                ids = ids[-limit:]
            for imap_id in ids:
                status, fetched = client.fetch(imap_id, "(BODY.PEEK[] UID)")
                if status != "OK" or not fetched:
                    continue
                raw_bytes = self._extract_message_bytes(fetched)
                if raw_bytes is None:
                    continue
                uid = self._extract_uid(fetched)
                if dedupe and uid and uid in self._processed_uids:
                    continue

                parsed = BytesParser(policy=policy.default).parsebytes(raw_bytes)
                sender = parseaddr(parsed.get("From", ""))[1].strip().lower()
                if not sender:
                    continue
                subject = self._decode_header_value(parsed.get("Subject", ""))
                date_value = parsed.get("Date", "")
                message_id = parsed.get("Message-ID", "").strip()
                body = self._extract_text_body(parsed) or "(empty email body)"
                body = body[: self.config.max_body_chars]
                content = (
                    "Email received.\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n"
                    f"Date: {date_value}\n\n"
                    f"{body}"
                )
                metadata = {
                    "message_id": message_id,
                    "subject": subject,
                    "date": date_value,
                    "sender_email": sender,
                    "uid": uid,
                }
                messages.append(
                    {
                        "sender": sender,
                        "subject": subject,
                        "message_id": message_id,
                        "content": content,
                        "metadata": metadata,
                    }
                )
                if dedupe and uid:
                    self._processed_uids.add(uid)
                    if len(self._processed_uids) > self._MAX_PROCESSED_UIDS:
                        half = len(self._processed_uids) // 2
                        self._processed_uids = set(list(self._processed_uids)[half:])
                if mark_seen:
                    client.store(imap_id, "+FLAGS", "\\Seen")
        finally:
            try:
                client.logout()
            except Exception:
                pass
        return messages

    @classmethod
    def _format_imap_date(cls, value: date) -> str:
        month = cls._IMAP_MONTHS[value.month - 1]
        return f"{value.day:02d}-{month}-{value.year}"

    @staticmethod
    def _extract_message_bytes(fetched: list[Any]) -> bytes | None:
        for item in fetched:
            if (
                isinstance(item, tuple)
                and len(item) >= 2
                and isinstance(item[1], (bytes, bytearray))
            ):
                return bytes(item[1])
        return None

    @staticmethod
    def _extract_uid(fetched: list[Any]) -> str:
        for item in fetched:
            if isinstance(item, tuple) and item and isinstance(item[0], (bytes, bytearray)):
                header = bytes(item[0]).decode("utf-8", errors="ignore")
                match = re.search(r"UID\s+(\d+)", header)
                if match:
                    return match.group(1)
        return ""

    @staticmethod
    def _decode_header_value(value: str) -> str:
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    @classmethod
    def _extract_text_body(cls, msg: Any) -> str:
        if msg.is_multipart():
            plain_parts: list[str] = []
            html_parts: list[str] = []
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    continue
                content_type = part.get_content_type()
                try:
                    payload = part.get_content()
                except Exception:
                    payload_bytes = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    payload = payload_bytes.decode(charset, errors="replace")
                if not isinstance(payload, str):
                    continue
                if content_type == "text/plain":
                    plain_parts.append(payload)
                elif content_type == "text/html":
                    html_parts.append(payload)
            if plain_parts:
                return "\n\n".join(plain_parts).strip()
            if html_parts:
                return cls._html_to_text("\n\n".join(html_parts)).strip()
            return ""

        try:
            payload = msg.get_content()
        except Exception:
            payload_bytes = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            payload = payload_bytes.decode(charset, errors="replace")
        if not isinstance(payload, str):
            return ""
        if msg.get_content_type() == "text/html":
            return cls._html_to_text(payload).strip()
        return payload.strip()

    @staticmethod
    def _html_to_text(raw_html: str) -> str:
        text = re.sub(r"<\s*br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
        text = re.sub(r"<\s*/\s*p\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return html.unescape(text)

    def _reply_subject(self, base_subject: str) -> str:
        subject = (base_subject or "").strip() or "SparkBot reply"
        prefix = self.config.subject_prefix or "Re: "
        if subject.lower().startswith("re:"):
            return subject
        return f"{prefix}{subject}"


class FeishuChannel(SparkBotChannel):
    name = "feishu"
    display_name = "Feishu"
    _MSG_TYPE_LABELS = {
        "image": "[image]",
        "audio": "[audio]",
        "file": "[file]",
        "sticker": "[sticker]",
    }
    _TABLE_RE = re.compile(
        r"((?:^[ \t]*\|.+\|[ \t]*\n)(?:^[ \t]*\|[-:\s|]+\|[ \t]*\n)(?:^[ \t]*\|.+\|[ \t]*\n?)+)",
        re.MULTILINE,
    )
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    _CODE_BLOCK_RE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)
    _COMPLEX_MD_RE = re.compile(
        r"```|^\|.+\|.*\n\s*\|[-:\s|]+\||^#{1,6}\s+",
        re.MULTILINE,
    )
    _SIMPLE_MD_RE = re.compile(
        r"\*\*.+?\*\*|__.+?__|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|~~.+?~~",
        re.DOTALL,
    )
    _MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
    _LIST_RE = re.compile(r"^[\s]*[-*+]\s+", re.MULTILINE)
    _OLIST_RE = re.compile(r"^[\s]*\d+\.\s+", re.MULTILINE)
    _TEXT_MAX_LEN = 200
    _POST_MAX_LEN = 2000
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".tif"}
    _AUDIO_EXTS = {".opus"}
    _VIDEO_EXTS = {".mp4", ".mov", ".avi"}
    _FILE_TYPE_MAP = {
        ".opus": "opus",
        ".mp4": "mp4",
        ".pdf": "pdf",
        ".doc": "doc",
        ".docx": "doc",
        ".xls": "xls",
        ".xlsx": "xls",
        ".ppt": "ppt",
        ".pptx": "ppt",
    }

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._client: Any | None = None
        self._ws_client: Any | None = None
        self._ws_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()

    @staticmethod
    def _register_optional_event(builder: Any, method_name: str, handler: Any) -> Any:
        method = getattr(builder, method_name, None)
        return method(handler) if callable(method) else builder

    async def start(self) -> None:
        if not self.config.app_id or not self.config.app_secret:
            logger.warning("Feishu credentials not configured; using in-memory channel")
            await super().start()
            return
        try:
            import lark_oapi as lark
        except Exception:
            logger.warning("Feishu channel requires lark-oapi; using in-memory channel")
            await super().start()
            return

        self._running = True
        self._stop_event.clear()
        self._loop = asyncio.get_running_loop()
        self._client = (
            lark.Client.builder()
            .app_id(self.config.app_id)
            .app_secret(self.config.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
        builder = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key or "",
            self.config.verification_token or "",
        ).register_p2_im_message_receive_v1(self._on_message_sync)
        builder = self._register_optional_event(
            builder,
            "register_p2_im_message_reaction_created_v1",
            self._on_reaction_created,
        )
        builder = self._register_optional_event(
            builder,
            "register_p2_im_message_message_read_v1",
            self._on_message_read,
        )
        builder = self._register_optional_event(
            builder,
            "register_p2_im_chat_access_event_bot_p2p_chat_entered_v1",
            self._on_bot_p2p_chat_entered,
        )
        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=builder.build(),
            log_level=lark.LogLevel.INFO,
        )

        def run_ws() -> None:
            try:
                import lark_oapi.ws.client as lark_ws_client
            except Exception:
                logger.exception("Failed to import Feishu WebSocket client")
                return
            ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ws_loop)
            lark_ws_client.loop = ws_loop
            try:
                while self._running:
                    try:
                        self._ws_client.start()
                    except Exception:
                        logger.exception("Feishu WebSocket connection failed")
                    if self._running:
                        time.sleep(5)
            finally:
                ws_loop.close()

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self._loop = None
        self._ws_client = None
        self._client = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._client is None:
            logger.warning("Feishu client not initialized; outbound message was not sent")
            await super().send(msg)
            return

        receive_id_type = "chat_id" if str(msg.chat_id).startswith("oc_") else "open_id"
        sent_any = False
        loop = asyncio.get_running_loop()

        for media_path in msg.media or []:
            path = Path(media_path)
            if not path.is_file():
                logger.warning("Feishu media file not found: %s", media_path)
                continue
            ext = path.suffix.lower()
            if ext in self._IMAGE_EXTS:
                key = await loop.run_in_executor(None, self._upload_image_sync, str(path))
                if key:
                    content = json.dumps({"image_key": key}, ensure_ascii=False)
                    sent_any = (
                        await loop.run_in_executor(
                            None,
                            self._send_message_sync,
                            receive_id_type,
                            msg.chat_id,
                            "image",
                            content,
                        )
                        or sent_any
                    )
                continue

            key = await loop.run_in_executor(None, self._upload_file_sync, str(path))
            if key:
                media_type = "media" if ext in self._AUDIO_EXTS or ext in self._VIDEO_EXTS else "file"
                content = json.dumps({"file_key": key}, ensure_ascii=False)
                sent_any = (
                    await loop.run_in_executor(
                        None,
                        self._send_message_sync,
                        receive_id_type,
                        msg.chat_id,
                        media_type,
                        content,
                    )
                    or sent_any
                )

        if msg.content and msg.content.strip():
            fmt = self._detect_msg_format(msg.content)
            if fmt == "text":
                content = json.dumps({"text": msg.content.strip()}, ensure_ascii=False)
                sent_any = (
                    await loop.run_in_executor(
                        None,
                        self._send_message_sync,
                        receive_id_type,
                        msg.chat_id,
                        "text",
                        content,
                    )
                    or sent_any
                )
            elif fmt == "post":
                content = self._markdown_to_post(msg.content)
                sent_any = (
                    await loop.run_in_executor(
                        None,
                        self._send_message_sync,
                        receive_id_type,
                        msg.chat_id,
                        "post",
                        content,
                    )
                    or sent_any
                )
            else:
                elements = self._build_card_elements(msg.content)
                for chunk in self._split_elements_by_table_limit(elements):
                    card = {"config": {"wide_screen_mode": True}, "elements": chunk}
                    content = json.dumps(card, ensure_ascii=False)
                    sent_any = (
                        await loop.run_in_executor(
                            None,
                            self._send_message_sync,
                            receive_id_type,
                            msg.chat_id,
                            "interactive",
                            content,
                        )
                        or sent_any
                    )

        if sent_any:
            self.sent_messages.append(msg)

    def _on_message_sync(self, data: Any) -> None:
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)

    async def _on_message(self, data: Any) -> bool:
        try:
            event = getattr(data, "event", data)
            message = getattr(event, "message", None)
            sender = getattr(event, "sender", None)
            if message is None or sender is None:
                return False

            message_id = str(getattr(message, "message_id", "") or "")
            if message_id and message_id in self._processed_message_ids:
                return False
            if message_id:
                self._processed_message_ids[message_id] = None
                while len(self._processed_message_ids) > 1000:
                    self._processed_message_ids.popitem(last=False)

            if str(getattr(sender, "sender_type", "") or "") == "bot":
                return False

            sender_id = self._sender_open_id(sender)
            chat_id = str(getattr(message, "chat_id", "") or "")
            chat_type = str(getattr(message, "chat_type", "") or "")
            msg_type = str(getattr(message, "message_type", "") or "")
            if not sender_id or not chat_id:
                return False
            if chat_type == "group" and not self._is_group_message_for_bot(message):
                return False

            if message_id:
                await self._add_reaction(message_id, self.config.react_emoji)

            content_json = self._loads_message_content(getattr(message, "content", ""))
            content_parts: list[str] = []
            media_paths: list[str] = []

            if msg_type == "text":
                text = str(content_json.get("text") or "").strip()
                if text:
                    content_parts.append(text)
            elif msg_type == "post":
                text, image_keys = self._extract_post_content(content_json)
                if text:
                    content_parts.append(text)
                for image_key in image_keys:
                    path, label = await self._download_and_save_media(
                        "image",
                        {"image_key": image_key},
                        message_id,
                    )
                    if path:
                        media_paths.append(path)
                    content_parts.append(label)
            elif msg_type in {"image", "audio", "file", "media"}:
                path, label = await self._download_and_save_media(msg_type, content_json, message_id)
                if path:
                    media_paths.append(path)
                if msg_type == "audio" and path:
                    transcription = await self.transcribe_audio(path)
                    if transcription:
                        label = f"[transcription: {transcription}]"
                content_parts.append(label)
            elif msg_type in {
                "share_chat",
                "share_user",
                "interactive",
                "share_calendar_event",
                "system",
                "merge_forward",
            }:
                label = self._extract_share_card_content(content_json, msg_type)
                if label:
                    content_parts.append(label)
            else:
                content_parts.append(self._MSG_TYPE_LABELS.get(msg_type, f"[{msg_type}]"))

            content = "\n".join(part for part in content_parts if part)
            if not content and not media_paths:
                return False

            reply_chat = chat_id if chat_type == "group" else sender_id
            return await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_chat,
                content=content,
                media=media_paths,
                metadata={
                    "message_id": message_id,
                    "chat_type": chat_type,
                    "msg_type": msg_type,
                },
                session_key=f"feishu:{reply_chat}",
            )
        except Exception:
            logger.exception("Error processing Feishu message")
            return False

    def _is_bot_mentioned(self, message: Any) -> bool:
        raw_content = str(getattr(message, "content", "") or "")
        if "@_all" in raw_content:
            return True
        for mention in getattr(message, "mentions", None) or []:
            mention_id = getattr(mention, "id", None)
            if mention_id is None:
                continue
            open_id = str(getattr(mention_id, "open_id", "") or "")
            user_id = str(getattr(mention_id, "user_id", "") or "")
            if open_id.startswith("ou_") and not user_id:
                return True
        return False

    def _is_group_message_for_bot(self, message: Any) -> bool:
        return self.config.group_policy == "open" or self._is_bot_mentioned(message)

    async def _add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        if self._client is None or not emoji_type:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_reaction_sync, message_id, emoji_type)

    def _add_reaction_sync(self, message_id: str, emoji_type: str) -> None:
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageReactionRequest,
                CreateMessageReactionRequestBody,
                Emoji,
            )

            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                )
                .build()
            )
            response = self._client.im.v1.message_reaction.create(request)
            if not response.success():
                logger.warning("Failed to add Feishu reaction: %s", getattr(response, "msg", ""))
        except Exception:
            logger.exception("Error adding Feishu reaction")

    def _upload_image_sync(self, file_path: str) -> str | None:
        try:
            from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody

            with open(file_path, "rb") as handle:
                request = (
                    CreateImageRequest.builder()
                    .request_body(
                        CreateImageRequestBody.builder()
                        .image_type("message")
                        .image(handle)
                        .build()
                    )
                    .build()
                )
                response = self._client.im.v1.image.create(request)
            if response.success():
                return str(response.data.image_key)
            logger.error("Failed to upload Feishu image: %s", getattr(response, "msg", ""))
            return None
        except Exception:
            logger.exception("Error uploading Feishu image")
            return None

    def _upload_file_sync(self, file_path: str) -> str | None:
        try:
            from lark_oapi.api.im.v1 import CreateFileRequest, CreateFileRequestBody

            path = Path(file_path)
            file_type = self._FILE_TYPE_MAP.get(path.suffix.lower(), "stream")
            with path.open("rb") as handle:
                request = (
                    CreateFileRequest.builder()
                    .request_body(
                        CreateFileRequestBody.builder()
                        .file_type(file_type)
                        .file_name(path.name)
                        .file(handle)
                        .build()
                    )
                    .build()
                )
                response = self._client.im.v1.file.create(request)
            if response.success():
                return str(response.data.file_key)
            logger.error("Failed to upload Feishu file: %s", getattr(response, "msg", ""))
            return None
        except Exception:
            logger.exception("Error uploading Feishu file")
            return None

    def _download_image_sync(self, message_id: str, image_key: str) -> tuple[bytes | None, str | None]:
        return self._download_resource_sync(message_id, image_key, "image")

    def _download_file_sync(
        self,
        message_id: str,
        file_key: str,
        resource_type: str = "file",
    ) -> tuple[bytes | None, str | None]:
        return self._download_resource_sync(
            message_id,
            file_key,
            "file" if resource_type == "audio" else resource_type,
        )

    def _download_resource_sync(
        self,
        message_id: str,
        file_key: str,
        resource_type: str,
    ) -> tuple[bytes | None, str | None]:
        try:
            from lark_oapi.api.im.v1 import GetMessageResourceRequest

            request = (
                GetMessageResourceRequest.builder()
                .message_id(message_id)
                .file_key(file_key)
                .type(resource_type)
                .build()
            )
            response = self._client.im.v1.message_resource.get(request)
            if not response.success():
                return None, None
            data = response.file
            if hasattr(data, "read"):
                data = data.read()
            return bytes(data), getattr(response, "file_name", None)
        except Exception:
            logger.exception("Error downloading Feishu resource")
            return None, None

    async def _download_and_save_media(
        self,
        msg_type: str,
        content_json: dict[str, Any],
        message_id: str | None = None,
    ) -> tuple[str | None, str]:
        loop = asyncio.get_running_loop()
        data: bytes | None = None
        filename: str | None = None
        if msg_type == "image":
            image_key = str(content_json.get("image_key") or "")
            if image_key and message_id:
                data, filename = await loop.run_in_executor(
                    None,
                    self._download_image_sync,
                    message_id,
                    image_key,
                )
                filename = filename or f"{image_key[:16]}.jpg"
        elif msg_type in {"audio", "file", "media"}:
            file_key = str(content_json.get("file_key") or "")
            if file_key and message_id:
                data, filename = await loop.run_in_executor(
                    None,
                    self._download_file_sync,
                    message_id,
                    file_key,
                    msg_type,
                )
                filename = filename or file_key[:16]
                if msg_type == "audio" and not filename.endswith(".opus"):
                    filename = f"{filename}.opus"

        if data and filename:
            safe_name = Path(filename).name or "feishu_media.bin"
            path = _sparkbot_media_dir("feishu") / safe_name
            path.write_bytes(data)
            return str(path), f"[{msg_type}: {safe_name}]"
        return None, f"[{msg_type}: download failed]"

    def _send_message_sync(
        self,
        receive_id_type: str,
        receive_id: str,
        msg_type: str,
        content: str,
    ) -> bool:
        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                )
                .build()
            )
            response = self._client.im.v1.message.create(request)
            if response.success():
                return True
            logger.error("Failed to send Feishu message: %s", getattr(response, "msg", ""))
            return False
        except Exception:
            logger.exception("Error sending Feishu message")
            return False

    @classmethod
    def _detect_msg_format(cls, content: str) -> str:
        stripped = content.strip()
        if cls._COMPLEX_MD_RE.search(stripped):
            return "interactive"
        if len(stripped) > cls._POST_MAX_LEN:
            return "interactive"
        if cls._SIMPLE_MD_RE.search(stripped):
            return "interactive"
        if cls._LIST_RE.search(stripped) or cls._OLIST_RE.search(stripped):
            return "interactive"
        if cls._MD_LINK_RE.search(stripped):
            return "post"
        if len(stripped) <= cls._TEXT_MAX_LEN:
            return "text"
        return "post"

    @classmethod
    def _markdown_to_post(cls, content: str) -> str:
        paragraphs: list[list[dict[str, str]]] = []
        for line in content.strip().split("\n"):
            elements: list[dict[str, str]] = []
            last_end = 0
            for match in cls._MD_LINK_RE.finditer(line):
                before = line[last_end : match.start()]
                if before:
                    elements.append({"tag": "text", "text": before})
                elements.append({"tag": "a", "text": match.group(1), "href": match.group(2)})
                last_end = match.end()
            remaining = line[last_end:]
            if remaining:
                elements.append({"tag": "text", "text": remaining})
            if not elements:
                elements.append({"tag": "text", "text": ""})
            paragraphs.append(elements)
        return json.dumps({"zh_cn": {"content": paragraphs}}, ensure_ascii=False)

    @staticmethod
    def _parse_md_table(table_text: str) -> dict[str, Any] | None:
        lines = [line.strip() for line in table_text.strip().split("\n") if line.strip()]
        if len(lines) < 3:
            return None

        def split(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip("|").split("|")]

        headers = split(lines[0])
        rows = [split(line) for line in lines[2:]]
        return {
            "tag": "table",
            "page_size": len(rows) + 1,
            "columns": [
                {"tag": "column", "name": f"c{index}", "display_name": header, "width": "auto"}
                for index, header in enumerate(headers)
            ],
            "rows": [
                {
                    f"c{index}": row[index] if index < len(row) else ""
                    for index in range(len(headers))
                }
                for row in rows
            ],
        }

    def _build_card_elements(self, content: str) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        last_end = 0
        for match in self._TABLE_RE.finditer(content):
            before = content[last_end : match.start()]
            if before.strip():
                elements.extend(self._split_headings(before))
            elements.append(
                self._parse_md_table(match.group(1))
                or {"tag": "markdown", "content": match.group(1)}
            )
            last_end = match.end()
        remaining = content[last_end:]
        if remaining.strip():
            elements.extend(self._split_headings(remaining))
        return elements or [{"tag": "markdown", "content": content}]

    @staticmethod
    def _split_elements_by_table_limit(
        elements: list[dict[str, Any]],
        max_tables: int = 1,
    ) -> list[list[dict[str, Any]]]:
        if not elements:
            return [[]]
        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        table_count = 0
        for element in elements:
            if element.get("tag") == "table" and table_count >= max_tables:
                if current:
                    groups.append(current)
                current = []
                table_count = 0
            current.append(element)
            if element.get("tag") == "table":
                table_count += 1
        if current:
            groups.append(current)
        return groups or [[]]

    def _split_headings(self, content: str) -> list[dict[str, Any]]:
        protected = content
        code_blocks: list[str] = []
        for match in self._CODE_BLOCK_RE.finditer(content):
            code_blocks.append(match.group(1))
            protected = protected.replace(match.group(1), f"\x00CODE{len(code_blocks) - 1}\x00", 1)

        elements: list[dict[str, Any]] = []
        last_end = 0
        for match in self._HEADING_RE.finditer(protected):
            before = protected[last_end : match.start()].strip()
            if before:
                elements.append({"tag": "markdown", "content": before})
            elements.append(
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**{match.group(2).strip()}**"},
                }
            )
            last_end = match.end()
        remaining = protected[last_end:].strip()
        if remaining:
            elements.append({"tag": "markdown", "content": remaining})
        for index, block in enumerate(code_blocks):
            for element in elements:
                if element.get("tag") == "markdown":
                    element["content"] = element["content"].replace(f"\x00CODE{index}\x00", block)
        return elements or [{"tag": "markdown", "content": content}]

    @classmethod
    def _extract_post_content(cls, content_json: dict[str, Any]) -> tuple[str, list[str]]:
        def parse_block(block: dict[str, Any]) -> tuple[str | None, list[str]]:
            if not isinstance(block, dict) or not isinstance(block.get("content"), list):
                return None, []
            texts: list[str] = []
            images: list[str] = []
            title = block.get("title")
            if title:
                texts.append(str(title))
            for row in block["content"]:
                if not isinstance(row, list):
                    continue
                for element in row:
                    if not isinstance(element, dict):
                        continue
                    tag = element.get("tag")
                    if tag in {"text", "a"}:
                        texts.append(str(element.get("text") or ""))
                    elif tag == "at":
                        texts.append(f"@{element.get('user_name', 'user')}")
                    elif tag == "img" and element.get("image_key"):
                        images.append(str(element["image_key"]))
            text = " ".join(part for part in texts if part).strip()
            return text or None, images

        root: Any = content_json.get("post") if isinstance(content_json.get("post"), dict) else content_json
        if not isinstance(root, dict):
            return "", []
        if "content" in root:
            text, images = parse_block(root)
            if text or images:
                return text or "", images
        for key in ("zh_cn", "en_us", "ja_jp"):
            if isinstance(root.get(key), dict):
                text, images = parse_block(root[key])
                if text or images:
                    return text or "", images
        for value in root.values():
            if isinstance(value, dict):
                text, images = parse_block(value)
                if text or images:
                    return text or "", images
        return "", []

    @classmethod
    def _extract_share_card_content(cls, content_json: dict[str, Any], msg_type: str) -> str:
        parts: list[str] = []
        if msg_type == "share_chat":
            parts.append(f"[shared chat: {content_json.get('chat_id', '')}]")
        elif msg_type == "share_user":
            parts.append(f"[shared user: {content_json.get('user_id', '')}]")
        elif msg_type == "interactive":
            parts.extend(cls._extract_interactive_content(content_json))
        elif msg_type == "share_calendar_event":
            parts.append(f"[shared calendar event: {content_json.get('event_key', '')}]")
        elif msg_type == "system":
            parts.append("[system message]")
        elif msg_type == "merge_forward":
            parts.append("[merged forward messages]")
        return "\n".join(part for part in parts if part) or f"[{msg_type}]"

    @classmethod
    def _extract_interactive_content(cls, content: Any) -> list[str]:
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return [content] if content.strip() else []
        if not isinstance(content, dict):
            return []

        parts: list[str] = []
        title = content.get("title")
        if isinstance(title, dict):
            title_text = title.get("content") or title.get("text")
            if title_text:
                parts.append(f"title: {title_text}")
        elif isinstance(title, str):
            parts.append(f"title: {title}")

        for row in content.get("elements", []) if isinstance(content.get("elements"), list) else []:
            if isinstance(row, list):
                for element in row:
                    parts.extend(cls._extract_element_content(element))
            else:
                parts.extend(cls._extract_element_content(row))
        card = content.get("card")
        if isinstance(card, dict):
            parts.extend(cls._extract_interactive_content(card))
        header = content.get("header")
        if isinstance(header, dict):
            header_title = header.get("title")
            if isinstance(header_title, dict):
                header_text = header_title.get("content") or header_title.get("text")
                if header_text:
                    parts.append(f"title: {header_text}")
        return parts

    @classmethod
    def _extract_element_content(cls, element: Any) -> list[str]:
        if not isinstance(element, dict):
            return []
        tag = element.get("tag", "")
        parts: list[str] = []
        if tag in {"markdown", "lark_md", "plain_text"}:
            content = element.get("content") or element.get("text")
            if content:
                parts.append(str(content))
        elif tag == "div":
            text = element.get("text")
            if isinstance(text, dict):
                text_content = text.get("content") or text.get("text")
                if text_content:
                    parts.append(str(text_content))
            elif isinstance(text, str):
                parts.append(text)
            for field in element.get("fields", []) if isinstance(element.get("fields"), list) else []:
                field_text = field.get("text") if isinstance(field, dict) else None
                if isinstance(field_text, dict) and field_text.get("content"):
                    parts.append(str(field_text["content"]))
        elif tag == "a":
            if element.get("href"):
                parts.append(f"link: {element['href']}")
            if element.get("text"):
                parts.append(str(element["text"]))
        elif tag == "button":
            text = element.get("text")
            if isinstance(text, dict) and text.get("content"):
                parts.append(str(text["content"]))
            url = element.get("url") or (element.get("multi_url") or {}).get("url")
            if url:
                parts.append(f"link: {url}")
        elif tag == "img":
            alt = element.get("alt")
            parts.append(str(alt.get("content", "[image]")) if isinstance(alt, dict) else "[image]")
        for key in ("elements", "columns"):
            values = element.get(key)
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, dict) and key == "columns":
                        for nested in value.get("elements", []) if isinstance(value.get("elements"), list) else []:
                            parts.extend(cls._extract_element_content(nested))
                    else:
                        parts.extend(cls._extract_element_content(value))
        return parts

    @staticmethod
    def _loads_message_content(raw_content: Any) -> dict[str, Any]:
        if isinstance(raw_content, dict):
            return raw_content
        if not raw_content:
            return {}
        try:
            parsed = json.loads(str(raw_content))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _sender_open_id(sender: Any) -> str:
        sender_id = getattr(sender, "sender_id", None)
        if sender_id is None:
            return "unknown"
        return str(getattr(sender_id, "open_id", "") or "unknown")

    def _on_reaction_created(self, _data: Any) -> None:
        return None

    def _on_message_read(self, _data: Any) -> None:
        return None

    def _on_bot_p2p_chat_entered(self, _data: Any) -> None:
        return None


class MatrixChannel(SparkBotChannel):
    name = "matrix"
    display_name = "Matrix"
    _TYPING_NOTICE_TIMEOUT_MS = 30_000
    _TYPING_KEEPALIVE_INTERVAL_MS = 20_000
    _HTML_FORMAT = "org.matrix.custom.html"
    _ATTACH_MARKER = "[attachment: {}]"
    _ATTACH_TOO_LARGE = "[attachment: {} - too large]"
    _ATTACH_FAILED = "[attachment: {} - download failed]"
    _ATTACH_UPLOAD_FAILED = "[attachment: {} - upload failed]"
    _DEFAULT_ATTACH_NAME = "attachment"
    _MSGTYPE_MAP = {"m.image": "image", "m.audio": "audio", "m.video": "video", "m.file": "file"}

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self.client: Any | None = None
        self._sync_task: asyncio.Task | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._server_upload_limit_bytes: int | None = None
        self._server_upload_limit_checked = False

    async def start(self) -> None:
        if not self.config.access_token or not self.config.user_id:
            logger.warning("Matrix credentials not configured; using in-memory channel")
            await super().start()
            return
        try:
            from nio import (
                AsyncClient,
                AsyncClientConfig,
                InviteEvent,
                JoinError,
                RoomEncryptedMedia,
                RoomMessageMedia,
                RoomMessageText,
                RoomSendError,
                SyncError,
            )
        except Exception:
            logger.warning("Matrix channel requires matrix-nio; using in-memory channel")
            await super().start()
            return

        self._running = True
        self._stop_event.clear()
        store_path = get_path_service().project_root / "data" / "sparkbot" / "matrix-store"
        store_path.mkdir(parents=True, exist_ok=True)
        self.client = AsyncClient(
            homeserver=self.config.homeserver,
            user=self.config.user_id,
            store_path=store_path,
            config=AsyncClientConfig(
                store_sync_tokens=True,
                encryption_enabled=self.config.e2ee_enabled,
            ),
        )
        self.client.user_id = self.config.user_id
        self.client.access_token = self.config.access_token
        self.client.device_id = self.config.device_id
        self.client.add_event_callback(self._on_message, RoomMessageText)
        self.client.add_event_callback(self._on_media_message, (RoomMessageMedia, RoomEncryptedMedia))
        self.client.add_event_callback(self._on_room_invite, InviteEvent)
        self.client.add_response_callback(self._on_response_error, SyncError)
        self.client.add_response_callback(self._on_response_error, JoinError)
        self.client.add_response_callback(self._on_response_error, RoomSendError)
        if self.config.device_id:
            try:
                self.client.load_store()
            except Exception:
                logger.exception("Matrix store load failed")
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        for room_id in list(self._typing_tasks):
            await self._stop_typing_keepalive(room_id, clear_typing=False)
        if self.client is not None:
            stop_sync = getattr(self.client, "stop_sync_forever", None)
            if callable(stop_sync):
                stop_sync()
        if self._sync_task is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._sync_task),
                    timeout=float(self.config.sync_stop_grace_seconds),
                )
            except (asyncio.CancelledError, asyncio.TimeoutError):
                self._sync_task.cancel()
                try:
                    await self._sync_task
                except asyncio.CancelledError:
                    pass
            self._sync_task = None
        if self.client is not None:
            close = getattr(self.client, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self.client = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self.client is None:
            logger.warning("Matrix client not initialized; outbound message was not sent")
            await super().send(msg)
            return

        text = msg.content or ""
        candidates = self._collect_outbound_media_candidates(msg.media)
        relates_to = self._build_thread_relates_to(msg.metadata)
        is_progress = bool((msg.metadata or {}).get("_progress"))
        sent_any = False
        try:
            failures: list[str] = []
            if candidates:
                limit_bytes = await self._effective_media_limit_bytes()
                for path in candidates:
                    failure = await self._upload_and_send_attachment(
                        room_id=msg.chat_id,
                        path=path,
                        limit_bytes=limit_bytes,
                        relates_to=relates_to,
                    )
                    if failure:
                        failures.append(failure)
                    else:
                        sent_any = True
            if failures:
                text = f"{text.rstrip()}\n{chr(10).join(failures)}" if text.strip() else "\n".join(failures)
            if text or not candidates:
                content = self._build_matrix_text_content(text)
                if relates_to:
                    content["m.relates_to"] = relates_to
                await self._send_room_content(msg.chat_id, content)
                sent_any = True
        finally:
            if not is_progress:
                await self._stop_typing_keepalive(msg.chat_id, clear_typing=True)
        if sent_any:
            self.sent_messages.append(msg)

    def _collect_outbound_media_candidates(self, media: list[str]) -> list[Path]:
        seen: set[str] = set()
        candidates: list[Path] = []
        for raw in media or []:
            text = str(raw or "").strip()
            if not text:
                continue
            path = Path(text).expanduser()
            try:
                key = str(path.resolve(strict=False))
            except OSError:
                key = str(path)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(path)
        return candidates

    @classmethod
    def _build_matrix_text_content(cls, text: str) -> dict[str, Any]:
        content: dict[str, Any] = {"msgtype": "m.text", "body": text, "m.mentions": {}}
        formatted = cls._render_markdown_html(text)
        if formatted:
            content["format"] = cls._HTML_FORMAT
            content["formatted_body"] = formatted
        return content

    @staticmethod
    def _render_markdown_html(text: str) -> str | None:
        try:
            from mistune import create_markdown
            import nh3
        except Exception:
            return None
        try:
            markdown = create_markdown(
                escape=True,
                plugins=["table", "strikethrough", "url", "superscript", "subscript"],
            )
            cleaner = nh3.Cleaner(
                tags={
                    "p",
                    "a",
                    "strong",
                    "em",
                    "del",
                    "code",
                    "pre",
                    "blockquote",
                    "ul",
                    "ol",
                    "li",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "hr",
                    "br",
                    "table",
                    "thead",
                    "tbody",
                    "tr",
                    "th",
                    "td",
                    "caption",
                    "sup",
                    "sub",
                    "img",
                },
                attributes={
                    "a": {"href"},
                    "code": {"class"},
                    "ol": {"start"},
                    "img": {"src", "alt", "title", "width", "height"},
                },
                url_schemes={"https", "http", "matrix", "mailto", "mxc"},
                strip_comments=True,
                link_rel="noopener noreferrer",
            )
            formatted = cleaner.clean(markdown(text)).strip()
            if formatted.startswith("<p>") and formatted.endswith("</p>"):
                inner = formatted[3:-4]
                if "<" not in inner and ">" not in inner:
                    return None
            return formatted or None
        except Exception:
            return None

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" ._")
        return cleaned[:160] or MatrixChannel._DEFAULT_ATTACH_NAME

    @classmethod
    def _build_outbound_attachment_content(
        cls,
        *,
        filename: str,
        mime: str,
        size_bytes: int,
        mxc_url: str,
        encryption_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prefix = mime.split("/", 1)[0]
        msgtype = {"image": "m.image", "audio": "m.audio", "video": "m.video"}.get(prefix, "m.file")
        content: dict[str, Any] = {
            "msgtype": msgtype,
            "body": filename,
            "filename": filename,
            "info": {"mimetype": mime, "size": size_bytes},
            "m.mentions": {},
        }
        if encryption_info:
            content["file"] = {**encryption_info, "url": mxc_url}
        else:
            content["url"] = mxc_url
        return content

    def _is_encrypted_room(self, room_id: str) -> bool:
        if self.client is None:
            return False
        room = getattr(self.client, "rooms", {}).get(room_id)
        return bool(getattr(room, "encrypted", False))

    async def _send_room_content(self, room_id: str, content: dict[str, Any]) -> None:
        if self.client is None:
            return
        kwargs: dict[str, Any] = {
            "room_id": room_id,
            "message_type": "m.room.message",
            "content": content,
        }
        if self.config.e2ee_enabled:
            kwargs["ignore_unverified_devices"] = True
        await self.client.room_send(**kwargs)

    async def _resolve_server_upload_limit_bytes(self) -> int | None:
        if self._server_upload_limit_checked:
            return self._server_upload_limit_bytes
        self._server_upload_limit_checked = True
        if self.client is None:
            return None
        try:
            response = await self.client.content_repository_config()
        except Exception:
            return None
        upload_size = getattr(response, "upload_size", None)
        if isinstance(upload_size, int) and upload_size > 0:
            self._server_upload_limit_bytes = upload_size
            return upload_size
        return None

    async def _effective_media_limit_bytes(self) -> int:
        local_limit = max(int(self.config.max_media_bytes), 0)
        server_limit = await self._resolve_server_upload_limit_bytes()
        if server_limit is None:
            return local_limit
        return min(local_limit, server_limit) if local_limit else 0

    async def _upload_and_send_attachment(
        self,
        room_id: str,
        path: Path,
        limit_bytes: int,
        relates_to: dict[str, Any] | None = None,
    ) -> str | None:
        if self.client is None:
            return self._ATTACH_UPLOAD_FAILED.format(path.name or self._DEFAULT_ATTACH_NAME)
        resolved = path.expanduser().resolve(strict=False)
        filename = self._safe_filename(resolved.name)
        failure = self._ATTACH_UPLOAD_FAILED.format(filename)
        if not resolved.is_file():
            return failure
        try:
            size_bytes = resolved.stat().st_size
        except OSError:
            return failure
        if limit_bytes <= 0 or size_bytes > limit_bytes:
            return self._ATTACH_TOO_LARGE.format(filename)
        mime = mimetypes.guess_type(filename, strict=False)[0] or "application/octet-stream"
        try:
            with resolved.open("rb") as handle:
                upload_result = await self.client.upload(
                    handle,
                    content_type=mime,
                    filename=filename,
                    encrypt=self.config.e2ee_enabled and self._is_encrypted_room(room_id),
                    filesize=size_bytes,
                )
        except Exception:
            return failure
        upload_response = upload_result[0] if isinstance(upload_result, tuple) else upload_result
        encryption_info = (
            upload_result[1]
            if isinstance(upload_result, tuple) and isinstance(upload_result[1], dict)
            else None
        )
        mxc_url = getattr(upload_response, "content_uri", None)
        if not isinstance(mxc_url, str) or not mxc_url.startswith("mxc://"):
            return failure
        content = self._build_outbound_attachment_content(
            filename=filename,
            mime=mime,
            size_bytes=size_bytes,
            mxc_url=mxc_url,
            encryption_info=encryption_info,
        )
        if relates_to:
            content["m.relates_to"] = relates_to
        try:
            await self._send_room_content(room_id, content)
        except Exception:
            return failure
        return None

    async def _sync_loop(self) -> None:
        while self._running and self.client is not None:
            try:
                await self.client.sync_forever(timeout=30000, full_state=True)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Matrix sync failed")
                await asyncio.sleep(2)

    async def _on_response_error(self, response: Any) -> None:
        logger.warning("Matrix response error: %s", response)

    async def _on_room_invite(self, room: Any, event: Any) -> None:
        if self.client is not None and self.is_allowed(str(getattr(event, "sender", ""))):
            await self.client.join(room.room_id)

    def _is_direct_room(self, room: Any) -> bool:
        count = getattr(room, "member_count", None)
        return isinstance(count, int) and count <= 2

    def _is_bot_mentioned(self, event: Any) -> bool:
        content = self._event_source_content(event)
        mentions = content.get("m.mentions")
        if not isinstance(mentions, dict):
            return False
        user_ids = mentions.get("user_ids")
        if isinstance(user_ids, list) and self.config.user_id in user_ids:
            return True
        return bool(self.config.allow_room_mentions and mentions.get("room") is True)

    def _should_process_message(self, room: Any, event: Any) -> bool:
        sender = str(getattr(event, "sender", ""))
        if not self.is_allowed(sender):
            return False
        if self._is_direct_room(room):
            return True
        policy = self.config.group_policy
        if policy == "open":
            return True
        if policy == "allowlist":
            return room.room_id in (self.config.group_allow_from or [])
        if policy == "mention":
            return self._is_bot_mentioned(event)
        return False

    @staticmethod
    def _event_source_content(event: Any) -> dict[str, Any]:
        source = getattr(event, "source", None)
        if not isinstance(source, dict):
            return {}
        content = source.get("content")
        return content if isinstance(content, dict) else {}

    def _event_thread_root_id(self, event: Any) -> str | None:
        relates_to = self._event_source_content(event).get("m.relates_to")
        if not isinstance(relates_to, dict) or relates_to.get("rel_type") != "m.thread":
            return None
        root_id = relates_to.get("event_id")
        return root_id if isinstance(root_id, str) and root_id else None

    def _thread_metadata(self, event: Any) -> dict[str, str] | None:
        root_id = self._event_thread_root_id(event)
        if not root_id:
            return None
        metadata: dict[str, str] = {"thread_root_event_id": root_id}
        event_id = getattr(event, "event_id", None)
        if isinstance(event_id, str) and event_id:
            metadata["thread_reply_to_event_id"] = event_id
        return metadata

    @staticmethod
    def _build_thread_relates_to(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if not metadata:
            return None
        root_id = metadata.get("thread_root_event_id")
        if not isinstance(root_id, str) or not root_id:
            return None
        reply_to = metadata.get("thread_reply_to_event_id") or metadata.get("event_id")
        if not isinstance(reply_to, str) or not reply_to:
            return None
        return {
            "rel_type": "m.thread",
            "event_id": root_id,
            "m.in_reply_to": {"event_id": reply_to},
            "is_falling_back": True,
        }

    def _base_metadata(self, room: Any, event: Any) -> dict[str, Any]:
        metadata: dict[str, Any] = {"room": getattr(room, "display_name", room.room_id)}
        event_id = getattr(event, "event_id", None)
        if isinstance(event_id, str) and event_id:
            metadata["event_id"] = event_id
        thread = self._thread_metadata(event)
        if thread:
            metadata.update(thread)
        return metadata

    async def _on_message(self, room: Any, event: Any) -> bool:
        sender = str(getattr(event, "sender", ""))
        if sender == self.config.user_id or not self._should_process_message(room, event):
            return False
        await self._start_typing_keepalive(room.room_id)
        return await self._handle_message(
            sender_id=sender,
            chat_id=room.room_id,
            content=str(getattr(event, "body", "") or ""),
            metadata=self._base_metadata(room, event),
            session_key=f"matrix:{room.room_id}",
        )

    async def _on_media_message(self, room: Any, event: Any) -> bool:
        sender = str(getattr(event, "sender", ""))
        if sender == self.config.user_id or not self._should_process_message(room, event):
            return False
        attachment, marker = await self._fetch_media_attachment(room, event)
        parts: list[str] = []
        body = getattr(event, "body", None)
        if isinstance(body, str) and body.strip():
            parts.append(body.strip())
        if attachment and attachment.get("type") == "audio":
            transcription = await self.transcribe_audio(attachment["path"])
            parts.append(f"[transcription: {transcription}]" if transcription else marker)
        elif marker:
            parts.append(marker)
        await self._start_typing_keepalive(room.room_id)
        metadata = self._base_metadata(room, event)
        metadata["attachments"] = [attachment] if attachment else []
        return await self._handle_message(
            sender_id=sender,
            chat_id=room.room_id,
            content="\n".join(parts),
            media=[attachment["path"]] if attachment else [],
            attachments=[attachment] if attachment else [],
            metadata=metadata,
            session_key=f"matrix:{room.room_id}",
        )

    def _event_attachment_type(self, event: Any) -> str:
        msgtype = self._event_source_content(event).get("msgtype")
        return self._MSGTYPE_MAP.get(msgtype, "file")

    @staticmethod
    def _is_encrypted_media_event(event: Any) -> bool:
        return (
            isinstance(getattr(event, "key", None), dict)
            and isinstance(getattr(event, "hashes", None), dict)
            and isinstance(getattr(event, "iv", None), str)
        )

    def _event_declared_size_bytes(self, event: Any) -> int | None:
        info = self._event_source_content(event).get("info")
        size = info.get("size") if isinstance(info, dict) else None
        return size if isinstance(size, int) and size >= 0 else None

    def _event_mime(self, event: Any) -> str | None:
        info = self._event_source_content(event).get("info")
        if isinstance(info, dict) and isinstance(info.get("mimetype"), str):
            return info["mimetype"]
        mime = getattr(event, "mimetype", None)
        return mime if isinstance(mime, str) and mime else None

    def _event_filename(self, event: Any, attachment_type: str) -> str:
        body = getattr(event, "body", None)
        if isinstance(body, str) and body.strip():
            return self._safe_filename(Path(body).name)
        return self._DEFAULT_ATTACH_NAME if attachment_type == "file" else attachment_type

    def _build_attachment_path(
        self,
        event: Any,
        attachment_type: str,
        filename: str,
        mime: str | None,
    ) -> Path:
        safe_name = self._safe_filename(Path(filename).name)
        suffix = Path(safe_name).suffix
        if not suffix and mime:
            suffix = mimetypes.guess_extension(mime, strict=False) or ""
            safe_name = f"{safe_name}{suffix}" if suffix else safe_name
        stem = (Path(safe_name).stem or attachment_type)[:72]
        suffix = (Path(safe_name).suffix or suffix)[:16]
        event_id = self._safe_filename(str(getattr(event, "event_id", "") or "evt").lstrip("$"))
        event_prefix = (event_id[:24] or "evt").strip("_")
        return _sparkbot_media_dir("matrix") / f"{event_prefix}_{stem}{suffix}"

    async def _download_media_bytes(self, mxc_url: str) -> bytes | None:
        if self.client is None:
            return None
        try:
            response = await self.client.download(mxc=mxc_url)
        except Exception:
            return None
        body = getattr(response, "body", None)
        if isinstance(body, (bytes, bytearray)):
            return bytes(body)
        if isinstance(body, (str, Path)):
            path = Path(body)
            if path.is_file():
                try:
                    return path.read_bytes()
                except OSError:
                    return None
        return None

    def _decrypt_media_bytes(self, event: Any, ciphertext: bytes) -> bytes | None:
        key_obj = getattr(event, "key", None)
        hashes = getattr(event, "hashes", None)
        iv = getattr(event, "iv", None)
        key = key_obj.get("k") if isinstance(key_obj, dict) else None
        sha256 = hashes.get("sha256") if isinstance(hashes, dict) else None
        if not all(isinstance(value, str) for value in (key, sha256, iv)):
            return None
        try:
            from nio.crypto.attachments import decrypt_attachment

            return decrypt_attachment(ciphertext, key, sha256, iv)
        except Exception:
            logger.warning("Matrix media decrypt failed for event %s", getattr(event, "event_id", ""))
            return None

    async def _fetch_media_attachment(self, room: Any, event: Any) -> tuple[dict[str, Any] | None, str]:
        del room
        attachment_type = self._event_attachment_type(event)
        mime = self._event_mime(event)
        filename = self._event_filename(event, attachment_type)
        mxc_url = getattr(event, "url", None)
        failure = self._ATTACH_FAILED.format(filename)
        if not isinstance(mxc_url, str) or not mxc_url.startswith("mxc://"):
            return None, failure
        limit_bytes = await self._effective_media_limit_bytes()
        declared = self._event_declared_size_bytes(event)
        if declared is not None and declared > limit_bytes:
            return None, self._ATTACH_TOO_LARGE.format(filename)
        downloaded = await self._download_media_bytes(mxc_url)
        if downloaded is None:
            return None, failure
        encrypted = self._is_encrypted_media_event(event)
        data = self._decrypt_media_bytes(event, downloaded) if encrypted else downloaded
        if data is None:
            return None, failure
        if len(data) > limit_bytes:
            return None, self._ATTACH_TOO_LARGE.format(filename)
        path = self._build_attachment_path(event, attachment_type, filename, mime)
        try:
            path.write_bytes(data)
        except OSError:
            return None, failure
        attachment = {
            "type": attachment_type,
            "mime": mime,
            "filename": filename,
            "event_id": str(getattr(event, "event_id", "") or ""),
            "encrypted": encrypted,
            "size_bytes": len(data),
            "path": str(path),
            "mxc_url": mxc_url,
        }
        return attachment, self._ATTACH_MARKER.format(path)

    async def _set_typing(self, room_id: str, typing: bool) -> None:
        if self.client is None:
            return
        try:
            await self.client.room_typing(
                room_id=room_id,
                typing_state=typing,
                timeout=self._TYPING_NOTICE_TIMEOUT_MS,
            )
        except Exception:
            return

    async def _start_typing_keepalive(self, room_id: str) -> None:
        await self._stop_typing_keepalive(room_id, clear_typing=False)
        await self._set_typing(room_id, True)
        if not self._running:
            return

        async def keepalive() -> None:
            try:
                while self._running:
                    await asyncio.sleep(self._TYPING_KEEPALIVE_INTERVAL_MS / 1000)
                    await self._set_typing(room_id, True)
            except asyncio.CancelledError:
                return

        self._typing_tasks[room_id] = asyncio.create_task(keepalive())

    async def _stop_typing_keepalive(self, room_id: str, *, clear_typing: bool) -> None:
        task = self._typing_tasks.pop(room_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if clear_typing:
            await self._set_typing(room_id, False)


MOCHAT_MAX_SEEN_MESSAGE_IDS = 2000
MOCHAT_CURSOR_SAVE_DEBOUNCE_S = 0.5


@dataclass(slots=True)
class MochatBufferedEntry:
    raw_body: str
    author: str
    sender_name: str = ""
    sender_username: str = ""
    timestamp: int | None = None
    message_id: str = ""
    group_id: str = ""


@dataclass(slots=True)
class MochatDelayState:
    entries: list[MochatBufferedEntry] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    timer: asyncio.Task | None = None


@dataclass(slots=True)
class MochatTarget:
    id: str
    is_panel: bool


def _mochat_safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _mochat_str_field(src: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = src.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _make_mochat_synthetic_event(
    *,
    message_id: str,
    author: str,
    content: Any,
    meta: Any,
    group_id: str,
    converse_id: str,
    timestamp: Any = None,
    author_info: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messageId": message_id,
        "author": author,
        "content": content,
        "meta": _mochat_safe_dict(meta),
        "groupId": group_id,
        "converseId": converse_id,
    }
    if author_info is not None:
        payload["authorInfo"] = _mochat_safe_dict(author_info)
    return {
        "type": "message.add",
        "timestamp": timestamp or datetime.utcnow().isoformat(),
        "payload": payload,
    }


def _normalize_mochat_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if content is None:
        return ""
    try:
        return json.dumps(content, ensure_ascii=False)
    except TypeError:
        return str(content)


def _resolve_mochat_target(raw: str) -> MochatTarget:
    trimmed = (raw or "").strip()
    if not trimmed:
        return MochatTarget(id="", is_panel=False)
    lowered = trimmed.lower()
    cleaned = trimmed
    forced_panel = False
    for prefix in ("mochat:", "group:", "channel:", "panel:"):
        if lowered.startswith(prefix):
            cleaned = trimmed[len(prefix) :].strip()
            forced_panel = prefix in {"group:", "channel:", "panel:"}
            break
    if not cleaned:
        return MochatTarget(id="", is_panel=False)
    return MochatTarget(id=cleaned, is_panel=forced_panel or not cleaned.startswith("session_"))


def _extract_mochat_mention_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            ids.append(item.strip())
        elif isinstance(item, dict):
            for key in ("id", "userId", "_id"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    ids.append(candidate.strip())
                    break
    return ids


def _resolve_mochat_was_mentioned(payload: dict[str, Any], agent_user_id: str) -> bool:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        if meta.get("mentioned") is True or meta.get("wasMentioned") is True:
            return True
        for key in ("mentions", "mentionIds", "mentionedUserIds", "mentionedUsers"):
            if agent_user_id and agent_user_id in _extract_mochat_mention_ids(meta.get(key)):
                return True
    if not agent_user_id:
        return False
    content = payload.get("content")
    if not isinstance(content, str) or not content:
        return False
    return f"<@{agent_user_id}>" in content or f"@{agent_user_id}" in content


def _resolve_mochat_require_mention(
    config: MochatConfig,
    session_id: str,
    group_id: str,
) -> bool:
    groups = config.groups or {}
    for key in (group_id, session_id, "*"):
        if key and key in groups:
            return bool(groups[key].require_mention)
    return bool(config.mention.require_in_groups)


def _build_mochat_buffered_body(entries: list[MochatBufferedEntry], is_group: bool) -> str:
    if not entries:
        return ""
    if len(entries) == 1:
        return entries[0].raw_body
    lines: list[str] = []
    for entry in entries:
        if not entry.raw_body:
            continue
        if is_group:
            label = entry.sender_name.strip() or entry.sender_username.strip() or entry.author
            if label:
                lines.append(f"{label}: {entry.raw_body}")
                continue
        lines.append(entry.raw_body)
    return "\n".join(lines).strip()


def _parse_mochat_timestamp(value: Any) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


class MochatChannel(SparkBotChannel):
    name = "mochat"
    display_name = "Mochat"

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._http: Any | None = None
        self._socket: Any | None = None
        self._ws_connected = False
        self._ws_ready = False

        self._state_dir = get_path_service().project_root / "data" / "sparkbot" / "mochat"
        self._cursor_path = self._state_dir / "session_cursors.json"
        self._session_cursor: dict[str, int] = {}
        self._cursor_save_task: asyncio.Task | None = None

        self._session_set: set[str] = set()
        self._panel_set: set[str] = set()
        self._auto_discover_sessions = False
        self._auto_discover_panels = False
        self._cold_sessions: set[str] = set()
        self._session_by_converse: dict[str, str] = {}

        self._seen_set: dict[str, set[str]] = {}
        self._seen_queue: dict[str, deque[str]] = {}
        self._delay_states: dict[str, MochatDelayState] = {}
        self._fallback_mode = False
        self._session_fallback_tasks: dict[str, asyncio.Task] = {}
        self._panel_fallback_tasks: dict[str, asyncio.Task] = {}
        self._refresh_task: asyncio.Task | None = None
        self._target_locks: dict[str, asyncio.Lock] = {}

    async def start(self) -> None:
        if not self.config.claw_token:
            logger.warning("Mochat claw_token not configured; using in-memory channel")
            await super().start()
            return
        try:
            import httpx
        except Exception:
            logger.warning("Mochat channel requires httpx; using in-memory channel")
            await super().start()
            return

        self._running = True
        self._stop_event.clear()
        self._http = httpx.AsyncClient(timeout=30.0)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        await self._load_session_cursors()
        self._seed_targets_from_config()
        await self._refresh_targets(subscribe_new=False)
        if not await self._start_socket_client():
            await self._ensure_fallback_workers()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None
        await self._stop_fallback_workers()
        await self._cancel_delay_timers()
        if self._socket is not None:
            try:
                await self._socket.disconnect()
            except Exception:
                pass
            self._socket = None
        if self._cursor_save_task is not None:
            self._cursor_save_task.cancel()
            self._cursor_save_task = None
        await self._save_session_cursors()
        if self._http is not None:
            close = getattr(self._http, "aclose", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._http = None
        self._ws_connected = False
        self._ws_ready = False

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if not self.config.claw_token:
            await super().send(msg)
            return
        parts = [msg.content.strip()] if msg.content and msg.content.strip() else []
        parts.extend(str(item).strip() for item in msg.media or [] if str(item).strip())
        content = "\n".join(parts).strip()
        if not content:
            return

        target = _resolve_mochat_target(msg.chat_id)
        if not target.id:
            logger.warning("Mochat outbound target is empty")
            return
        is_panel = (target.is_panel or target.id in self._panel_set) and not target.id.startswith("session_")
        if is_panel:
            await self._api_send(
                "/api/claw/groups/panels/send",
                "panelId",
                target.id,
                content,
                msg.reply_to,
                self._read_group_id(msg.metadata),
            )
        else:
            await self._api_send(
                "/api/claw/sessions/send",
                "sessionId",
                target.id,
                content,
                msg.reply_to,
            )
        self.sent_messages.append(msg)

    def _seed_targets_from_config(self) -> None:
        sessions, self._auto_discover_sessions = self._normalize_id_list(self.config.sessions)
        panels, self._auto_discover_panels = self._normalize_id_list(self.config.panels)
        self._session_set.update(sessions)
        self._panel_set.update(panels)
        for session_id in sessions:
            if session_id not in self._session_cursor:
                self._cold_sessions.add(session_id)

    @staticmethod
    def _normalize_id_list(values: list[str]) -> tuple[list[str], bool]:
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        return sorted({value for value in cleaned if value != "*"}), "*" in cleaned

    async def _start_socket_client(self) -> bool:
        try:
            import socketio
        except Exception:
            logger.warning("python-socketio not installed; Mochat using polling fallback")
            return False
        serializer = "default"
        if not self.config.socket_disable_msgpack:
            try:
                import msgpack  # noqa: F401
            except Exception:
                logger.warning("msgpack not installed; Mochat websocket using JSON serializer")
            else:
                serializer = "msgpack"
        client = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=self.config.max_retry_attempts or None,
            reconnection_delay=max(0.1, self.config.socket_reconnect_delay_ms / 1000.0),
            reconnection_delay_max=max(0.1, self.config.socket_max_reconnect_delay_ms / 1000.0),
            logger=False,
            engineio_logger=False,
            serializer=serializer,
        )

        @client.event
        async def connect() -> None:
            self._ws_connected = True
            self._ws_ready = False
            subscribed = await self._subscribe_all()
            self._ws_ready = subscribed
            if subscribed:
                await self._stop_fallback_workers()
            else:
                await self._ensure_fallback_workers()

        @client.event
        async def disconnect() -> None:
            if not self._running:
                return
            self._ws_connected = False
            self._ws_ready = False
            await self._ensure_fallback_workers()

        @client.event
        async def connect_error(data: Any) -> None:
            logger.error("Mochat websocket connect error: %s", data)

        @client.on("claw.session.events")
        async def on_session_events(payload: dict[str, Any]) -> None:
            await self._handle_watch_payload(payload, "session")

        @client.on("claw.panel.events")
        async def on_panel_events(payload: dict[str, Any]) -> None:
            await self._handle_watch_payload(payload, "panel")

        for event_name in (
            "notify:chat.inbox.append",
            "notify:chat.message.add",
            "notify:chat.message.update",
            "notify:chat.message.recall",
            "notify:chat.message.delete",
        ):
            client.on(event_name, self._build_notify_handler(event_name))

        socket_url = (self.config.socket_url or self.config.base_url).strip().rstrip("/")
        socket_path = (self.config.socket_path or "/socket.io").strip().lstrip("/")
        try:
            self._socket = client
            await client.connect(
                socket_url,
                transports=["websocket"],
                socketio_path=socket_path,
                auth={"token": self.config.claw_token},
                wait_timeout=max(1.0, self.config.socket_connect_timeout_ms / 1000.0),
            )
            return True
        except Exception:
            logger.exception("Failed to connect Mochat websocket")
            try:
                await client.disconnect()
            except Exception:
                pass
            self._socket = None
            return False

    def _build_notify_handler(self, event_name: str) -> Callable[[Any], Awaitable[None]]:
        async def handler(payload: Any) -> None:
            if event_name == "notify:chat.inbox.append":
                await self._handle_notify_inbox_append(payload)
            elif event_name.startswith("notify:chat.message."):
                await self._handle_notify_chat_message(payload)

        return handler

    async def _subscribe_all(self) -> bool:
        ok = await self._subscribe_sessions(sorted(self._session_set))
        ok = await self._subscribe_panels(sorted(self._panel_set)) and ok
        if self._auto_discover_sessions or self._auto_discover_panels:
            await self._refresh_targets(subscribe_new=True)
        return ok

    async def _subscribe_sessions(self, session_ids: list[str]) -> bool:
        if not session_ids:
            return True
        for session_id in session_ids:
            if session_id not in self._session_cursor:
                self._cold_sessions.add(session_id)
        ack = await self._socket_call(
            "com.claw.im.subscribeSessions",
            {
                "sessionIds": session_ids,
                "cursors": self._session_cursor,
                "limit": self.config.watch_limit,
            },
        )
        if not ack.get("result"):
            logger.error("Mochat subscribeSessions failed: %s", ack.get("message", "unknown error"))
            return False
        data = ack.get("data")
        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            sessions = data.get("sessions")
            if isinstance(sessions, list):
                items = [item for item in sessions if isinstance(item, dict)]
            elif "sessionId" in data:
                items = [data]
        for item in items:
            await self._handle_watch_payload(item, "session")
        return True

    async def _subscribe_panels(self, panel_ids: list[str]) -> bool:
        if not self._auto_discover_panels and not panel_ids:
            return True
        ack = await self._socket_call("com.claw.im.subscribePanels", {"panelIds": panel_ids})
        if not ack.get("result"):
            logger.error("Mochat subscribePanels failed: %s", ack.get("message", "unknown error"))
            return False
        return True

    async def _socket_call(self, event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._socket is None:
            return {"result": False, "message": "socket not connected"}
        try:
            raw = await self._socket.call(event_name, payload, timeout=10)
        except Exception as exc:
            return {"result": False, "message": str(exc)}
        return raw if isinstance(raw, dict) else {"result": True, "data": raw}

    async def _refresh_loop(self) -> None:
        interval_s = max(1.0, self.config.refresh_interval_ms / 1000.0)
        while self._running:
            await asyncio.sleep(interval_s)
            try:
                await self._refresh_targets(subscribe_new=self._ws_ready)
            except Exception:
                logger.exception("Mochat refresh failed")
            if self._fallback_mode:
                await self._ensure_fallback_workers()

    async def _refresh_targets(self, subscribe_new: bool) -> None:
        if self._auto_discover_sessions:
            await self._refresh_sessions_directory(subscribe_new)
        if self._auto_discover_panels:
            await self._refresh_panels(subscribe_new)

    async def _refresh_sessions_directory(self, subscribe_new: bool) -> None:
        try:
            response = await self._post_json("/api/claw/sessions/list", {})
        except Exception:
            logger.exception("Mochat listSessions failed")
            return
        sessions = response.get("sessions")
        if not isinstance(sessions, list):
            return
        new_ids: list[str] = []
        for item in sessions:
            if not isinstance(item, dict):
                continue
            session_id = _mochat_str_field(item, "sessionId")
            if not session_id:
                continue
            if session_id not in self._session_set:
                self._session_set.add(session_id)
                new_ids.append(session_id)
                if session_id not in self._session_cursor:
                    self._cold_sessions.add(session_id)
            converse_id = _mochat_str_field(item, "converseId")
            if converse_id:
                self._session_by_converse[converse_id] = session_id
        if not new_ids:
            return
        if self._ws_ready and subscribe_new:
            await self._subscribe_sessions(new_ids)
        if self._fallback_mode:
            await self._ensure_fallback_workers()

    async def _refresh_panels(self, subscribe_new: bool) -> None:
        try:
            response = await self._post_json("/api/claw/groups/get", {})
        except Exception:
            logger.exception("Mochat getWorkspaceGroup failed")
            return
        raw_panels = response.get("panels")
        if not isinstance(raw_panels, list):
            return
        new_ids: list[str] = []
        for item in raw_panels:
            if not isinstance(item, dict):
                continue
            panel_type = item.get("type")
            if isinstance(panel_type, int) and panel_type != 0:
                continue
            panel_id = _mochat_str_field(item, "id", "_id")
            if panel_id and panel_id not in self._panel_set:
                self._panel_set.add(panel_id)
                new_ids.append(panel_id)
        if not new_ids:
            return
        if self._ws_ready and subscribe_new:
            await self._subscribe_panels(new_ids)
        if self._fallback_mode:
            await self._ensure_fallback_workers()

    async def _ensure_fallback_workers(self) -> None:
        if not self._running:
            return
        self._fallback_mode = True
        for session_id in sorted(self._session_set):
            task = self._session_fallback_tasks.get(session_id)
            if task is None or task.done():
                self._session_fallback_tasks[session_id] = asyncio.create_task(
                    self._session_watch_worker(session_id)
                )
        for panel_id in sorted(self._panel_set):
            task = self._panel_fallback_tasks.get(panel_id)
            if task is None or task.done():
                self._panel_fallback_tasks[panel_id] = asyncio.create_task(
                    self._panel_poll_worker(panel_id)
                )

    async def _stop_fallback_workers(self) -> None:
        self._fallback_mode = False
        tasks = [*self._session_fallback_tasks.values(), *self._panel_fallback_tasks.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._session_fallback_tasks.clear()
        self._panel_fallback_tasks.clear()

    async def _session_watch_worker(self, session_id: str) -> None:
        while self._running and self._fallback_mode:
            try:
                payload = await self._post_json(
                    "/api/claw/sessions/watch",
                    {
                        "sessionId": session_id,
                        "cursor": self._session_cursor.get(session_id, 0),
                        "timeoutMs": self.config.watch_timeout_ms,
                        "limit": self.config.watch_limit,
                    },
                )
                await self._handle_watch_payload(payload, "session")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Mochat watch fallback failed for %s", session_id)
                await asyncio.sleep(max(0.1, self.config.retry_delay_ms / 1000.0))

    async def _panel_poll_worker(self, panel_id: str) -> None:
        sleep_s = max(1.0, self.config.refresh_interval_ms / 1000.0)
        while self._running and self._fallback_mode:
            try:
                response = await self._post_json(
                    "/api/claw/groups/panels/messages",
                    {"panelId": panel_id, "limit": min(100, max(1, self.config.watch_limit))},
                )
                messages = response.get("messages")
                if isinstance(messages, list):
                    for item in reversed(messages):
                        if not isinstance(item, dict):
                            continue
                        event = _make_mochat_synthetic_event(
                            message_id=str(item.get("messageId") or ""),
                            author=str(item.get("author") or ""),
                            content=item.get("content"),
                            meta=item.get("meta"),
                            group_id=str(response.get("groupId") or ""),
                            converse_id=panel_id,
                            timestamp=item.get("createdAt"),
                            author_info=item.get("authorInfo"),
                        )
                        await self._process_inbound_event(panel_id, event, "panel")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Mochat panel polling failed for %s", panel_id)
            await asyncio.sleep(sleep_s)

    async def _handle_watch_payload(self, payload: dict[str, Any], target_kind: str) -> None:
        if not isinstance(payload, dict):
            return
        target_id = _mochat_str_field(payload, "sessionId", "panelId", "id")
        if not target_id:
            return
        lock = self._target_locks.setdefault(f"{target_kind}:{target_id}", asyncio.Lock())
        async with lock:
            previous_cursor = self._session_cursor.get(target_id, 0) if target_kind == "session" else 0
            payload_cursor = payload.get("cursor")
            if target_kind == "session" and isinstance(payload_cursor, int) and payload_cursor >= 0:
                self._mark_session_cursor(target_id, payload_cursor)
            raw_events = payload.get("events")
            if not isinstance(raw_events, list):
                return
            if target_kind == "session" and target_id in self._cold_sessions:
                self._cold_sessions.discard(target_id)
                return
            for event in raw_events:
                if not isinstance(event, dict):
                    continue
                seq = event.get("seq")
                if (
                    target_kind == "session"
                    and isinstance(seq, int)
                    and seq > self._session_cursor.get(target_id, previous_cursor)
                ):
                    self._mark_session_cursor(target_id, seq)
                if event.get("type") == "message.add":
                    await self._process_inbound_event(target_id, event, target_kind)

    async def _process_inbound_event(
        self,
        target_id: str,
        event: dict[str, Any],
        target_kind: str,
    ) -> None:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return
        author = _mochat_str_field(payload, "author")
        if not author or (self.config.agent_user_id and author == self.config.agent_user_id):
            return
        if not self.is_allowed(author):
            return
        message_id = _mochat_str_field(payload, "messageId")
        seen_key = f"{target_kind}:{target_id}"
        if message_id and self._remember_message_id(seen_key, message_id):
            return

        raw_body = _normalize_mochat_content(payload.get("content")) or "[empty message]"
        author_info = _mochat_safe_dict(payload.get("authorInfo"))
        sender_name = _mochat_str_field(author_info, "nickname", "email")
        sender_username = _mochat_str_field(author_info, "agentId")
        group_id = _mochat_str_field(payload, "groupId")
        is_group = bool(group_id)
        was_mentioned = _resolve_mochat_was_mentioned(payload, self.config.agent_user_id)
        require_mention = (
            target_kind == "panel"
            and is_group
            and _resolve_mochat_require_mention(self.config, target_id, group_id)
        )
        use_delay = target_kind == "panel" and self.config.reply_delay_mode == "non-mention"
        if require_mention and not was_mentioned and not use_delay:
            return

        entry = MochatBufferedEntry(
            raw_body=raw_body,
            author=author,
            sender_name=sender_name,
            sender_username=sender_username,
            timestamp=_parse_mochat_timestamp(event.get("timestamp")),
            message_id=message_id,
            group_id=group_id,
        )
        if use_delay:
            if was_mentioned:
                await self._flush_delayed_entries(seen_key, target_id, target_kind, "mention", entry)
            else:
                await self._enqueue_delayed_entry(seen_key, target_id, target_kind, entry)
            return
        await self._dispatch_entries(target_id, target_kind, [entry], was_mentioned)

    def _remember_message_id(self, key: str, message_id: str) -> bool:
        seen_set = self._seen_set.setdefault(key, set())
        seen_queue = self._seen_queue.setdefault(key, deque())
        if message_id in seen_set:
            return True
        seen_set.add(message_id)
        seen_queue.append(message_id)
        while len(seen_queue) > MOCHAT_MAX_SEEN_MESSAGE_IDS:
            seen_set.discard(seen_queue.popleft())
        return False

    async def _enqueue_delayed_entry(
        self,
        key: str,
        target_id: str,
        target_kind: str,
        entry: MochatBufferedEntry,
    ) -> None:
        state = self._delay_states.setdefault(key, MochatDelayState())
        async with state.lock:
            state.entries.append(entry)
            if state.timer is not None:
                state.timer.cancel()
            state.timer = asyncio.create_task(self._delay_flush_after(key, target_id, target_kind))

    async def _delay_flush_after(self, key: str, target_id: str, target_kind: str) -> None:
        await asyncio.sleep(max(0, self.config.reply_delay_ms) / 1000.0)
        await self._flush_delayed_entries(key, target_id, target_kind, "timer", None)

    async def _flush_delayed_entries(
        self,
        key: str,
        target_id: str,
        target_kind: str,
        reason: str,
        entry: MochatBufferedEntry | None,
    ) -> None:
        state = self._delay_states.setdefault(key, MochatDelayState())
        async with state.lock:
            if entry is not None:
                state.entries.append(entry)
            current = asyncio.current_task()
            if state.timer is not None and state.timer is not current:
                state.timer.cancel()
            state.timer = None
            entries = list(state.entries)
            state.entries.clear()
        if entries:
            await self._dispatch_entries(target_id, target_kind, entries, reason == "mention")

    async def _dispatch_entries(
        self,
        target_id: str,
        target_kind: str,
        entries: list[MochatBufferedEntry],
        was_mentioned: bool,
    ) -> None:
        if not entries:
            return
        last = entries[-1]
        is_group = bool(last.group_id)
        body = _build_mochat_buffered_body(entries, is_group) or "[empty message]"
        await self._handle_message(
            sender_id=last.author,
            chat_id=target_id,
            content=body,
            metadata={
                "message_id": last.message_id,
                "timestamp": last.timestamp,
                "is_group": is_group,
                "group_id": last.group_id,
                "sender_name": last.sender_name,
                "sender_username": last.sender_username,
                "target_kind": target_kind,
                "was_mentioned": was_mentioned,
                "buffered_count": len(entries),
            },
            session_key=f"mochat:{target_id}",
        )

    async def _cancel_delay_timers(self) -> None:
        for state in self._delay_states.values():
            if state.timer is not None:
                state.timer.cancel()
        self._delay_states.clear()

    async def _handle_notify_chat_message(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        group_id = _mochat_str_field(payload, "groupId")
        panel_id = _mochat_str_field(payload, "converseId", "panelId")
        if not group_id or not panel_id:
            return
        if self._panel_set and panel_id not in self._panel_set:
            return
        event = _make_mochat_synthetic_event(
            message_id=str(payload.get("_id") or payload.get("messageId") or ""),
            author=str(payload.get("author") or ""),
            content=payload.get("content"),
            meta=payload.get("meta"),
            group_id=group_id,
            converse_id=panel_id,
            timestamp=payload.get("createdAt"),
            author_info=payload.get("authorInfo"),
        )
        await self._process_inbound_event(panel_id, event, "panel")

    async def _handle_notify_inbox_append(self, payload: Any) -> None:
        if not isinstance(payload, dict) or payload.get("type") != "message":
            return
        detail = payload.get("payload")
        if not isinstance(detail, dict) or _mochat_str_field(detail, "groupId"):
            return
        converse_id = _mochat_str_field(detail, "converseId")
        if not converse_id:
            return
        session_id = self._session_by_converse.get(converse_id)
        if not session_id:
            await self._refresh_sessions_directory(self._ws_ready)
            session_id = self._session_by_converse.get(converse_id)
        if not session_id:
            return
        event = _make_mochat_synthetic_event(
            message_id=str(detail.get("messageId") or payload.get("_id") or ""),
            author=str(detail.get("messageAuthor") or ""),
            content=str(detail.get("messagePlainContent") or detail.get("messageSnippet") or ""),
            meta={"source": "notify:chat.inbox.append", "converseId": converse_id},
            group_id="",
            converse_id=converse_id,
            timestamp=payload.get("createdAt"),
        )
        await self._process_inbound_event(session_id, event, "session")

    def _mark_session_cursor(self, session_id: str, cursor: int) -> None:
        if cursor < 0 or cursor < self._session_cursor.get(session_id, 0):
            return
        self._session_cursor[session_id] = cursor
        if self._cursor_save_task is None or self._cursor_save_task.done():
            self._cursor_save_task = asyncio.create_task(self._save_cursor_debounced())

    async def _save_cursor_debounced(self) -> None:
        await asyncio.sleep(MOCHAT_CURSOR_SAVE_DEBOUNCE_S)
        await self._save_session_cursors()

    async def _load_session_cursors(self) -> None:
        if not self._cursor_path.exists():
            return
        try:
            data = json.loads(self._cursor_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to read Mochat cursor file")
            return
        cursors = data.get("cursors") if isinstance(data, dict) else None
        if not isinstance(cursors, dict):
            return
        for session_id, cursor in cursors.items():
            if isinstance(session_id, str) and isinstance(cursor, int) and cursor >= 0:
                self._session_cursor[session_id] = cursor

    async def _save_session_cursors(self) -> None:
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            self._cursor_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "updatedAt": datetime.utcnow().isoformat(),
                        "cursors": self._session_cursor,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save Mochat cursor file")

    async def _ensure_http(self) -> Any:
        if self._http is not None:
            return self._http
        import httpx

        self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        http = await self._ensure_http()
        url = f"{self.config.base_url.strip().rstrip('/')}{path}"
        response = await http.post(
            url,
            headers={"Content-Type": "application/json", "X-Claw-Token": self.config.claw_token},
            json=payload,
        )
        is_success = getattr(response, "is_success", None)
        status_code = getattr(response, "status_code", 200)
        if is_success is False or status_code >= 400:
            body = str(getattr(response, "text", ""))[:200]
            raise RuntimeError(f"Mochat HTTP {status_code}: {body}")
        try:
            parsed = response.json()
        except Exception:
            parsed = getattr(response, "text", "")
        if isinstance(parsed, dict) and isinstance(parsed.get("code"), int):
            if parsed["code"] != 200:
                message = str(parsed.get("message") or parsed.get("name") or "request failed")
                raise RuntimeError(f"Mochat API error: {message} (code={parsed['code']})")
            data = parsed.get("data")
            return data if isinstance(data, dict) else {}
        return parsed if isinstance(parsed, dict) else {}

    async def _api_send(
        self,
        path: str,
        id_key: str,
        id_value: str,
        content: str,
        reply_to: str | None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {id_key: id_value, "content": content}
        if reply_to:
            body["replyTo"] = reply_to
        if group_id:
            body["groupId"] = group_id
        return await self._post_json(path, body)

    @staticmethod
    def _read_group_id(metadata: dict[str, Any]) -> str | None:
        if not isinstance(metadata, dict):
            return None
        value = metadata.get("group_id") or metadata.get("groupId")
        return value.strip() if isinstance(value, str) and value.strip() else None


class QQChannel(SparkBotChannel):
    name = "qq"
    display_name = "QQ"

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._client: Any | None = None
        self._processed_ids: OrderedDict[str, None] = OrderedDict()
        self._msg_seq = 1
        self._chat_type_cache: dict[str, str] = {}

    async def start(self) -> None:
        if not self.config.app_id or not self.config.secret:
            logger.warning("QQ credentials not configured; using in-memory channel")
            await super().start()
            return
        try:
            import botpy
        except Exception:
            logger.warning("QQ channel requires qq-botpy; using in-memory channel")
            await super().start()
            return

        channel = self
        intents = botpy.Intents(public_messages=True, direct_message=True)

        class QQBot(botpy.Client):
            def __init__(self) -> None:
                super().__init__(intents=intents, ext_handlers=False)

            async def on_c2c_message_create(self, message: Any) -> None:
                await channel._on_message(message, is_group=False)

            async def on_direct_message_create(self, message: Any) -> None:
                await channel._on_message(message, is_group=False)

            async def on_group_at_message_create(self, message: Any) -> None:
                await channel._on_message(message, is_group=True)

        self._running = True
        self._stop_event.clear()
        self._client = QQBot()
        while self._running:
            try:
                await self._client.start(appid=self.config.app_id, secret=self.config.secret)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("QQ bot connection failed")
                if self._running:
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._client = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._client is None:
            logger.warning("QQ client not initialized; outbound message was not sent")
            await super().send(msg)
            return

        self._msg_seq += 1
        use_markdown = self.config.msg_format == "markdown"
        payload: dict[str, Any] = {
            "msg_type": 2 if use_markdown else 0,
            "msg_id": msg.metadata.get("message_id"),
            "msg_seq": self._msg_seq,
        }
        if use_markdown:
            payload["markdown"] = {"content": msg.content}
        else:
            payload["content"] = msg.content

        chat_type = self._chat_type_cache.get(msg.chat_id, "c2c")
        if chat_type == "group":
            await self._client.api.post_group_message(group_openid=msg.chat_id, **payload)
        else:
            await self._client.api.post_c2c_message(openid=msg.chat_id, **payload)
        self.sent_messages.append(msg)

    async def _on_message(self, data: Any, is_group: bool = False) -> bool:
        message_id = str(getattr(data, "id", "") or "")
        if message_id:
            if message_id in self._processed_ids:
                return False
            self._processed_ids[message_id] = None
            while len(self._processed_ids) > 1000:
                self._processed_ids.popitem(last=False)

        content = str(getattr(data, "content", "") or "").strip()
        if not content:
            return False
        author = getattr(data, "author", None)
        if is_group:
            chat_id = str(getattr(data, "group_openid", "") or "")
            user_id = str(getattr(author, "member_openid", "") or "unknown")
            self._chat_type_cache[chat_id] = "group"
        else:
            chat_id = str(
                getattr(author, "id", None)
                or getattr(author, "user_openid", None)
                or "unknown"
            )
            user_id = chat_id
            self._chat_type_cache[chat_id] = "c2c"
        if not chat_id:
            return False
        return await self._handle_message(
            sender_id=user_id,
            chat_id=chat_id,
            content=content,
            metadata={"message_id": message_id},
            session_key=f"qq:{chat_id}",
        )


class WecomChannel(SparkBotChannel):
    name = "wecom"
    display_name = "WeCom"
    _MSG_TYPE_LABELS = {
        "image": "[image]",
        "voice": "[voice]",
        "file": "[file]",
        "mixed": "[mixed content]",
    }

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._client: Any | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._generate_req_id: Callable[[str], str] | None = None
        self._chat_frames: dict[str, Any] = {}

    async def start(self) -> None:
        if not self.config.bot_id or not self.config.secret:
            logger.warning("WeCom credentials not configured; using in-memory channel")
            await super().start()
            return
        try:
            from wecom_aibot_sdk import WSClient, generate_req_id
        except Exception:
            logger.warning("WeCom channel requires wecom_aibot_sdk; using in-memory channel")
            await super().start()
            return

        self._running = True
        self._stop_event.clear()
        self._generate_req_id = generate_req_id
        self._client = WSClient(
            {
                "bot_id": self.config.bot_id,
                "secret": self.config.secret,
                "reconnect_interval": 1000,
                "max_reconnect_attempts": -1,
                "heartbeat_interval": 30000,
            }
        )
        for name, handler in {
            "connected": self._on_connected,
            "authenticated": self._on_authenticated,
            "disconnected": self._on_disconnected,
            "error": self._on_error,
            "message.text": self._on_text_message,
            "message.image": self._on_image_message,
            "message.voice": self._on_voice_message,
            "message.file": self._on_file_message,
            "message.mixed": self._on_mixed_message,
            "event.enter_chat": self._on_enter_chat,
        }.items():
            self._client.on(name, handler)
        await self._client.connect_async()
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._client is not None:
            disconnect = getattr(self._client, "disconnect", None)
            if callable(disconnect):
                result = disconnect()
                if asyncio.iscoroutine(result):
                    await result
            self._client = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._client is None:
            logger.warning("WeCom client not initialized; outbound message was not sent")
            await super().send(msg)
            return
        content = (msg.content or "").strip()
        if not content:
            return
        frame = self._chat_frames.get(msg.chat_id)
        if frame is None:
            logger.warning("No WeCom frame found for chat %s; cannot reply", msg.chat_id)
            return
        generate_req_id = self._generate_req_id or (lambda prefix: f"{prefix}-{uuid.uuid4().hex}")
        stream_id = generate_req_id("stream")
        await self._client.reply_stream(frame, stream_id, content, finish=True)
        self.sent_messages.append(msg)

    async def _on_connected(self, _frame: Any) -> None:
        return None

    async def _on_authenticated(self, _frame: Any) -> None:
        return None

    async def _on_disconnected(self, _frame: Any) -> None:
        return None

    async def _on_error(self, frame: Any) -> None:
        logger.error("WeCom error: %s", frame)

    async def _on_text_message(self, frame: Any) -> bool:
        return await self._process_message(frame, "text")

    async def _on_image_message(self, frame: Any) -> bool:
        return await self._process_message(frame, "image")

    async def _on_voice_message(self, frame: Any) -> bool:
        return await self._process_message(frame, "voice")

    async def _on_file_message(self, frame: Any) -> bool:
        return await self._process_message(frame, "file")

    async def _on_mixed_message(self, frame: Any) -> bool:
        return await self._process_message(frame, "mixed")

    async def _on_enter_chat(self, frame: Any) -> None:
        body = self._frame_body(frame)
        chat_id = str(body.get("chatid") or "")
        if not chat_id or not self.config.welcome_message or self._client is None:
            return
        await self._client.reply_welcome(
            frame,
            {"msgtype": "text", "text": {"content": self.config.welcome_message}},
        )

    async def _process_message(self, frame: Any, msg_type: str) -> bool:
        body = self._frame_body(frame)
        if not body:
            return False
        message_id = str(body.get("msgid") or f"{body.get('chatid', '')}_{body.get('sendertime', '')}")
        if message_id:
            if message_id in self._processed_message_ids:
                return False
            self._processed_message_ids[message_id] = None
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

        from_info = body.get("from") if isinstance(body.get("from"), dict) else {}
        sender_id = str(from_info.get("userid") or "unknown")
        chat_type = str(body.get("chattype") or "single")
        chat_id = str(body.get("chatid") or sender_id)
        content_parts: list[str] = []
        media_paths: list[str] = []

        if msg_type == "text":
            text = ((body.get("text") or {}).get("content") if isinstance(body.get("text"), dict) else "")
            if text:
                content_parts.append(str(text))
        elif msg_type == "image":
            path = await self._download_media_from_body(body.get("image"), "image")
            if path:
                media_paths.append(path)
                content_parts.append(f"[image: {Path(path).name}]\n[Image: source: {path}]")
            else:
                content_parts.append("[image: download failed]")
        elif msg_type == "voice":
            voice = body.get("voice") if isinstance(body.get("voice"), dict) else {}
            voice_content = str(voice.get("content") or "")
            content_parts.append(f"[voice] {voice_content}".strip() if voice_content else "[voice]")
        elif msg_type == "file":
            file_info = body.get("file") if isinstance(body.get("file"), dict) else {}
            file_name = str(file_info.get("name") or "unknown")
            path = await self._download_media_from_body(file_info, "file", file_name)
            if path:
                media_paths.append(path)
                content_parts.append(f"[file: {file_name}]\n[File: source: {path}]")
            else:
                content_parts.append(f"[file: {file_name}: download failed]")
        elif msg_type == "mixed":
            mixed = body.get("mixed") if isinstance(body.get("mixed"), dict) else {}
            for item in mixed.get("item", []) if isinstance(mixed.get("item"), list) else []:
                item_type = item.get("type") if isinstance(item, dict) else ""
                if item_type == "text" and isinstance(item.get("text"), dict):
                    text = item["text"].get("content")
                    if text:
                        content_parts.append(str(text))
                else:
                    content_parts.append(self._MSG_TYPE_LABELS.get(str(item_type), f"[{item_type}]"))
        else:
            content_parts.append(self._MSG_TYPE_LABELS.get(msg_type, f"[{msg_type}]"))

        content = "\n".join(part for part in content_parts if part)
        if not content:
            return False
        self._chat_frames[chat_id] = frame
        return await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media_paths,
            metadata={
                "message_id": message_id,
                "msg_type": msg_type,
                "chat_type": chat_type,
            },
            session_key=f"wecom:{chat_id}",
        )

    async def _download_media_from_body(
        self,
        info: Any,
        media_type: str,
        filename: str | None = None,
    ) -> str | None:
        if not isinstance(info, dict):
            return None
        file_url = str(info.get("url") or "")
        aes_key = str(info.get("aeskey") or "")
        if not file_url or not aes_key:
            return None
        return await self._download_and_save_media(file_url, aes_key, media_type, filename)

    async def _download_and_save_media(
        self,
        file_url: str,
        aes_key: str,
        media_type: str,
        filename: str | None = None,
    ) -> str | None:
        if self._client is None:
            return None
        try:
            data, remote_name = await self._client.download_file(file_url, aes_key)
        except Exception:
            logger.exception("WeCom media download failed")
            return None
        if not data:
            return None
        name = Path(filename or remote_name or f"{media_type}_{abs(hash(file_url)) % 100000}").name
        path = _sparkbot_media_dir("wecom") / name
        path.write_bytes(data)
        return str(path)

    @staticmethod
    def _frame_body(frame: Any) -> dict[str, Any]:
        if hasattr(frame, "body"):
            body = frame.body or {}
        elif isinstance(frame, dict):
            body = frame.get("body", frame)
        else:
            body = {}
        return body if isinstance(body, dict) else {}


class WhatsAppChannel(SparkBotChannel):
    name = "whatsapp"
    display_name = "WhatsApp"

    def __init__(self, config: Any, bus: SparkBotMessageBus) -> None:
        super().__init__(config, bus)
        self._ws: Any | None = None
        self._connected = False
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()

    async def start(self) -> None:
        """Connect to a WhatsApp bridge WebSocket and forward inbound messages."""
        try:
            import websockets
        except Exception as exc:
            raise RuntimeError("WhatsApp channel requires the websockets package.") from exc

        self._running = True
        self._stop_event.clear()
        while self._running:
            try:
                async with websockets.connect(self.config.bridge_url) as ws:
                    self._ws = ws
                    if self.config.bridge_token:
                        await ws.send(
                            json.dumps(
                                {"type": "auth", "token": self.config.bridge_token},
                                ensure_ascii=False,
                            )
                        )
                    self._connected = True
                    async for message in ws:
                        await self._handle_bridge_message(message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("WhatsApp bridge connection failed")
                self._connected = False
                self._ws = None
                if self._running:
                    await asyncio.sleep(5)
            finally:
                self._connected = False
                self._ws = None

    async def stop(self) -> None:
        self._running = False
        self._connected = False
        self._stop_event.set()
        if self._ws is not None:
            close = getattr(self._ws, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._ws = None

    async def send(self, msg: SparkBotOutboundMessage) -> None:
        if self._ws is None or not self._connected:
            logger.warning("WhatsApp bridge not connected; outbound message was not sent")
            return
        payload: dict[str, Any] = {
            "type": "send",
            "to": msg.chat_id,
            "text": msg.content,
        }
        if msg.reply_to:
            payload["replyTo"] = msg.reply_to
        if msg.media:
            payload["media"] = msg.media
        await self._ws.send(json.dumps(payload, ensure_ascii=False))
        self.sent_messages.append(msg)

    async def _handle_bridge_message(self, raw: str | bytes) -> None:
        try:
            data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Invalid JSON from WhatsApp bridge")
            return
        if not isinstance(data, dict):
            return

        msg_type = data.get("type")
        if msg_type == "message":
            await self._handle_bridge_inbound_message(data)
            return
        if msg_type == "status":
            self._connected = data.get("status") == "connected"
            return
        if msg_type == "qr":
            logger.info("Scan the WhatsApp bridge QR code in the bridge terminal")
            return
        if msg_type == "error":
            logger.error("WhatsApp bridge error: %s", data.get("error"))

    async def _handle_bridge_inbound_message(self, data: dict[str, Any]) -> None:
        message_id = str(data.get("id") or "")
        if message_id:
            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

        sender = str(data.get("sender") or "")
        pn = str(data.get("pn") or "")
        user_id = pn or sender
        sender_id = user_id.split("@", 1)[0] if "@" in user_id else user_id
        content = str(data.get("content") or "")
        if content == "[Voice Message]":
            content = "[Voice Message: Transcription not available for WhatsApp yet]"

        media_paths = self._normalize_bridge_media(data.get("media"))
        for path in media_paths:
            mime, _ = mimetypes.guess_type(path)
            media_type = "image" if mime and mime.startswith("image/") else "file"
            media_tag = f"[{media_type}: {path}]"
            content = f"{content}\n{media_tag}" if content else media_tag

        await self._handle_message(
            sender_id=sender_id,
            chat_id=sender,
            content=content,
            media=media_paths,
            metadata={
                "message_id": message_id,
                "timestamp": data.get("timestamp"),
                "is_group": bool(data.get("isGroup", False)),
            },
        )

    @staticmethod
    def _normalize_bridge_media(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result


def discover_builtin_channels() -> dict[str, type]:
    return {
        "telegram": TelegramChannel,
        "slack": SlackChannel,
        "discord": DiscordChannel,
        "dingtalk": DingTalkChannel,
        "email": EmailChannel,
        "feishu": FeishuChannel,
        "matrix": MatrixChannel,
        "mochat": MochatChannel,
        "qq": QQChannel,
        "wecom": WecomChannel,
        "whatsapp": WhatsAppChannel,
    }


class SparkBotChannelManager:
    """Instantiate and manage enabled NG SparkBot channels."""

    def __init__(self, channels_config: ChannelsConfig, bus: SparkBotMessageBus) -> None:
        self.channels_config = channels_config
        self.bus = bus
        self.transcription_api_key = (
            channels_config.transcription_api_key or os.environ.get("GROQ_API_KEY", "")
        )
        self.channels: dict[str, SparkBotChannel] = {}
        self._init_channels()

    def _init_channels(self) -> None:
        for name, channel_cls in discover_builtin_channels().items():
            section = getattr(self.channels_config, name, None)
            if section is None or not getattr(section, "enabled", False):
                continue
            channel = channel_cls(section, self.bus)
            channel.transcription_api_key = self.transcription_api_key
            self.channels[name] = channel
        self._validate_allow_from()

    def _validate_allow_from(self) -> None:
        for name, channel in self.channels.items():
            allow_from = getattr(channel.config, "allow_from", None)
            if allow_from == []:
                raise ValueError(
                    f'Channel "{name}" has empty allow_from; use ["*"] or explicit ids.'
                )

    async def start_all(self) -> None:
        await asyncio.gather(
            *(channel.start() for channel in self.channels.values()),
            return_exceptions=True,
        )

    async def stop_all(self) -> None:
        for name, channel in self.channels.items():
            try:
                await channel.stop()
            except Exception:
                logger.exception("Error stopping SparkBot channel '%s'", name)

    def get_channel(self, name: str) -> SparkBotChannel | None:
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        return {
            name: {"enabled": True, "running": channel.is_running}
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        return list(self.channels)


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
                *[
                    task
                    for task_id in task_ids
                    if (task := self._running.get(task_id)) is not None
                ],
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
            lines.append(f"- {record.label} {record.id}: {record.status} - {record.instruction[:80]}")
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


_TEAM_FINISHED_STATUSES = {"completed", "stopped"}


def _team_timestamp() -> str:
    return datetime.now().isoformat()


@dataclass(slots=True)
class SparkBotTeamTask:
    id: str
    title: str
    description: str = ""
    owner: str | None = None
    status: str = "pending"
    depends_on: list[str] = field(default_factory=list)
    plan: str | None = None
    result: str | None = None
    requires_approval: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SparkBotTeamTask":
        tool_calls = data.get("tool_calls") or data.get("toolCalls") or []
        if not isinstance(tool_calls, list):
            tool_calls = []
        if not tool_calls and (data.get("tool") or data.get("tool_name") or data.get("toolName")):
            tool_calls = [
                {
                    "name": data.get("tool") or data.get("tool_name") or data.get("toolName"),
                    "arguments": data.get("arguments") or data.get("tool_args") or data.get("toolArgs") or {},
                }
            ]
        tool_results = data.get("tool_results") or data.get("toolResults") or []
        if not isinstance(tool_results, list):
            tool_results = []
        artifacts = data.get("artifacts") or []
        if not isinstance(artifacts, list):
            artifacts = []
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            owner=data.get("owner"),
            status=str(data.get("status") or "pending"),
            depends_on=[str(item) for item in data.get("depends_on", []) or []],
            plan=data.get("plan"),
            result=data.get("result"),
            requires_approval=bool(data.get("requires_approval", False)),
            tool_calls=[
                dict(item)
                for item in tool_calls
                if isinstance(item, dict)
            ],
            tool_results=[
                dict(item)
                for item in tool_results
                if isinstance(item, dict)
            ],
            artifacts=[
                dict(item)
                for item in artifacts
                if isinstance(item, dict)
            ],
            last_error=data.get("last_error") or data.get("lastError"),
        )


@dataclass(slots=True)
class SparkBotTeamMember:
    name: str
    role: str
    model: str | None = None
    status: str = "idle"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SparkBotTeamMember":
        return cls(
            name=str(data.get("name") or ""),
            role=str(data.get("role") or ""),
            model=data.get("model"),
            status=str(data.get("status") or "idle"),
        )


@dataclass(slots=True)
class SparkBotTeamState:
    team_id: str
    run_id: str
    mission: str = ""
    lead: str = "lead"
    members: list[SparkBotTeamMember] = field(default_factory=list)
    status: str = "active"
    created_at: str = field(default_factory=_team_timestamp)
    updated_at: str = field(default_factory=_team_timestamp)
    session_key: str = "web:web"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SparkBotTeamState":
        return cls(
            team_id=str(data.get("team_id") or data.get("teamId") or ""),
            run_id=str(data.get("run_id") or data.get("runId") or data.get("team_id") or ""),
            mission=str(data.get("mission") or ""),
            lead=str(data.get("lead") or "lead"),
            members=[
                SparkBotTeamMember.from_json(item)
                for item in data.get("members", []) or []
                if isinstance(item, dict)
            ],
            status=str(data.get("status") or "active"),
            created_at=str(data.get("created_at") or data.get("createdAt") or _team_timestamp()),
            updated_at=str(data.get("updated_at") or data.get("updatedAt") or _team_timestamp()),
            session_key=str(data.get("session_key") or data.get("sessionKey") or "web:web"),
        )


@dataclass(slots=True)
class SparkBotTeamMail:
    id: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: str = field(default_factory=_team_timestamp)
    read_by: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SparkBotTeamMail":
        return cls(
            id=str(data.get("id") or ""),
            from_agent=str(data.get("from_agent") or data.get("fromAgent") or ""),
            to_agent=str(data.get("to_agent") or data.get("toAgent") or ""),
            content=str(data.get("content") or ""),
            timestamp=str(data.get("timestamp") or _team_timestamp()),
            read_by=[str(item) for item in data.get("read_by", []) or []],
        )


@dataclass(slots=True)
class SparkBotTeamRuntime:
    session_key: str
    run_dir: Path
    state: SparkBotTeamState
    worker_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    prompted_approvals: set[str] = field(default_factory=set)

    @property
    def config_path(self) -> Path:
        return self.run_dir / "config.json"

    @property
    def tasks_path(self) -> Path:
        return self.run_dir / "tasks.json"

    @property
    def events_path(self) -> Path:
        return self.run_dir / "events.jsonl"

    @property
    def mailbox_path(self) -> Path:
        return self.run_dir / "mailbox.jsonl"


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
        pending_approval = [
            task for task in tasks if task.status == "awaiting_approval"
        ]
        member_text = ", ".join(
            f"{member.name}={member.status}" for member in runtime.state.members
        ) or "none"
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
        reject_hit = any(token in lowered for token in ("reject", "decline", "deny", "拒绝", "驳回"))
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
                if task.owner == name and task.status in {"planning", "awaiting_approval", "in_progress"}
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
            self._append_event(runtime, "risk_gate", f"Paused risky instruction: {normalized[:140]}")
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
        return [
            SparkBotTeamTask.from_json(item)
            for item in data
            if isinstance(item, dict)
        ]

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
        member_lines = "\n".join(
            (
                f"- {member.name}: {member.role} ({member.status}) "
                f"[{self._current_task_label(tasks, member.name)}]"
            )
            for member in runtime.state.members
        ) or "- none"
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
            self._append_event(runtime, "worker_message", f"{worker_name} -> {to_agent}: {content[:120]}")
            return f"Sent message to {to_agent}"
        if action == "mail_read":
            unread = self._read_unread_mail(runtime, worker_name)
            return "\n".join(f"- [{mail.from_agent}] {mail.content}" for mail in unread) or "No unread messages."
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
            lambda done, key=runtime.session_key, worker=worker_name: self._cleanup_worker(key, worker, done)
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
                    complete_result = self._complete_task(runtime, current.id, worker_name, final_result)
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
        self._append_event(runtime, "task_plan_submitted", f"{worker_name} submitted plan for {task_id}")
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
            if task.owner == worker_name and task.status in {"planning", "awaiting_approval", "in_progress"}:
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
            tool_name = str(raw.get("name") or raw.get("tool") or raw.get("tool_name") or "").strip()
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
            return [
                dict(item)
                for item in result.sources
                if isinstance(item, dict)
            ]
        if isinstance(result, dict):
            sources = result.get("sources") or []
            return [
                dict(item)
                for item in sources
                if isinstance(item, dict)
            ] if isinstance(sources, list) else []
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
            filename = str(artifact_names[index]) if index < len(artifact_names) else Path(str(path)).name
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
                    key = str(artifact.get("path") or artifact.get("file") or artifact.get("url") or "")
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
        return (safe[:80] or "session")

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
            if task.owner == owner and task.status in {"planning", "awaiting_approval", "in_progress"}:
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
                    enum=["create", "resume", "shutdown", "board", "approve", "reject", "message", "add_task"],
                ),
                ToolParameter(name="team_id", type="string", description="Team or run id.", required=False),
                ToolParameter(name="members", type="array", description="Optional member specs.", required=False),
                ToolParameter(name="tasks", type="array", description="Optional task specs.", required=False),
                ToolParameter(name="notes", type="string", description="Shared notes.", required=False),
                ToolParameter(name="mission", type="string", description="Team mission.", required=False),
                ToolParameter(name="task_id", type="string", description="Task id.", required=False),
                ToolParameter(name="reason", type="string", description="Rejection reason.", required=False),
                ToolParameter(name="to", type="string", description="Message recipient.", required=False),
                ToolParameter(name="content", type="string", description="Message content.", required=False),
                ToolParameter(name="task", type="object", description="Task to add.", required=False),
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
                ToolParameter(name="task_id", type="string", description="Task id.", required=False),
                ToolParameter(name="result", type="string", description="Completion result.", required=False),
                ToolParameter(name="plan", type="string", description="Approval plan.", required=False),
                ToolParameter(name="to", type="string", description="Message recipient.", required=False),
                ToolParameter(name="content", type="string", description="Message content.", required=False),
                ToolParameter(name="tool_name", type="string", description="NG tool name.", required=False),
                ToolParameter(name="arguments", type="object", description="Tool arguments.", required=False),
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
                ToolParameter(name="content", type="string", description="Message content to send."),
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
        chat_id = str(kwargs.get("chat_id") or kwargs.get("chatId") or self._chat_id_var.get() or "")
        if not content:
            return ToolResult(content="Error: content is required", success=False)
        if not channel or not chat_id:
            return ToolResult(content="Error: No target channel/chat specified", success=False)

        media_raw = kwargs.get("media") or []
        media = [str(item) for item in media_raw] if isinstance(media_raw, list) else [str(media_raw)]
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
                    return ToolResult(content="Error: every_seconds must be positive", success=False)
                schedule = SparkBotCronSchedule(kind="every", every_ms=seconds * 1000)
            elif cron_expr:
                schedule = SparkBotCronSchedule(kind="cron", expr=str(cron_expr), tz=str(tz) if tz else None)
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
        include_disabled = bool(kwargs.get("include_disabled", kwargs.get("includeDisabled", False)))
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
        return ToolResult(content=f"Job {job_id} not found", success=False, metadata={"job_id": job_id})

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
            str(config.agent.reasoning_effort).strip()
            if config.agent.reasoning_effort
            else None
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
                "/cron add cron \"<expr>\" [tz=<iana>] <message>\n"
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

    def _load_session_history(self, chat_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
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
            if not calls_raw and (parsed.get("name") or parsed.get("tool") or parsed.get("tool_name")):
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


class SparkBotHeartbeatService:
    """Periodic HEARTBEAT.md checker for proactive SparkBot reminders."""

    def __init__(
        self,
        *,
        workspace: Path,
        model: str | None = None,
        on_execute: Callable[[str], Awaitable[str]] | None = None,
        on_notify: Callable[[str], Awaitable[None]] | None = None,
        interval_s: int = 30 * 60,
        enabled: bool = True,
    ) -> None:
        self.workspace = workspace
        self.model = model
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"

    @property
    def task(self) -> asyncio.Task | None:
        return self._task

    async def start(self) -> None:
        if not self.enabled or self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="SparkBot:heartbeat")

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval_s)
                if self._running:
                    await self.tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SparkBot heartbeat tick failed")

    async def tick(self) -> str | None:
        content = self._read_heartbeat_file()
        if not content:
            return None
        action, tasks = await self._decide(content)
        if action != "run" or not tasks or self.on_execute is None:
            return None
        response = await self.on_execute(tasks)
        if response and self.on_notify is not None:
            if await self._should_notify_response(response, tasks):
                await self.on_notify(response)
        return response

    async def trigger_now(self) -> str | None:
        return await self.tick()

    def _read_heartbeat_file(self) -> str | None:
        try:
            content = self.heartbeat_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return content or None

    async def _should_notify_response(self, response: str, task_context: str) -> bool:
        prompt = (
            "You are a notification gate for a background SparkBot task. "
            "Decide whether the user should be notified about the result. "
            "Return only JSON like "
            '{"should_notify":true,"reason":"actionable result"}.\n\n'
            "Notify for actionable information, errors, completed deliverables, "
            "or explicit reminders. Suppress routine checks with nothing new.\n\n"
            f"## Original task\n{task_context}\n\n"
            f"## Agent response\n{response}"
        )
        try:
            raw = await llm_complete(prompt=prompt, model=self.model)
        except Exception:
            return True
        return self._parse_should_notify(raw)

    @staticmethod
    def _parse_should_notify(raw: Any) -> bool:
        if isinstance(raw, dict):
            data = raw
        else:
            parsed = extract_json_from_text(str(raw))
            data = parsed if isinstance(parsed, dict) else {}
        value = data.get("should_notify", True)
        if isinstance(value, str):
            return value.strip().lower() not in {"false", "0", "no", "skip", "suppress"}
        return bool(value)

    async def _decide(self, content: str) -> tuple[str, str]:
        prompt = (
            "You are a SparkBot heartbeat checker. Read HEARTBEAT.md and return "
            'only JSON like {"action":"skip","tasks":""} or '
            '{"action":"run","tasks":"short task summary"}.\n\n'
            f"HEARTBEAT.md:\n{content}"
        )
        try:
            raw = await llm_complete(prompt=prompt, model=self.model)
        except Exception:
            return "skip", ""

        data = self._parse_decision(raw)
        action = str(data.get("action", "skip")).lower()
        tasks = str(data.get("tasks", "")).strip()
        if action not in {"skip", "run"}:
            action = "skip"
        return action, tasks

    @staticmethod
    def _parse_decision(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        text = str(raw).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end <= start:
                return {"action": "skip", "tasks": ""}
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {"action": "skip", "tasks": ""}
        return parsed if isinstance(parsed, dict) else {"action": "skip", "tasks": ""}


@dataclass(slots=True)
class SparkBotCronSchedule:
    kind: Literal["at", "every", "cron"]
    at_ms: int | None = None
    every_ms: int | None = None
    expr: str | None = None
    tz: str | None = None


@dataclass(slots=True)
class SparkBotCronPayload:
    kind: Literal["system_event", "agent_turn"] = "agent_turn"
    message: str = ""
    deliver: bool = False
    channel: str | None = None
    to: str | None = None


@dataclass(slots=True)
class SparkBotCronJobState:
    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None


@dataclass(slots=True)
class SparkBotCronJob:
    id: str
    name: str
    enabled: bool = True
    schedule: SparkBotCronSchedule = field(
        default_factory=lambda: SparkBotCronSchedule(kind="every")
    )
    payload: SparkBotCronPayload = field(default_factory=SparkBotCronPayload)
    state: SparkBotCronJobState = field(default_factory=SparkBotCronJobState)
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False


@dataclass(slots=True)
class SparkBotCronStore:
    version: int = 1
    jobs: list[SparkBotCronJob] = field(default_factory=list)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_cron_next_run(
    schedule: SparkBotCronSchedule,
    now_ms: int,
) -> int | None:
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None
    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        return now_ms + schedule.every_ms
    if schedule.kind == "cron" and schedule.expr:
        try:
            from zoneinfo import ZoneInfo

            from croniter import croniter

            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(now_ms / 1000, tz=tz)
            next_dt = croniter(schedule.expr, base_dt).get_next(datetime)
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None
    return None


def _validate_cron_schedule(schedule: SparkBotCronSchedule) -> None:
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")
    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(schedule.tz)
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None


class SparkBotCronService:
    """Persistent scheduler for SparkBot reminders and background turns."""

    def __init__(
        self,
        *,
        store_path: Path,
        on_job: Callable[[SparkBotCronJob], Awaitable[str | None]] | None = None,
    ) -> None:
        self.store_path = store_path
        self.on_job = on_job
        self._store: SparkBotCronStore | None = None
        self._last_mtime = 0.0
        self._timer_task: asyncio.Task | None = None
        self._running = False

    @property
    def task(self) -> asyncio.Task | None:
        return self._timer_task

    async def start(self) -> None:
        self._running = True
        self._load_store()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()

    def stop(self) -> None:
        self._running = False
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = None

    def list_jobs(self, *, include_disabled: bool = False) -> list[SparkBotCronJob]:
        store = self._load_store()
        jobs = store.jobs if include_disabled else [job for job in store.jobs if job.enabled]
        return sorted(jobs, key=lambda job: job.state.next_run_at_ms or float("inf"))

    def add_job(
        self,
        *,
        name: str,
        schedule: SparkBotCronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
    ) -> SparkBotCronJob:
        _validate_cron_schedule(schedule)
        store = self._load_store()
        now = _now_ms()
        job = SparkBotCronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=SparkBotCronPayload(
                kind="agent_turn",
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
            ),
            state=SparkBotCronJobState(next_run_at_ms=_compute_cron_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )
        store.jobs.append(job)
        self._save_store()
        self._arm_timer()
        return job

    def remove_job(self, job_id: str) -> bool:
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [job for job in store.jobs if job.id != job_id]
        removed = len(store.jobs) != before
        if removed:
            self._save_store()
            self._arm_timer()
        return removed

    def enable_job(self, job_id: str, enabled: bool = True) -> SparkBotCronJob | None:
        store = self._load_store()
        for job in store.jobs:
            if job.id != job_id:
                continue
            job.enabled = enabled
            job.updated_at_ms = _now_ms()
            job.state.next_run_at_ms = (
                _compute_cron_next_run(job.schedule, _now_ms()) if enabled else None
            )
            self._save_store()
            self._arm_timer()
            return job
        return None

    async def run_job(self, job_id: str, *, force: bool = False) -> bool:
        store = self._load_store()
        for job in list(store.jobs):
            if job.id != job_id:
                continue
            if not force and not job.enabled:
                return False
            await self._execute_job(job)
            self._save_store()
            self._arm_timer()
            return True
        return False

    def status(self) -> dict[str, Any]:
        store = self._load_store()
        return {
            "enabled": self._running,
            "jobs": len(store.jobs),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }

    def _load_store(self) -> SparkBotCronStore:
        if self._store and self.store_path.exists():
            mtime = self.store_path.stat().st_mtime
            if mtime != self._last_mtime:
                self._store = None
        if self._store is not None:
            return self._store
        if not self.store_path.exists():
            self._store = SparkBotCronStore()
            return self._store
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._store = SparkBotCronStore(
                version=int(data.get("version", 1)),
                jobs=[self._job_from_json(item) for item in data.get("jobs", [])],
            )
            self._last_mtime = self.store_path.stat().st_mtime
        except Exception:
            logger.exception("Failed to load SparkBot cron store: %s", self.store_path)
            self._store = SparkBotCronStore()
        return self._store

    def _save_store(self) -> None:
        if self._store is None:
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self._store.version,
            "jobs": [self._job_to_json(job) for job in self._store.jobs],
        }
        self.store_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._last_mtime = self.store_path.stat().st_mtime

    def _recompute_next_runs(self) -> None:
        if self._store is None:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_cron_next_run(job.schedule, now)

    def _get_next_wake_ms(self) -> int | None:
        if self._store is None:
            return None
        times = [
            job.state.next_run_at_ms
            for job in self._store.jobs
            if job.enabled and job.state.next_run_at_ms
        ]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = None
        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return

        async def tick() -> None:
            await asyncio.sleep(max(0, next_wake - _now_ms()) / 1000)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick(), name="SparkBot:cron")

    async def _on_timer(self) -> None:
        store = self._load_store()
        now = _now_ms()
        due = [
            job
            for job in list(store.jobs)
            if job.enabled and job.state.next_run_at_ms and now >= job.state.next_run_at_ms
        ]
        for job in due:
            await self._execute_job(job)
        self._save_store()
        self._arm_timer()

    async def _execute_job(self, job: SparkBotCronJob) -> None:
        start_ms = _now_ms()
        try:
            if self.on_job is not None:
                await self.on_job(job)
            job.state.last_status = "ok"
            job.state.last_error = None
        except Exception as exc:
            job.state.last_status = "error"
            job.state.last_error = str(exc)
        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = _now_ms()
        if job.schedule.kind == "at":
            if job.delete_after_run and self._store is not None:
                self._store.jobs = [item for item in self._store.jobs if item.id != job.id]
            else:
                job.enabled = False
                job.state.next_run_at_ms = None
        else:
            job.state.next_run_at_ms = _compute_cron_next_run(job.schedule, _now_ms())

    @staticmethod
    def _job_from_json(data: dict[str, Any]) -> SparkBotCronJob:
        schedule = data.get("schedule", {})
        payload = data.get("payload", {})
        state = data.get("state", {})
        return SparkBotCronJob(
            id=str(data["id"]),
            name=str(data["name"]),
            enabled=bool(data.get("enabled", True)),
            schedule=SparkBotCronSchedule(
                kind=schedule.get("kind", "every"),
                at_ms=schedule.get("atMs"),
                every_ms=schedule.get("everyMs"),
                expr=schedule.get("expr"),
                tz=schedule.get("tz"),
            ),
            payload=SparkBotCronPayload(
                kind=payload.get("kind", "agent_turn"),
                message=payload.get("message", ""),
                deliver=bool(payload.get("deliver", False)),
                channel=payload.get("channel"),
                to=payload.get("to"),
            ),
            state=SparkBotCronJobState(
                next_run_at_ms=state.get("nextRunAtMs"),
                last_run_at_ms=state.get("lastRunAtMs"),
                last_status=state.get("lastStatus"),
                last_error=state.get("lastError"),
            ),
            created_at_ms=int(data.get("createdAtMs", 0)),
            updated_at_ms=int(data.get("updatedAtMs", 0)),
            delete_after_run=bool(data.get("deleteAfterRun", False)),
        )

    @staticmethod
    def _job_to_json(job: SparkBotCronJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "schedule": {
                "kind": job.schedule.kind,
                "atMs": job.schedule.at_ms,
                "everyMs": job.schedule.every_ms,
                "expr": job.schedule.expr,
                "tz": job.schedule.tz,
            },
            "payload": {
                "kind": job.payload.kind,
                "message": job.payload.message,
                "deliver": job.payload.deliver,
                "channel": job.payload.channel,
                "to": job.payload.to,
            },
            "state": {
                "nextRunAtMs": job.state.next_run_at_ms,
                "lastRunAtMs": job.state.last_run_at_ms,
                "lastStatus": job.state.last_status,
                "lastError": job.state.last_error,
            },
            "createdAtMs": job.created_at_ms,
            "updatedAtMs": job.updated_at_ms,
            "deleteAfterRun": job.delete_after_run,
        }


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

    def _config_path(self, bot_id: str) -> Path:
        return self._bot_dir(bot_id) / "config.yaml"

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
            for legacy_yaml in (legacy_root / "bots" / f"{safe}.yaml", legacy_root / f"{safe}.yaml"):
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

    @staticmethod
    def _apply_agent_tool_runtime_defaults(config: BotConfig) -> None:
        exec_config = config.tools.exec_config
        if exec_config.timeout == 60:
            exec_config.timeout = 300
        if not exec_config.path_append:
            exec_config.path_append = str(Path(sys.executable).parent)

    async def start_bot(self, bot_id: str, config: BotConfig | None = None) -> SparkBotInstance:
        existing = self._bots.get(bot_id)
        if existing is not None:
            return existing

        cfg = config or self.load_bot_config(bot_id) or BotConfig(name=bot_id)
        self._apply_agent_tool_runtime_defaults(cfg)
        self.save_bot_config(bot_id, cfg, auto_start=True)
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

        instance.tasks.append(
            asyncio.create_task(agent_loop.run(), name=f"SparkBot:{bot_id}:loop")
        )
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
        """Start bots whose saved config opts into autostart."""
        started: list[SparkBotInstance] = []
        for bot_id in sorted(self._discover_bot_ids()):
            cfg = self.load_bot_config(bot_id)
            if cfg and cfg.auto_start:
                started.append(await self.start_bot(bot_id, cfg))
        return started

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
            "metadata": metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {},
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
            prompt = f"Persona:\n{instance.config.persona or instance.config.name}\n\nUser:\n{content}"
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
        if any(souls_dir.glob("*.json")):
            return
        for soul in _DEFAULT_SOULS:
            (souls_dir / f"{soul['id']}.json").write_text(
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
    "TelegramChannel",
    "TelegramConfig",
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
    "_is_secret_field",
    "discover_builtin_channels",
    "get_sparkbot_manager",
    "mask_channel_secrets",
]

