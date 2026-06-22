"""Safe static-file exposure for user-generated output artifacts."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from sparkweave.services.paths import get_path_service

ACTIVE_OUTPUT_SUFFIXES = {".html", ".htm", ".svg", ".xml", ".xhtml", ".js", ".mjs"}


def _safe_header_filename(value: str, *, fallback: str = "download") -> str:
    filename = Path(value).name
    filename = "".join(
        ch if ch.isprintable() and ch not in {'"', "\\", "\r", "\n"} else "_" for ch in filename
    )
    filename = filename.strip(" .\t")[:180]
    return filename or fallback


class SafeOutputStaticFiles(StaticFiles):
    """Static file mount that only exposes explicitly whitelisted artifacts."""

    def __init__(self, *args, path_service, **kwargs):
        super().__init__(*args, **kwargs)
        self._path_service = path_service

    async def get_response(self, path: str, scope):
        if not self._path_service.is_public_output_path(path):
            raise HTTPException(status_code=404, detail="Output not found")
        response = await super().get_response(path, scope)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if Path(path).suffix.lower() in ACTIVE_OUTPUT_SUFFIXES:
            filename = _safe_header_filename(path)
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            response.headers.setdefault(
                "Content-Security-Policy",
                "sandbox; default-src 'none'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'unsafe-inline'",
            )
        return response


def mount_public_outputs(app: FastAPI):
    """Mount the filtered public output directory and return the path service."""
    path_service = get_path_service()
    user_dir = path_service.get_public_outputs_root()

    try:
        path_service.ensure_all_directories()
    except Exception:
        if not user_dir.exists():
            user_dir.mkdir(parents=True)

    app.mount(
        "/api/outputs",
        SafeOutputStaticFiles(directory=str(user_dir), path_service=path_service),
        name="outputs",
    )
    return path_service


__all__ = [
    "ACTIVE_OUTPUT_SUFFIXES",
    "SafeOutputStaticFiles",
    "_safe_header_filename",
    "mount_public_outputs",
]
