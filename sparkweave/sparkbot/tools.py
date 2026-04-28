"""Workspace-scoped tools used by the NG SparkBot agent loop."""

from __future__ import annotations

import asyncio
import difflib
import html
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from sparkweave.core.tool_protocol import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from sparkweave.tools.registry import ToolRegistry, get_tool_registry

_AGENT_NG_TOOL_NAMES = (
    "brainstorm",
    "rag",
    "web_search",
    "code_execution",
    "reason",
    "paper_search",
)
_USER_AGENT = "SparkWeave-SparkBot/1.0"
_MAX_FETCH_CHARS = 50_000
_MAX_EXEC_OUTPUT = 12_000
_MAX_EXEC_TIMEOUT = 600
_DENY_COMMAND_PATTERNS = (
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fq]\b",
    r"\brmdir\s+/s\b",
    r"(?:^|[;&|]\s*)format\b",
    r"\b(mkfs|diskpart)\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{.*\};\s*:",
    r"\bgit\s+reset\s+--hard\b",
)


def _resolve_workspace_path(path: str, workspace: Path) -> Path:
    raw = Path(path or ".").expanduser()
    candidate = raw if raw.is_absolute() else workspace / raw
    resolved = candidate.resolve()
    root = workspace.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"Path '{path}' is outside the SparkBot workspace") from exc
    return resolved


def _display_path(path: Path, workspace: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace.resolve()))
    except ValueError:
        return str(path)


def _find_edit_match(content: str, old_text: str) -> tuple[str | None, int]:
    if old_text in content:
        return old_text, content.count(old_text)

    old_lines = old_text.splitlines()
    if not old_lines:
        return None, 0
    stripped_old = [line.strip() for line in old_lines]
    content_lines = content.splitlines()
    matches: list[str] = []
    for index in range(len(content_lines) - len(stripped_old) + 1):
        window = content_lines[index : index + len(stripped_old)]
        if [line.strip() for line in window] == stripped_old:
            matches.append("\n".join(window))
    if matches:
        return matches[0], len(matches)
    return None, 0


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _html_to_markdown(text: str) -> str:
    text = re.sub(
        r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>",
        lambda match: f"[{_strip_html(match.group(2))}]({match.group(1)})",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<h([1-6])[^>]*>([\s\S]*?)</h\1>",
        lambda match: f"\n{'#' * int(match.group(1))} {_strip_html(match.group(2))}\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<li[^>]*>([\s\S]*?)</li>", lambda match: f"\n- {_strip_html(match.group(1))}", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|section|article)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(br|hr)\s*/?>", "\n", text, flags=re.IGNORECASE)
    return _normalize_text(_strip_html(text))


def _normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _format_search_result(query: str, payload: dict[str, Any]) -> str:
    answer = str(payload.get("answer") or payload.get("content") or "").strip()
    if answer:
        return answer
    rows = payload.get("search_results") or []
    if not rows:
        return f"No results for: {query}"
    lines = [f"Results for: {query}"]
    for index, item in enumerate(rows[:10], start=1):
        title = _normalize_text(str(item.get("title") or "Untitled"))
        url = str(item.get("url") or "")
        snippet = _normalize_text(str(item.get("snippet") or item.get("content") or ""))
        lines.append(f"{index}. {title}")
        if url:
            lines.append(f"   {url}")
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


def _validate_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        return str(exc)
    if parsed.scheme not in {"http", "https"}:
        return f"Only http/https URLs are allowed, got '{parsed.scheme or 'none'}'"
    if not parsed.netloc:
        return "URL is missing a host"
    return None


def _config_value(config: Any, names: tuple[str, ...], default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, dict):
        for name in names:
            if name in config:
                return config[name]
        return default
    for name in names:
        if hasattr(config, name):
            return getattr(config, name)
    return default


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value if value is not None else default)
    except (TypeError, ValueError):
        number = default
    return min(max(minimum, number), maximum)


def _absolute_paths_from_command(command: str) -> list[str]:
    windows = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)
    posix = re.findall(r"(?:^|[\s|>'\"])(/[^\s\"'>;|<]+)", command)
    home = re.findall(r"(?:^|[\s|>'\"])(~[^\s\"'>;|<]*)", command)
    return windows + posix + home


