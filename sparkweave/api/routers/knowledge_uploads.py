"""Upload staging helpers for knowledge-base API routes."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from fastapi import HTTPException, UploadFile

from sparkweave.utils.document_validator import DocumentValidator
from sparkweave.utils.error_utils import format_exception_message

logger = logging.getLogger("Knowledge")

BYTES_PER_GB = 1024**3
BYTES_PER_MB = 1024**2


def format_bytes_human_readable(size_bytes: int) -> str:
    """Format bytes into human-readable string (GB, MB, or bytes)."""
    if size_bytes >= BYTES_PER_GB:
        return f"{size_bytes / BYTES_PER_GB:.1f} GB"
    if size_bytes >= BYTES_PER_MB:
        return f"{size_bytes / BYTES_PER_MB:.1f} MB"
    return f"{size_bytes} bytes"


def save_uploaded_files(
    files: list[UploadFile],
    target_dir: Path,
    allowed_extensions: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    uploaded_files: list[str] = []
    uploaded_file_paths: list[str] = []
    seen_names: set[str] = set()
    target_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        file_path = None
        original_filename = file.filename or "upload"
        try:
            sanitized_filename = DocumentValidator.validate_upload_safety(
                original_filename,
                None,
                allowed_extensions=allowed_extensions,
                content_type=file.content_type,
            )
            file.filename = sanitized_filename
            if sanitized_filename in seen_names:
                raise ValueError(f"Duplicate filename in upload batch: {sanitized_filename}")
            seen_names.add(sanitized_filename)

            file_path = target_dir / sanitized_filename
            max_size = DocumentValidator.MAX_FILE_SIZE
            written_bytes = 0

            with open(file_path, "wb") as buffer:
                for chunk in iter(lambda: file.file.read(8192), b""):
                    written_bytes += len(chunk)
                    if written_bytes > max_size:
                        size_str = format_bytes_human_readable(max_size)
                        raise HTTPException(
                            status_code=400,
                            detail=f"File '{sanitized_filename}' exceeds maximum size limit of {size_str}",
                        )
                    buffer.write(chunk)

            DocumentValidator.validate_upload_safety(
                sanitized_filename,
                written_bytes,
                allowed_extensions=allowed_extensions,
                content_type=file.content_type,
            )
            uploaded_files.append(sanitized_filename)
            uploaded_file_paths.append(str(file_path))
        except Exception as e:
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass
            for staged_path in uploaded_file_paths:
                try:
                    Path(staged_path).unlink()
                except OSError:
                    pass

            error_message = (
                f"Validation failed for file '{original_filename}': {format_exception_message(e)}"
            )
            logger.error(error_message, exc_info=True)
            raise HTTPException(status_code=400, detail=error_message) from e

    return uploaded_files, uploaded_file_paths


def cleanup_upload_staging(uploaded_file_paths: list[str], base_dir: str, kb_name: str) -> None:
    """Remove per-task upload staging dirs without touching raw or linked folders."""
    staging_root = (Path(base_dir) / kb_name / ".uploads").resolve()
    candidate_dirs: set[Path] = set()

    for file_path in uploaded_file_paths:
        try:
            parent = Path(file_path).resolve().parent
        except OSError:
            continue
        if parent == staging_root:
            continue
        if staging_root in parent.parents:
            candidate_dirs.add(parent)

    for directory in candidate_dirs:
        try:
            resolved = directory.resolve()
            if staging_root not in resolved.parents:
                continue
            shutil.rmtree(resolved, ignore_errors=True)
        except OSError:
            logger.debug("Failed to remove upload staging directory: %s", directory, exc_info=True)
