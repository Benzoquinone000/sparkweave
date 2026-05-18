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
    MAX_FILENAME_LENGTH: ClassVar[int] = 180
    RESERVED_WINDOWS_NAMES: ClassVar[set[str]] = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    GENERIC_MIME_TYPES: ClassVar[set[str]] = {
        "application/octet-stream",
        "binary/octet-stream",
    }
    TEXT_LIKE_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".md",
        ".rtf",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".csv",
    }

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
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
    }

    EXTENSION_MIME_TYPES: ClassVar[dict[str, set[str]]] = {
        ".pdf": {"application/pdf"},
        ".txt": {"text/plain"},
        ".md": {"text/markdown", "text/plain"},
        ".doc": {"application/msword"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".rtf": {"application/rtf", "text/rtf"},
        ".html": {"text/html"},
        ".htm": {"text/html"},
        ".xml": {"application/xml", "text/xml"},
        ".json": {"application/json", "text/json"},
        ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".xls": {"application/vnd.ms-excel"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        ".ppt": {"application/vnd.ms-powerpoint"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".gif": {"image/gif"},
        ".webp": {"image/webp"},
        ".bmp": {"image/bmp", "image/x-ms-bmp"},
        ".tif": {"image/tiff"},
        ".tiff": {"image/tiff"},
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
        content_type: str | None = None,
    ) -> str:
        if file_size is not None and file_size > DocumentValidator.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_size} bytes. "
                f"Maximum allowed: {DocumentValidator.MAX_FILE_SIZE} bytes"
            )

        safe_name = DocumentValidator.sanitize_filename(filename)
        _, ext = os.path.splitext(safe_name.lower())
        if ext == ".pdf" and file_size is not None and file_size > DocumentValidator.MAX_PDF_SIZE:
            raise ValueError(
                f"PDF file too large: {file_size} bytes. "
                f"Maximum allowed for PDFs: {DocumentValidator.MAX_PDF_SIZE} bytes"
            )

        exts_to_check = {item.lower() for item in (allowed_extensions or DocumentValidator.ALLOWED_EXTENSIONS)}
        if ext not in exts_to_check:
            raise ValueError(
                f"Unsupported file type: {ext}. Allowed types: {', '.join(exts_to_check)}"
            )

        guessed_mime, _ = mimetypes.guess_type(safe_name.lower())
        if guessed_mime and not DocumentValidator._is_allowed_mime(guessed_mime):
            raise ValueError(
                f"MIME type validation failed: {guessed_mime}. "
                "File may be malicious or corrupted."
            )
        DocumentValidator._validate_declared_mime(ext, content_type)

        return safe_name

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Return a single safe filename, rejecting reserved or ambiguous names."""
        raw_name = str(filename or "").strip()
        base_name = re.split(r"[\\/]+", raw_name)[-1]
        safe_name = re.sub(r"[\x00-\x1f\x7f]", "", base_name)
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name)
        safe_name = safe_name.strip(" .")
        safe_name = re.sub(r"\s+", " ", safe_name)

        if not safe_name or safe_name in (".", "..") or safe_name.strip("_") == "":
            raise ValueError("Invalid filename")

        stem, ext = os.path.splitext(safe_name)
        reserved_stem = stem.rstrip(" .").upper()
        if reserved_stem in DocumentValidator.RESERVED_WINDOWS_NAMES:
            raise ValueError("Reserved filename")

        if len(safe_name) > DocumentValidator.MAX_FILENAME_LENGTH:
            max_stem_length = max(1, DocumentValidator.MAX_FILENAME_LENGTH - len(ext))
            safe_name = f"{stem[:max_stem_length].rstrip(' .')}{ext}"

        if not safe_name or safe_name in (".", "..") or safe_name.strip("_") == "":
            raise ValueError("Invalid filename")
        return safe_name

    @staticmethod
    def _is_allowed_mime(mime_type: str) -> bool:
        return (
            mime_type in DocumentValidator.ALLOWED_MIME_TYPES
            or mime_type in DocumentValidator.TEXT_LIKE_MIME_TYPES
            or mime_type.startswith("text/")
        )

    @staticmethod
    def _normalize_mime(content_type: str | None) -> str:
        return (content_type or "").split(";", 1)[0].strip().lower()

    @staticmethod
    def _validate_declared_mime(ext: str, content_type: str | None) -> None:
        declared_mime = DocumentValidator._normalize_mime(content_type)
        if not declared_mime or declared_mime in DocumentValidator.GENERIC_MIME_TYPES:
            return
        if not DocumentValidator._is_allowed_mime(declared_mime):
            raise ValueError(
                f"MIME type validation failed: {declared_mime}. File may be malicious or corrupted."
            )

        expected = DocumentValidator.EXTENSION_MIME_TYPES.get(ext)
        if ext in DocumentValidator.TEXT_LIKE_EXTENSIONS and declared_mime == "text/plain":
            return
        if expected and declared_mime not in expected:
            raise ValueError(
                f"MIME type does not match file extension: {declared_mime} for {ext}"
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