class _WorkspaceTool(BaseTool):
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def _resolve(self, path: str) -> Path:
        return _resolve_workspace_path(path, self.workspace)


class ReadFileTool(_WorkspaceTool):
    """Read UTF-8 text files from the SparkBot workspace."""

    _DEFAULT_LIMIT = 2000
    _MAX_CHARS = 128_000

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read a UTF-8 file from the SparkBot workspace and return numbered lines.",
            parameters=[
                ToolParameter(name="path", type="string", description="Workspace-relative file path."),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="1-based starting line number.",
                    required=False,
                    default=1,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum lines to return.",
                    required=False,
                    default=self._DEFAULT_LIMIT,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = str(kwargs.get("path") or "")
        offset = max(1, int(kwargs.get("offset") or 1))
        limit = max(1, int(kwargs.get("limit") or self._DEFAULT_LIMIT))
        try:
            target = self._resolve(path)
            if not target.exists():
                return ToolResult(content=f"Error: File not found: {path}", success=False)
            if not target.is_file():
                return ToolResult(content=f"Error: Not a file: {path}", success=False)
            lines = target.read_text(encoding="utf-8").splitlines()
        except PermissionError as exc:
            return ToolResult(content=f"Error: {exc}", success=False)
        except UnicodeDecodeError as exc:
            return ToolResult(content=f"Error: File is not valid UTF-8: {exc}", success=False)
        except OSError as exc:
            return ToolResult(content=f"Error reading file: {exc}", success=False)

        total = len(lines)
        if total == 0:
            return ToolResult(content=f"(Empty file: {path})", metadata={"path": str(target)})
        if offset > total:
            return ToolResult(
                content=f"Error: offset {offset} is beyond end of file ({total} lines)",
                success=False,
            )

        start = offset - 1
        end = min(start + limit, total)
        numbered = [f"{line_no}| {line}" for line_no, line in enumerate(lines[start:end], start=offset)]
        rendered = "\n".join(numbered)
        if len(rendered) > self._MAX_CHARS:
            rendered = rendered[: self._MAX_CHARS] + "\n...[truncated]"
        suffix = (
            f"\n\n(Showing lines {offset}-{end} of {total}. Use offset={end + 1} to continue.)"
            if end < total
            else f"\n\n(End of file - {total} lines total)"
        )
        return ToolResult(
            content=rendered + suffix,
            sources=[{"type": "file", "file": _display_path(target, self.workspace)}],
            metadata={"path": str(target), "offset": offset, "limit": limit, "total_lines": total},
        )


class WriteFileTool(_WorkspaceTool):
    """Write UTF-8 text files inside the SparkBot workspace."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write UTF-8 content to a workspace file, creating parent directories when needed.",
            parameters=[
                ToolParameter(name="path", type="string", description="Workspace-relative file path."),
                ToolParameter(name="content", type="string", description="Text content to write."),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = str(kwargs.get("path") or "")
        content = str(kwargs.get("content") or "")
        try:
            target = self._resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except PermissionError as exc:
            return ToolResult(content=f"Error: {exc}", success=False)
        except OSError as exc:
            return ToolResult(content=f"Error writing file: {exc}", success=False)
        display = _display_path(target, self.workspace)
        return ToolResult(
            content=f"Successfully wrote {len(content)} characters to {display}",
            sources=[{"type": "file", "file": display}],
            metadata={"path": str(target), "bytes": len(content.encode("utf-8"))},
        )


class EditFileTool(_WorkspaceTool):
    """Replace text inside UTF-8 files in the SparkBot workspace."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description="Replace old_text with new_text in a workspace file.",
            parameters=[
                ToolParameter(name="path", type="string", description="Workspace-relative file path."),
                ToolParameter(name="old_text", type="string", description="Text to replace."),
                ToolParameter(name="new_text", type="string", description="Replacement text."),
                ToolParameter(
                    name="replace_all",
                    type="boolean",
                    description="Replace every occurrence instead of only one.",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = str(kwargs.get("path") or "")
        old_text = str(kwargs.get("old_text") or "")
        new_text = str(kwargs.get("new_text") or "")
        replace_all = bool(kwargs.get("replace_all", False))
        if not old_text:
            return ToolResult(content="Error: old_text is required", success=False)
        try:
            target = self._resolve(path)
            if not target.exists():
                return ToolResult(content=f"Error: File not found: {path}", success=False)
            raw = target.read_bytes()
            uses_crlf = b"\r\n" in raw
            content = raw.decode("utf-8").replace("\r\n", "\n")
            match, count = _find_edit_match(content, old_text.replace("\r\n", "\n"))
            if match is None:
                return ToolResult(
                    content=self._not_found_message(old_text, content, path),
                    success=False,
                )
            if count > 1 and not replace_all:
                return ToolResult(
                    content=(
                        f"Warning: old_text appears {count} times. Provide more context "
                        "or set replace_all=true."
                    ),
                    success=False,
                )
            replacement = new_text.replace("\r\n", "\n")
            edited = content.replace(match, replacement) if replace_all else content.replace(match, replacement, 1)
            if uses_crlf:
                edited = edited.replace("\n", "\r\n")
            target.write_bytes(edited.encode("utf-8"))
        except PermissionError as exc:
            return ToolResult(content=f"Error: {exc}", success=False)
        except UnicodeDecodeError as exc:
            return ToolResult(content=f"Error: File is not valid UTF-8: {exc}", success=False)
        except OSError as exc:
            return ToolResult(content=f"Error editing file: {exc}", success=False)
        display = _display_path(target, self.workspace)
        return ToolResult(
            content=f"Successfully edited {display}",
            sources=[{"type": "file", "file": display}],
            metadata={"path": str(target), "replace_all": replace_all},
        )

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = max(1, len(old_lines))
        best_ratio = 0.0
        best_start = 0
        old_sample = "".join(old_lines)
        for index in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(
                None,
                old_sample,
                "".join(lines[index : index + window]),
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = index

        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return (
                f"Error: old_text not found in {path}.\n"
                f"Best match ({best_ratio:.0%} similar) at line {best_start + 1}:\n"
                f"{diff}"
            )
        return f"Error: old_text not found in {path}. No similar text found."


class ListDirTool(_WorkspaceTool):
    """List files and folders inside the SparkBot workspace."""

    _IGNORE_DIRS = {
        ".coverage",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "venv",
    }

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_dir",
            description="List a workspace directory with file types and sizes.",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Workspace-relative directory path.",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="max_entries",
                    type="integer",
                    description="Maximum entries to show.",
                    required=False,
                    default=200,
                ),
                ToolParameter(
                    name="include_hidden",
                    type="boolean",
                    description="Include dotfiles and dot-directories.",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="recursive",
                    type="boolean",
                    description="Recursively list nested files and folders.",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = str(kwargs.get("path") or ".")
        max_entries = max(1, int(kwargs.get("max_entries") or 200))
        include_hidden = bool(kwargs.get("include_hidden", False))
        recursive = bool(kwargs.get("recursive", False))
        try:
            target = self._resolve(path)
            if not target.exists():
                return ToolResult(content=f"Error: Directory not found: {path}", success=False)
            if not target.is_dir():
                return ToolResult(content=f"Error: Not a directory: {path}", success=False)
            children = (
                sorted(target.rglob("*"), key=lambda item: str(item.relative_to(target)).lower())
                if recursive
                else sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
            )
        except PermissionError as exc:
            return ToolResult(content=f"Error: {exc}", success=False)
        except OSError as exc:
            return ToolResult(content=f"Error listing directory: {exc}", success=False)

        visible = [
            item
            for item in children
            if self._is_visible_entry(item, root=target, include_hidden=include_hidden)
        ]
        lines = [f"Directory: {_display_path(target, self.workspace) or '.'}"]
        for item in visible[:max_entries]:
            name = (
                str(item.relative_to(target)).replace("\\", "/")
                if recursive
                else item.name
            )
            if item.is_dir():
                lines.append(f"- dir  {name}/")
            else:
                try:
                    size = item.stat().st_size
                except OSError:
                    size = 0
                lines.append(f"- file {name} ({size} bytes)")
        if len(visible) > max_entries:
            lines.append(f"... {len(visible) - max_entries} more entries")
        return ToolResult(
            content="\n".join(lines),
            sources=[{"type": "directory", "file": _display_path(target, self.workspace)}],
            metadata={"path": str(target), "entries": len(visible), "recursive": recursive},
        )

    @classmethod
    def _is_visible_entry(cls, item: Path, *, root: Path, include_hidden: bool) -> bool:
        try:
            parts = item.relative_to(root).parts
        except ValueError:
            parts = item.parts
        if not include_hidden and any(part.startswith(".") for part in parts):
            return False
        return not any(part in cls._IGNORE_DIRS for part in parts)


class ExecTool(_WorkspaceTool):
    """Run conservative shell commands inside the SparkBot workspace."""

    def __init__(
        self,
        workspace: Path,
        *,
        default_timeout: int = 60,
        path_append: str = "",
        max_timeout: int = _MAX_EXEC_TIMEOUT,
    ) -> None:
        super().__init__(workspace)
        self.max_timeout = max(1, int(max_timeout or _MAX_EXEC_TIMEOUT))
        self.default_timeout = _clamp_int(
            default_timeout,
            default=60,
            minimum=1,
            maximum=self.max_timeout,
        )
        self.path_append = str(path_append or "")

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="exec",
            description=(
                "Execute a shell command from inside the SparkBot workspace. "
                "Dangerous commands and paths outside the workspace are blocked."
            ),
            parameters=[
                ToolParameter(name="command", type="string", description="Shell command to execute."),
                ToolParameter(
                    name="working_dir",
                    type="string",
                    description="Workspace-relative working directory.",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Timeout in seconds.",
                    required=False,
                    default=self.default_timeout,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        command = str(kwargs.get("command") or "").strip()
        if not command:
            return ToolResult(content="Error: command is required", success=False)
        working_dir = str(kwargs.get("working_dir") or ".")
        timeout = _clamp_int(
            kwargs.get("timeout"),
            default=self.default_timeout,
            minimum=1,
            maximum=self.max_timeout,
        )
        try:
            cwd = self._resolve(working_dir)
            cwd.mkdir(parents=True, exist_ok=True)
            guard_error = self._guard_command(command, cwd)
            if guard_error:
                return ToolResult(content=f"Error: {guard_error}", success=False)
            env = os.environ.copy()
            if self.path_append:
                env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(content=f"Error: Command timed out after {timeout} seconds", success=False)
        except PermissionError as exc:
            return ToolResult(content=f"Error: {exc}", success=False)
        except OSError as exc:
            return ToolResult(content=f"Error executing command: {exc}", success=False)

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
        parts: list[str] = []
        if stdout_text:
            parts.append(stdout_text.rstrip())
        if stderr_text.strip():
            parts.append(f"STDERR:\n{stderr_text.rstrip()}")
        parts.append(f"Exit code: {process.returncode}")
        content = "\n".join(parts)
        if len(content) > _MAX_EXEC_OUTPUT:
            half = _MAX_EXEC_OUTPUT // 2
            content = f"{content[:half]}\n\n...[truncated]...\n\n{content[-half:]}"
        return ToolResult(
            content=content,
            success=process.returncode == 0,
            metadata={"cwd": str(cwd), "exit_code": process.returncode, "timeout": timeout},
        )

    def _guard_command(self, command: str, cwd: Path) -> str | None:
        lowered = command.lower()
        for pattern in _DENY_COMMAND_PATTERNS:
            if re.search(pattern, lowered):
                return "Command blocked by safety guard"
        if "../" in command or "..\\" in command:
            return "Command blocked by path traversal guard"
        workspace = self.workspace.resolve()
        for raw_path in _absolute_paths_from_command(command):
            try:
                resolved = Path(os.path.expandvars(raw_path)).expanduser().resolve()
            except OSError:
                continue
            try:
                resolved.relative_to(workspace)
            except ValueError:
                return f"Command references path outside workspace: {raw_path}"
        try:
            cwd.resolve().relative_to(workspace)
        except ValueError:
            return "Working directory is outside workspace"
        return None


class WebFetchTool(BaseTool):
    """Fetch and lightly extract text from an HTTP(S) URL."""

    def __init__(
        self,
        *,
        max_chars: int = _MAX_FETCH_CHARS,
        proxy: str | None = None,
    ) -> None:
        self.max_chars = _clamp_int(
            max_chars,
            default=_MAX_FETCH_CHARS,
            minimum=100,
            maximum=_MAX_FETCH_CHARS,
        )
        self.proxy = proxy

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_fetch",
            description="Fetch an http/https URL and extract readable markdown or plain text.",
            parameters=[
                ToolParameter(name="url", type="string", description="URL to fetch."),
                ToolParameter(
                    name="extract_mode",
                    type="string",
                    description="Extraction mode: markdown or text.",
                    required=False,
                    default="markdown",
                    enum=["markdown", "text"],
                ),
                ToolParameter(
                    name="max_chars",
                    type="integer",
                    description="Maximum returned characters.",
                    required=False,
                    default=self.max_chars,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = str(kwargs.get("url") or "").strip()
        mode = str(kwargs.get("extract_mode") or kwargs.get("extractMode") or "markdown").strip().lower()
        max_chars = _clamp_int(
            kwargs.get("max_chars") or kwargs.get("maxChars"),
            default=self.max_chars,
            minimum=100,
            maximum=_MAX_FETCH_CHARS,
        )
        error = _validate_url(url)
        if error:
            return ToolResult(content=f"Error: URL validation failed: {error}", success=False)
        jina_result = await self._fetch_jina(url, max_chars=max_chars)
        if jina_result is not None:
            return jina_result
        try:
            response = await self._fetch(url)
            content_type = response.headers.get("content-type", "")
            raw_text = response.text
        except httpx.HTTPError as exc:
            return ToolResult(content=f"Error fetching URL: {exc}", success=False, sources=[{"type": "url", "url": url}])
        except OSError as exc:
            return ToolResult(content=f"Error fetching URL: {exc}", success=False, sources=[{"type": "url", "url": url}])

        if "application/json" in content_type:
            extracted = raw_text
            extractor = "json"
        elif "text/html" in content_type or raw_text[:256].lower().lstrip().startswith(("<!doctype", "<html")):
            extracted = _html_to_markdown(raw_text) if mode == "markdown" else _normalize_text(_strip_html(raw_text))
            extractor = "html"
        else:
            extracted = _normalize_text(raw_text)
            extractor = "text"
        truncated = len(extracted) > max_chars
        if truncated:
            extracted = extracted[:max_chars]
        return ToolResult(
            content=extracted or "(No readable content extracted.)",
            success=True,
            sources=[{"type": "url", "url": str(response.url)}],
            metadata={
                "url": url,
                "final_url": str(response.url),
                "status_code": response.status_code,
                "content_type": content_type,
                "extractor": extractor,
                "truncated": truncated,
            },
        )

    async def _fetch_jina(self, url: str, *, max_chars: int) -> ToolResult | None:
        headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
        jina_key = os.environ.get("JINA_API_KEY", "")
        if jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"
        try:
            async with httpx.AsyncClient(timeout=20.0, proxy=self.proxy) as client:
                response = await client.get(f"https://r.jina.ai/{url}", headers=headers)
            if response.status_code == 429:
                return None
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        text = str(data.get("content") or "").strip()
        if not text:
            return None
        title = str(data.get("title") or "").strip()
        if title:
            text = f"# {title}\n\n{text}"
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]
        return ToolResult(
            content=text,
            success=True,
            sources=[{"type": "url", "url": str(data.get("url") or url)}],
            metadata={
                "url": url,
                "final_url": str(data.get("url") or url),
                "status_code": response.status_code,
                "extractor": "jina",
                "truncated": truncated,
            },
        )

    async def _fetch(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": _USER_AGENT},
            proxy=self.proxy,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response


class WebSearchTool(BaseTool):
    """Search the web using SparkBot's bot-level web.search config first."""

    _API_KEY_OPTIONAL_FALLBACKS = {"brave", "tavily", "jina"}

    def __init__(
        self,
        *,
        provider: str = "brave",
        api_key: str = "",
        base_url: str = "",
        max_results: int = 5,
        proxy: str | None = None,
    ) -> None:
        self.provider = str(provider or "brave").strip().lower()
        self.api_key = str(api_key or "")
        self.base_url = str(base_url or "")
        self.max_results = _clamp_int(max_results, default=5, minimum=1, maximum=10)
        self.proxy = proxy

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web using this SparkBot's configured provider.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
                ToolParameter(
                    name="count",
                    type="integer",
                    description="Maximum results to return.",
                    required=False,
                    default=self.max_results,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(content="Error: query is required", success=False)
        count = _clamp_int(
            kwargs.get("count") or kwargs.get("max_results") or kwargs.get("maxResults"),
            default=self.max_results,
            minimum=1,
            maximum=10,
        )
        provider_name = self._effective_provider_name()
        provider_kwargs = self._provider_kwargs(count)
        try:
            provider = self._get_provider(provider_name, provider_kwargs)
            response = await asyncio.to_thread(
                provider.search,
                query,
                max_results=count,
                base_url=self.base_url,
            )
        except Exception as exc:
            return ToolResult(
                content=f"Error searching web with {provider_name}: {exc}",
                success=False,
                metadata={"provider": provider_name, "query": query},
            )

        payload = response.to_dict()
        citations = payload.get("citations") or []
        return ToolResult(
            content=_format_search_result(query, payload),
            sources=[
                {"type": "web", "url": citation.get("url", ""), "title": citation.get("title", "")}
                for citation in citations
            ],
            metadata=payload,
        )

    def _effective_provider_name(self) -> str:
        if self.provider == "searxng" and not self.base_url:
            return "duckduckgo"
        return self.provider or "brave"

    def _provider_kwargs(self, count: int) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"max_results": count}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    def _get_provider(self, provider_name: str, provider_kwargs: dict[str, Any]) -> Any:
        from sparkweave.services.search_support.providers import get_provider

        try:
            return get_provider(provider_name, **provider_kwargs)
        except ValueError:
            if provider_name in self._API_KEY_OPTIONAL_FALLBACKS:
                fallback_kwargs = {"max_results": provider_kwargs["max_results"]}
                if self.proxy:
                    fallback_kwargs["proxy"] = self.proxy
                return get_provider("duckduckgo", **fallback_kwargs)
            raise


class SparkBotNgToolAdapter(BaseTool):
    """Expose selected NG tools to SparkBot with SparkBot-friendly defaults."""

    def __init__(self, tool: BaseTool, workspace: Path) -> None:
        self.tool = tool
        self.workspace = workspace

    def get_definition(self) -> ToolDefinition:
        return self.tool.get_definition()

    async def execute(self, **kwargs: Any) -> ToolResult:
        if self.name == "code_execution":
            run_dir = self.workspace / ".tool_runs" / "code_execution"
            kwargs.setdefault("workspace_dir", str(run_dir))
            kwargs.setdefault("feature", "SparkBot_agent")
        return await self.tool.execute(**kwargs)


def build_sparkbot_agent_tool_registry(workspace: Path, config: Any | None = None) -> ToolRegistry:
    """Build the workspace-scoped SparkBot agent tool registry."""

    registry = ToolRegistry()
    for tool_type in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
        registry.register(tool_type(workspace))
    exec_config = _config_value(config, ("exec_config", "exec"), {}) or {}
    web_config = _config_value(config, ("web",), {}) or {}
    search_config = _config_value(web_config, ("search",), {}) or {}
    registry.register(
        ExecTool(
            workspace,
            default_timeout=_config_value(exec_config, ("timeout",), 60),
            path_append=_config_value(exec_config, ("path_append", "pathAppend"), ""),
        )
    )
    registry.register(
        WebSearchTool(
            provider=_config_value(search_config, ("provider",), "brave"),
            api_key=_config_value(search_config, ("api_key", "apiKey"), ""),
            base_url=_config_value(search_config, ("base_url", "baseUrl"), ""),
            max_results=_config_value(search_config, ("max_results", "maxResults"), 5),
            proxy=_config_value(web_config, ("proxy",), None),
        )
    )
    registry.register(
        WebFetchTool(
            max_chars=_config_value(web_config, ("fetch_max_chars", "fetchMaxChars"), _MAX_FETCH_CHARS),
            proxy=_config_value(web_config, ("proxy",), None),
        )
    )
    ng_registry = get_tool_registry()
    for tool_name in _AGENT_NG_TOOL_NAMES:
        tool = ng_registry.get(tool_name)
        if tool is not None and tool.name not in registry.list_tools():
            registry.register(SparkBotNgToolAdapter(tool, workspace))
    return registry


__all__ = [
    "EditFileTool",
    "ExecTool",
    "ListDirTool",
    "ReadFileTool",
    "SparkBotNgToolAdapter",
    "WebFetchTool",
    "WebSearchTool",
    "WriteFileTool",
    "build_sparkbot_agent_tool_registry",
]

