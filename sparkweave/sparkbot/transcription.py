"""Audio transcription helpers for NG SparkBot channels."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GroqTranscriptionProvider:
    """Transcribe audio files through Groq's OpenAI-compatible Whisper endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = "whisper-large-v3",
        api_url: str = "https://api.groq.com/openai/v1/audio/transcriptions",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model
        self.api_url = api_url
        self.timeout = timeout

    async def transcribe(self, file_path: str | Path) -> str:
        """Return the transcription text, or an empty string when unavailable."""
        if not self.api_key:
            logger.debug("Groq API key not configured for audio transcription")
            return ""

        path = Path(file_path)
        if not path.exists() or not path.is_file():
            logger.warning("Audio file not found for transcription: %s", file_path)
            return ""

        try:
            data = await self._post(path)
        except Exception:
            logger.exception("Groq audio transcription failed")
            return ""
        text = data.get("text", "")
        return str(text or "").strip()

    async def _post(self, path: Path) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            with path.open("rb") as handle:
                response = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={
                        "file": (path.name, handle),
                        "model": (None, self.model),
                    },
                    timeout=self.timeout,
                )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}


async def transcribe_audio(file_path: str | Path, api_key: str | None = None) -> str:
    """Convenience wrapper matching the old SparkBot transcription behavior."""
    return await GroqTranscriptionProvider(api_key=api_key).transcribe(file_path)


__all__ = ["GroqTranscriptionProvider", "transcribe_audio"]
