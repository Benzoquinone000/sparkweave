"""NG-owned guided-learning service with the legacy GuideManager surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import html
import json
from pathlib import Path
import re
import time
from typing import Any
import uuid

from sparkweave.logging import get_logger
from sparkweave.services.config import PROJECT_ROOT, load_config_with_main
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.paths import get_path_service


class BaseAgent:
    """Tiny stats compatibility shim for legacy guide routes."""

    @staticmethod
    def reset_stats(_module: str | None = None) -> None:
        return None

    @staticmethod
    def print_stats(_module: str | None = None) -> None:
        return None


@dataclass
class GuidedSession:
    session_id: str
    notebook_id: str
    notebook_name: str
    created_at: float
    knowledge_points: list[dict[str, Any]] = field(default_factory=list)
    current_index: int = -1
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    status: str = "initialized"
    html_pages: dict[str, str] = field(default_factory=dict)
    page_statuses: dict[str, str] = field(default_factory=dict)
    page_errors: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    notebook_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GuidedSession:
        payload = dict(data)
        payload.setdefault("knowledge_points", [])
        payload.setdefault("current_index", -1)
        payload.setdefault("chat_history", [])
        payload.setdefault("status", "initialized")
        payload.setdefault("html_pages", {})
        payload.setdefault("page_statuses", {})
        payload.setdefault("page_errors", {})
        payload.setdefault("summary", "")
        payload.setdefault("notebook_context", "")
        return cls(**payload)


class GuideManager:
    """Manage guided-learning sessions without legacy agent dependencies."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        language: str | None = None,
        output_dir: str | None = None,
        config_path: str | None = None,
        binding: str = "openai",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.binding = binding
        self.language = language or "en"

        config = load_config_with_main("main.yaml", PROJECT_ROOT)
        log_dir = config.get("paths", {}).get("user_log_dir") or config.get(
            "logging", {}
        ).get("log_dir")
        self.logger = get_logger("Guide", log_dir=log_dir)

        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = get_path_service().get_guide_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, GuidedSession] = {}

    async def create_session(
        self,
        user_input: str,
        display_title: str | None = None,
        notebook_context: str = "",
    ) -> dict[str, Any]:
        if not user_input.strip():
            return {"success": False, "error": "User input cannot be empty", "session_id": None}

        knowledge_points = await self._design_knowledge_points(user_input, notebook_context)
        if not knowledge_points:
            return {"success": False, "error": "No knowledge points identified", "session_id": None}

        session_id = uuid.uuid4().hex[:8]
        title = (display_title or user_input).strip().replace("\n", " ")[:50]
        session = GuidedSession(
            session_id=session_id,
            notebook_id="user_input",
            notebook_name=title or "Guided Learning",
            created_at=time.time(),
            knowledge_points=knowledge_points,
            notebook_context=notebook_context,
        )
        self._initialize_page_statuses(session)
        self._save_session(session)
        return {
            "success": True,
            "session_id": session_id,
            "knowledge_points": knowledge_points,
            "total_points": len(knowledge_points),
            "message": f"Learning plan created with {len(knowledge_points)} knowledge points",
        }

    async def start_learning(self, session_id: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        session.current_index = 0
        session.status = "learning"
        self._initialize_page_statuses(session)
        await self._ensure_page(session, 0)
        session.chat_history.append(
            {
                "role": "system",
                "content": "Started guided learning.",
                "knowledge_index": 0,
                "timestamp": time.time(),
            }
        )
        self._save_session(session)
        return {
            "success": True,
            "current_index": 0,
            "current_knowledge": session.knowledge_points[0] if session.knowledge_points else None,
            "html": session.html_pages.get("0", ""),
            "page_statuses": session.page_statuses,
            "progress": self._calculate_progress(session),
            "total_points": len(session.knowledge_points),
            "message": "Guided learning started.",
        }

    async def navigate_to_knowledge(self, session_id: str, knowledge_index: int) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        if knowledge_index < 0 or knowledge_index >= len(session.knowledge_points):
            return {"success": False, "error": "Knowledge point does not exist"}
        session.current_index = knowledge_index
        session.status = "learning"
        await self._ensure_page(session, knowledge_index)
        self._save_session(session)
        key = str(knowledge_index)
        return {
            "success": True,
            "current_index": knowledge_index,
            "current_knowledge": session.knowledge_points[knowledge_index],
            "html": session.html_pages.get(key, ""),
            "page_status": session.page_statuses.get(key, "pending"),
            "page_error": session.page_errors.get(key, ""),
            "progress": self._calculate_progress(session),
            "total_points": len(session.knowledge_points),
        }

    async def complete_learning(self, session_id: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        session.status = "completed"
        session.current_index = len(session.knowledge_points)
        session.summary = self._build_summary(session)
        self._save_session(session)
        return {
            "success": True,
            "summary": session.summary,
            "status": session.status,
            "progress_percentage": 100,
        }

    async def chat(
        self,
        session_id: str,
        message: str,
        knowledge_index: int | None = None,
    ) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        index = knowledge_index if knowledge_index is not None else max(session.current_index, 0)
        knowledge = (
            session.knowledge_points[index]
            if 0 <= index < len(session.knowledge_points)
            else {}
        )
        answer = await self._chat_answer(message, knowledge, session.notebook_context)
        entry = {
            "role": "user",
            "content": message,
            "knowledge_index": index,
            "timestamp": time.time(),
        }
        session.chat_history.append(entry)
        session.chat_history.append(
            {
                "role": "assistant",
                "content": answer,
                "knowledge_index": index,
                "timestamp": time.time(),
            }
        )
        self._save_session(session)
        return {"success": True, "response": answer, "chat_history": session.chat_history}

    async def fix_html(self, session_id: str, bug_description: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        index = max(session.current_index, 0)
        if index >= len(session.knowledge_points):
            return {"success": False, "error": "No current knowledge point"}
        key = str(index)
        base_html = session.html_pages.get(key) or self._render_page(session.knowledge_points[index])
        fixed = base_html.replace(
            "</main>",
            f"<p><strong>Revision note:</strong> {html.escape(bug_description)}</p></main>",
        )
        session.html_pages[key] = fixed
        session.page_statuses[key] = "ready"
        session.page_errors[key] = ""
        self._save_session(session)
        return {"success": True, "html": fixed, "message": "HTML updated."}

    async def retry_page(self, session_id: str, page_index: int) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        if page_index < 0 or page_index >= len(session.knowledge_points):
            return {"success": False, "error": "Knowledge point does not exist"}
        key = str(page_index)
        session.html_pages.pop(key, None)
        session.page_statuses[key] = "pending"
        await self._ensure_page(session, page_index)
        self._save_session(session)
        return {
            "success": True,
            "page_index": page_index,
            "html": session.html_pages.get(key, ""),
            "page_status": session.page_statuses.get(key, "pending"),
        }

    async def reset_session(self, session_id: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        if not session:
            return {"success": False, "error": "Session does not exist"}
        session.current_index = -1
        session.status = "initialized"
        session.chat_history = []
        self._save_session(session)
        return {"success": True, "session_id": session_id, "status": session.status}

    def delete_session(self, session_id: str) -> dict[str, Any]:
        self._sessions.pop(session_id, None)
        path = self._get_session_file(session_id)
        if path.exists():
            path.unlink()
            return {"success": True, "session_id": session_id}
        return {"success": False, "error": "Session does not exist"}

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions = []
        for path in self.output_dir.glob("session_*.json"):
            try:
                session = GuidedSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            sessions.append(
                {
                    "session_id": session.session_id,
                    "notebook_name": session.notebook_name,
                    "created_at": session.created_at,
                    "status": session.status,
                    "knowledge_count": len(session.knowledge_points),
                    "current_index": session.current_index,
                    "progress": self._calculate_progress(session),
                }
            )
        sessions.sort(key=lambda item: float(item.get("created_at", 0)), reverse=True)
        return sessions

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._load_session(session_id)
        return session.to_dict() if session else None

    def get_current_html(self, session_id: str) -> str | None:
        session = self._load_session(session_id)
        if not session:
            return None
        index = min(max(session.current_index, 0), max(len(session.knowledge_points) - 1, 0))
        key = str(index)
        return session.html_pages.get(key) or next(iter(session.html_pages.values()), None)

    def get_session_pages(self, session_id: str) -> dict[str, Any] | None:
        session = self._load_session(session_id)
        if not session:
            return None
        return {
            "session_id": session_id,
            "current_index": session.current_index,
            "page_statuses": session.page_statuses,
            "page_errors": session.page_errors,
            "html_pages": session.html_pages,
            "progress": self._calculate_progress(session),
        }

    def _get_session_file(self, session_id: str) -> Path:
        return self.output_dir / f"session_{session_id}.json"

    def _save_session(self, session: GuidedSession) -> None:
        self._sessions[session.session_id] = session
        self._get_session_file(session.session_id).write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_session(self, session_id: str) -> GuidedSession | None:
        if session_id in self._sessions:
            return self._sessions[session_id]
        path = self._get_session_file(session_id)
        if not path.exists():
            return None
        try:
            session = GuidedSession.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None
        self._sessions[session_id] = session
        return session

    def _initialize_page_statuses(self, session: GuidedSession) -> None:
        for index, _knowledge in enumerate(session.knowledge_points):
            session.page_statuses.setdefault(str(index), "pending")
            session.page_errors.setdefault(str(index), "")

    async def _ensure_page(self, session: GuidedSession, index: int) -> None:
        key = str(index)
        if session.html_pages.get(key):
            session.page_statuses[key] = "ready"
            return
        try:
            session.page_statuses[key] = "generating"
            session.html_pages[key] = self._render_page(session.knowledge_points[index])
            session.page_statuses[key] = "ready"
            session.page_errors[key] = ""
        except Exception as exc:
            session.page_statuses[key] = "failed"
            session.page_errors[key] = str(exc)

    async def _design_knowledge_points(
        self,
        user_input: str,
        notebook_context: str,
    ) -> list[dict[str, Any]]:
        prompt = (
            "Create a short guided-learning plan as JSON with key knowledge_points. "
            "Each item needs knowledge_title, learning_objective, and key_points.\n\n"
            f"Learner request:\n{user_input}\n\nNotebook context:\n{notebook_context or '(none)'}"
        )
        try:
            raw = await llm_complete(
                prompt=prompt,
                system_prompt="Return JSON only.",
                api_key=self.api_key,
                base_url=self.base_url,
                api_version=self.api_version,
                binding=self.binding,
                temperature=0.3,
            )
            parsed = self._parse_json_object(raw)
            points = parsed.get("knowledge_points", []) if isinstance(parsed, dict) else []
            normalized = [self._normalize_knowledge_point(item) for item in points[:8]]
            return [item for item in normalized if item]
        except Exception as exc:
            self.logger.debug("Falling back to deterministic guide plan: %s", exc)
            return self._fallback_knowledge_points(user_input)

    async def _chat_answer(
        self,
        message: str,
        knowledge: dict[str, Any],
        notebook_context: str,
    ) -> str:
        title = str(knowledge.get("knowledge_title") or "current topic")
        try:
            return await llm_complete(
                prompt=(
                    f"Current topic: {title}\n"
                    f"Key points: {knowledge.get('key_points', [])}\n"
                    f"Notebook context: {notebook_context or '(none)'}\n"
                    f"Learner question: {message}"
                ),
                system_prompt="You are a concise guided-learning tutor.",
                api_key=self.api_key,
                base_url=self.base_url,
                api_version=self.api_version,
                binding=self.binding,
                temperature=0.5,
            )
        except Exception:
            return f"Let's connect your question to {title}: {message}"

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        candidate = match.group(1) if match else raw
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _normalize_knowledge_point(item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        title = str(item.get("knowledge_title") or item.get("title") or "").strip()
        if not title:
            return {}
        key_points = item.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = [str(key_points)]
        return {
            "knowledge_title": title,
            "learning_objective": str(item.get("learning_objective") or "").strip(),
            "key_points": [str(point).strip() for point in key_points if str(point).strip()],
        }

    @staticmethod
    def _fallback_knowledge_points(user_input: str) -> list[dict[str, Any]]:
        topic = user_input.strip()[:120] or "Guided topic"
        return [
            {
                "knowledge_title": f"{topic} - foundations",
                "learning_objective": "Build the core mental model.",
                "key_points": ["Definitions", "Key intuition", "Common pitfalls"],
            },
            {
                "knowledge_title": f"{topic} - worked practice",
                "learning_objective": "Apply the idea to representative examples.",
                "key_points": ["Step-by-step reasoning", "Checks", "Variations"],
            },
            {
                "knowledge_title": f"{topic} - consolidation",
                "learning_objective": "Summarize and transfer the skill.",
                "key_points": ["Summary", "Self-test", "Next steps"],
            },
        ]

    @staticmethod
    def _render_page(knowledge: dict[str, Any]) -> str:
        title = html.escape(str(knowledge.get("knowledge_title") or "Learning point"))
        objective = html.escape(str(knowledge.get("learning_objective") or ""))
        points = knowledge.get("key_points", [])
        if not isinstance(points, list):
            points = [points]
        items = "\n".join(f"<li>{html.escape(str(point))}</li>" for point in points)
        return (
            "<main class=\"guide-page\">"
            f"<h1>{title}</h1>"
            f"<p>{objective}</p>"
            f"<ul>{items}</ul>"
            "<section><h2>Try It</h2><p>Explain this point in your own words, then ask for feedback.</p></section>"
            "</main>"
        )

    @staticmethod
    def _build_summary(session: GuidedSession) -> str:
        titles = [
            str(item.get("knowledge_title") or "")
            for item in session.knowledge_points
            if item.get("knowledge_title")
        ]
        if not titles:
            return "Guided learning completed."
        return "Completed guided learning on: " + "; ".join(titles)

    @staticmethod
    def _calculate_progress(session: GuidedSession) -> int:
        total = len(session.knowledge_points)
        if not total:
            return 0
        ready = sum(1 for status in session.page_statuses.values() if status == "ready")
        return int((ready / total) * 100)


__all__ = ["BaseAgent", "GuideManager", "GuidedSession"]

