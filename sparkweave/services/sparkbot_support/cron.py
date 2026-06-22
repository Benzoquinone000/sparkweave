"""Persistent cron scheduling support for SparkBot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Literal
import uuid

logger = logging.getLogger(__name__)


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


__all__ = [
    "SparkBotCronJob",
    "SparkBotCronJobState",
    "SparkBotCronPayload",
    "SparkBotCronSchedule",
    "SparkBotCronService",
    "SparkBotCronStore",
]
