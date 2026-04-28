"""Document upload validation helpers."""

from __future__ import annotations

import mimetypes
import os
import re
from typing import ClassVar


class DocumentValidator:
    """Document validation utilities."""

    MAX_FILE_SIZE: ClassVar[int] = 100 * 1024 * 1024
    MAX_PDF_SIZE: ClassVar[int] = 50 * 1024 * 1024

    ALLOWED_EXTENSIONS: ClassVar[set[str]] = {
        ".pdf",
        ".txt",
        ".md",
        ".doc",
        ".docx",
        ".rtf",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".csv",
        ".xlsx",
        ".xls",
        ".pptx",
        ".ppt",
    }

    ALLOWED_MIME_TYPES: ClassVar[set[str]] = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/rtf",
        "text/html",
        "application/xml",
        "text/xml",
        "application/json",
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    TEXT_LIKE_MIME_TYPES: ClassVar[set[str]] = {
        "application/javascript",
        "application/json",
        "application/toml",
        "application/x-csh",
        "application/x-httpd-php",
        "application/x-javascript",
        "application/x-ksh",
        "application/x-powershell",
        "application/x-python-code",
        "application/x-sh",
        "application/x-shellscript",
        "application/x-yaml",
        "application/xml",
    }

    @staticmethod
    def validate_upload_safety(
        filename: str,
        file_size: int | None,
        allowed_extensions: set[str] | None = None,
    ) -> str:
        if file_size is not None and file_size > DocumentValidator.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_size} bytes. "
                f"Maximum allowed: {DocumentValidator.MAX_FILE_SIZE} bytes"
            )

        _, ext = os.path.splitext(filename.lower())
        if ext == ".pdf" and file_size is not None and file_size > DocumentValidator.MAX_PDF_SIZE:
            raise ValueError(
                f"PDF file too large: {file_size} bytes. "
                f"Maximum allowed for PDFs: {DocumentValidator.MAX_PDF_SIZE} bytes"
            )

        safe_name = os.path.basename(filename)
        safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name)
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name)

        if not safe_name or safe_name in (".", "..") or safe_name.strip("_") == "":
            raise ValueError("Invalid filename")

        exts_to_check = allowed_extensions or DocumentValidator.ALLOWED_EXTENSIONS
        if ext not in exts_to_check:
            raise ValueError(
                f"Unsupported file type: {ext}. Allowed types: {', '.join(exts_to_check)}"
            )

        guessed_mime, _ = mimetypes.guess_type(filename.lower())
        if guessed_mime and not DocumentValidator._is_allowed_mime(guessed_mime):
            raise ValueError(
                f"MIME type validation failed: {guessed_mime}. "
                "File may be malicious or corrupted."
            )

        return safe_name

    @staticmethod
    def _is_allowed_mime(mime_type: str) -> bool:
        return (
            mime_type in DocumentValidator.ALLOWED_MIME_TYPES
            or mime_type in DocumentValidator.TEXT_LIKE_MIME_TYPES
            or mime_type.startswith("text/")
        )

    @staticmethod
    def get_file_info(filename: str, file_size: int) -> dict:
        _, ext = os.path.splitext(filename.lower())
        return {
            "filename": filename,
            "extension": ext,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "is_allowed": ext in DocumentValidator.ALLOWED_EXTENSIONS,
        }

    @staticmethod
    def validate_file(path: str) -> dict:
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        if not os.path.isfile(path):
            raise ValueError(f"Not a file: {path}")
        if not os.access(path, os.R_OK):
            raise ValueError(f"File not readable: {path}")

        size = os.path.getsize(path)
        filename = os.path.basename(path)
        safe_name = DocumentValidator.validate_upload_safety(filename, size)
        return DocumentValidator.get_file_info(safe_name, size)


__all__ = ["DocumentValidator"]
