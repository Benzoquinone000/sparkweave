"""HEARTBEAT.md polling and notification gating for SparkBot."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from pathlib import Path
from typing import Any

from sparkweave.services.llm import complete as llm_complete
from sparkweave.utils.json_parser import extract_json_from_text

logger = logging.getLogger(__name__)


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


__all__ = ["SparkBotHeartbeatService"]
