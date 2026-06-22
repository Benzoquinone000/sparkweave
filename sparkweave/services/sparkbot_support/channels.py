"""Built-in SparkBot channel adapters."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
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
import re
import smtplib
import ssl
import threading
import time
from typing import Any, Awaitable, Callable
from urllib.parse import unquote, urlparse
import uuid

from pydantic import BaseModel

from sparkweave.services.paths import get_path_service
from sparkweave.services.sparkbot_support.config_models import (
    DingTalkConfig,
    DiscordConfig,
    EmailConfig,
    FeishuConfig,
    MatrixConfig,
    MochatConfig,
    QQConfig,
    SlackConfig,
    TelegramConfig,
    WecomConfig,
    WhatsAppConfig,
)
from sparkweave.services.sparkbot_support.formatting import (
    markdown_to_telegram_html as _markdown_to_telegram_html,
)
from sparkweave.services.sparkbot_support.formatting import split_message as _split_message
from sparkweave.services.sparkbot_support.messages import (
    SparkBotInboundMessage,
    SparkBotMessageBus,
    SparkBotOutboundMessage,
)
from sparkweave.services.sparkbot_support.mochat import (
    MOCHAT_CURSOR_SAVE_DEBOUNCE_S,
    MOCHAT_MAX_SEEN_MESSAGE_IDS,
    MochatBufferedEntry,
    MochatDelayState,
)
from sparkweave.services.sparkbot_support.mochat import (
    build_mochat_buffered_body as _build_mochat_buffered_body,
)
from sparkweave.services.sparkbot_support.mochat import (
    make_mochat_synthetic_event as _make_mochat_synthetic_event,
)
from sparkweave.services.sparkbot_support.mochat import mochat_safe_dict as _mochat_safe_dict
from sparkweave.services.sparkbot_support.mochat import mochat_str_field as _mochat_str_field
from sparkweave.services.sparkbot_support.mochat import (
    normalize_mochat_content as _normalize_mochat_content,
)
from sparkweave.services.sparkbot_support.mochat import (
    parse_mochat_timestamp as _parse_mochat_timestamp,
)
from sparkweave.services.sparkbot_support.mochat import (
    resolve_mochat_require_mention as _resolve_mochat_require_mention,
)
from sparkweave.services.sparkbot_support.mochat import (
    resolve_mochat_target as _resolve_mochat_target,
)
from sparkweave.services.sparkbot_support.mochat import (
    resolve_mochat_was_mentioned as _resolve_mochat_was_mentioned,
)

logger = logging.getLogger(__name__)

CHANNEL_CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "DingTalkConfig": DingTalkConfig,
    "DiscordConfig": DiscordConfig,
    "EmailConfig": EmailConfig,
    "FeishuConfig": FeishuConfig,
    "MatrixConfig": MatrixConfig,
    "MochatConfig": MochatConfig,
    "QQConfig": QQConfig,
    "SlackConfig": SlackConfig,
    "TelegramConfig": TelegramConfig,
    "WecomConfig": WecomConfig,
    "WhatsAppConfig": WhatsAppConfig,
}

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
DISCORD_MAX_MESSAGE_LEN = 2000
TELEGRAM_MAX_MESSAGE_LEN = 4000
TELEGRAM_REPLY_CONTEXT_MAX_LEN = TELEGRAM_MAX_MESSAGE_LEN


def _channel_config_model(channel_cls: type) -> type[BaseModel] | None:
    expected = channel_cls.__name__.replace("Channel", "") + "Config"
    return CHANNEL_CONFIG_MODELS.get(expected)


def _sparkbot_media_dir(channel: str) -> Path:
    path = get_path_service().project_root / "data" / "sparkbot" / "media" / channel
    path.mkdir(parents=True, exist_ok=True)
    return path


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
            logger.warning("Telegram channel requires python-telegram-bot; using in-memory channel")
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
        builder = (
            Application.builder()
            .token(self.config.token)
            .request(request)
            .get_updates_request(request)
        )
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
        thread_kwargs = (
            {"message_thread_id": message_thread_id} if message_thread_id is not None else {}
        )
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
                else media_type
                if media_type in {"voice", "audio"}
                else "document"
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
            if (
                offset is not None
                and length is not None
                and text[offset : offset + length].lower() == handle
            ):
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
            parts = [
                f"**{headers[index]}**: {cells[index]}"
                for index in range(len(headers))
                if cells[index]
            ]
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
                        data={"payload_json": json.dumps(payload_json)} if payload_json else {},
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
            logger.warning(
                "DingTalk channel requires dingtalk-stream and httpx; using in-memory channel"
            )
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
            self.config.from_address or self.config.smtp_username or self.config.imap_username
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
                media_type = (
                    "media" if ext in self._AUDIO_EXTS or ext in self._VIDEO_EXTS else "file"
                )
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
                path, label = await self._download_and_save_media(
                    msg_type, content_json, message_id
                )
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
                        CreateImageRequestBody.builder().image_type("message").image(handle).build()
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

    def _download_image_sync(
        self, message_id: str, image_key: str
    ) -> tuple[bytes | None, str | None]:
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

        root: Any = (
            content_json.get("post") if isinstance(content_json.get("post"), dict) else content_json
        )
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
            for field in (
                element.get("fields", []) if isinstance(element.get("fields"), list) else []
            ):
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
                        for nested in (
                            value.get("elements", [])
                            if isinstance(value.get("elements"), list)
                            else []
                        ):
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
        self.client.add_event_callback(
            self._on_media_message, (RoomMessageMedia, RoomEncryptedMedia)
        )
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
                text = (
                    f"{text.rstrip()}\n{chr(10).join(failures)}"
                    if text.strip()
                    else "\n".join(failures)
                )
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
            logger.warning(
                "Matrix media decrypt failed for event %s", getattr(event, "event_id", "")
            )
            return None

    async def _fetch_media_attachment(
        self, room: Any, event: Any
    ) -> tuple[dict[str, Any] | None, str]:
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
        is_panel = (target.is_panel or target.id in self._panel_set) and not target.id.startswith(
            "session_"
        )
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
            previous_cursor = (
                self._session_cursor.get(target_id, 0) if target_kind == "session" else 0
            )
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
                await self._flush_delayed_entries(
                    seen_key, target_id, target_kind, "mention", entry
                )
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
                getattr(author, "id", None) or getattr(author, "user_openid", None) or "unknown"
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
            self.config.bot_id,
            self.config.secret,
            reconnect_interval=1000,
            max_reconnect_attempts=-1,
            heartbeat_interval=30000,
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
        await self._client.connect()
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

    async def _on_connected(self, _frame: Any = None) -> None:
        return None

    async def _on_authenticated(self, _frame: Any = None) -> None:
        return None

    async def _on_disconnected(self, _frame: Any = None) -> None:
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
        message_id = str(
            body.get("msgid") or f"{body.get('chatid', '')}_{body.get('sendertime', '')}"
        )
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
            text = (
                (body.get("text") or {}).get("content")
                if isinstance(body.get("text"), dict)
                else ""
            )
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
                    content_parts.append(
                        self._MSG_TYPE_LABELS.get(str(item_type), f"[{item_type}]")
                    )
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
            result = await self._client.download_file(file_url, aes_key)
        except Exception:
            logger.exception("WeCom media download failed")
            return None
        if isinstance(result, tuple):
            data, remote_name = result
        elif isinstance(result, dict):
            data = result.get("buffer") or result.get("data") or b""
            remote_name = result.get("filename") or result.get("name")
        else:
            data = b""
            remote_name = None
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

__all__ = [
    "DISCORD_API_BASE",
    "DISCORD_MAX_ATTACHMENT_BYTES",
    "DISCORD_MAX_MESSAGE_LEN",
    "TELEGRAM_MAX_MESSAGE_LEN",
    "TELEGRAM_REPLY_CONTEXT_MAX_LEN",
    "DingTalkChannel",
    "DiscordChannel",
    "EmailChannel",
    "FeishuChannel",
    "MatrixChannel",
    "MochatChannel",
    "QQChannel",
    "SlackChannel",
    "SparkBotChannel",
    "TelegramChannel",
    "WecomChannel",
    "WhatsAppChannel",
    "_channel_config_model",
    "_sparkbot_media_dir",
    "discover_builtin_channels",
]
