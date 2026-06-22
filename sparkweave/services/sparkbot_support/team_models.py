"""Nano-team state models for SparkBot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

TEAM_FINISHED_STATUSES = {"completed", "stopped"}


def team_timestamp() -> str:
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
                    "arguments": data.get("arguments")
                    or data.get("tool_args")
                    or data.get("toolArgs")
                    or {},
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
            tool_calls=[dict(item) for item in tool_calls if isinstance(item, dict)],
            tool_results=[dict(item) for item in tool_results if isinstance(item, dict)],
            artifacts=[dict(item) for item in artifacts if isinstance(item, dict)],
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
    created_at: str = field(default_factory=team_timestamp)
    updated_at: str = field(default_factory=team_timestamp)
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
            created_at=str(data.get("created_at") or data.get("createdAt") or team_timestamp()),
            updated_at=str(data.get("updated_at") or data.get("updatedAt") or team_timestamp()),
            session_key=str(data.get("session_key") or data.get("sessionKey") or "web:web"),
        )


@dataclass(slots=True)
class SparkBotTeamMail:
    id: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: str = field(default_factory=team_timestamp)
    read_by: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SparkBotTeamMail":
        return cls(
            id=str(data.get("id") or ""),
            from_agent=str(data.get("from_agent") or data.get("fromAgent") or ""),
            to_agent=str(data.get("to_agent") or data.get("toAgent") or ""),
            content=str(data.get("content") or ""),
            timestamp=str(data.get("timestamp") or team_timestamp()),
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


__all__ = [
    "TEAM_FINISHED_STATUSES",
    "SparkBotTeamMail",
    "SparkBotTeamMember",
    "SparkBotTeamRuntime",
    "SparkBotTeamState",
    "SparkBotTeamTask",
    "team_timestamp",
]
