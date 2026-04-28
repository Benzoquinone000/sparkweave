"""Task ID manager for API background jobs."""

from __future__ import annotations

from datetime import datetime, timedelta
import threading
import uuid


class TaskIDManager:
    """Singleton class for managing task IDs."""

    _instance: "TaskIDManager | None" = None
    _lock = threading.Lock()
    _task_ids: dict[str, str] = {}
    _task_metadata: dict[str, dict] = {}

    @classmethod
    def get_instance(cls) -> "TaskIDManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def generate_task_id(self, task_type: str, task_key: str) -> str:
        with self._lock:
            if task_key in self._task_ids:
                return self._task_ids[task_key]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            task_id = f"{task_type}_{timestamp}_{unique_id}"

            self._task_ids[task_key] = task_id
            self._task_metadata[task_id] = {
                "task_type": task_type,
                "task_key": task_key,
                "created_at": datetime.now().isoformat(),
                "status": "running",
            }
            return task_id

    def get_task_id(self, task_key: str) -> str | None:
        with self._lock:
            return self._task_ids.get(task_key)

    def update_task_status(self, task_id: str, status: str, **kwargs) -> None:
        with self._lock:
            if task_id in self._task_metadata:
                self._task_metadata[task_id]["status"] = status
                self._task_metadata[task_id].update(kwargs)
                if status in ["completed", "error", "cancelled"]:
                    self._task_metadata[task_id]["finished_at"] = datetime.now().isoformat()

    def get_task_metadata(self, task_id: str) -> dict | None:
        with self._lock:
            return self._task_metadata.get(task_id, {}).copy()

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            to_remove: list[str] = []
            for task_id, metadata in self._task_metadata.items():
                if metadata.get("status") not in ["completed", "error", "cancelled"]:
                    continue
                finished_at = metadata.get("finished_at")
                if not finished_at:
                    continue
                try:
                    finished_time = datetime.fromisoformat(finished_at)
                except ValueError:
                    continue
                if finished_time < cutoff:
                    to_remove.append(task_id)

            for task_id in to_remove:
                metadata = self._task_metadata.pop(task_id, {})
                task_key = metadata.get("task_key")
                if task_key:
                    self._task_ids.pop(task_key, None)


__all__ = ["TaskIDManager"]

