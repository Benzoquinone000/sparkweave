"""Text formatting helpers shared by SparkBot channels."""

from __future__ import annotations

import re
import unicodedata


def split_message(content: str, max_len: int) -> list[str]:
    if not content:
        return []
    if len(content) <= max_len:
        return [content]
    chunks: list[str] = []
    remaining = content
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        candidate = remaining[:max_len]
        split_at = candidate.rfind("\n")
        if split_at <= 0:
            split_at = candidate.rfind(" ")
        if split_at <= 0:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()
    return chunks


def strip_markdown_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def render_markdown_table_box(table_lines: list[str]) -> str:
    def display_width(value: str) -> int:
        return sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in value)

    rows: list[list[str]] = []
    has_separator = False
    for line in table_lines:
        cells = [strip_markdown_inline(cell) for cell in line.strip().strip("|").split("|")]
        if all(re.match(r"^:?-+:?$", cell) for cell in cells if cell):
            has_separator = True
            continue
        rows.append(cells)
    if not rows or not has_separator:
        return "\n".join(table_lines)

    columns = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (columns - len(row)))
    widths = [max(display_width(row[column]) for row in rows) for column in range(columns)]

    def render_row(cells: list[str]) -> str:
        return "  ".join(
            f"{cell}{' ' * (width - display_width(cell))}"
            for cell, width in zip(cells, widths)
        )

    output = [render_row(rows[0]), "  ".join("-" * width for width in widths)]
    output.extend(render_row(row) for row in rows[1:])
    return "\n".join(output)


def markdown_to_telegram_html(text: str) -> str:
    if not text:
        return ""

    code_blocks: list[str] = []

    def save_code_block(match: re.Match) -> str:
        code_blocks.append(match.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    lines = text.split("\n")
    rebuilt: list[str] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*\|.+\|", lines[index]):
            table: list[str] = []
            while index < len(lines) and re.match(r"^\s*\|.+\|", lines[index]):
                table.append(lines[index])
                index += 1
            box = render_markdown_table_box(table)
            if box != "\n".join(table):
                code_blocks.append(box)
                rebuilt.append(f"\x00CB{len(code_blocks) - 1}\x00")
            else:
                rebuilt.extend(table)
            continue
        rebuilt.append(lines[index])
        index += 1
    text = "\n".join(rebuilt)

    inline_codes: list[str] = []

    def save_inline_code(match: re.Match) -> str:
        inline_codes.append(match.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"^[-*]\s+", "- ", text, flags=re.MULTILINE)

    for index, code in enumerate(inline_codes):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{index}\x00", f"<code>{escaped}</code>")
    for index, code in enumerate(code_blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{index}\x00", f"<pre><code>{escaped}</code></pre>")
    return text


__all__ = [
    "markdown_to_telegram_html",
    "render_markdown_table_box",
    "split_message",
    "strip_markdown_inline",
]
