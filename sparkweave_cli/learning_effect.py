"""CLI commands for learning-effect closed-loop reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from rich.markdown import Markdown
import typer

from sparkweave.services.learning_effect import get_learning_effect_service

from .common import console


def register(app: typer.Typer) -> None:
    @app.command("summary")
    def learning_effect_summary(
        course_id: str = typer.Option("", "--course-id", help="Optional course id filter."),
        window: str = typer.Option("14d", "--window", help="Evidence window, e.g. 7d, 14d, all."),
        fmt: str = typer.Option("text", "--format", "-f", help="Output format: text | json."),
        output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional file path to write the summary."),
    ) -> None:
        """Print a presentation-friendly learning-effect closed-loop summary.

        Markdown output starts with ``学习效果评估闭环摘要``.
        """

        summary = get_learning_effect_service().demo_summary(course_id=course_id, window=window)
        if output is not None:
            _write_summary(output, summary, fmt=fmt)
            console.print(f"[green]已写出学习效果摘要：[/] {output}")
            return

        if fmt == "json":
            console.print_json(json.dumps(summary, ensure_ascii=False))
            return
        console.print(Markdown(str(summary.get("markdown") or "")))


def _write_summary(path: Path, summary: dict[str, Any], *, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json" or path.suffix.lower() == ".json":
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    path.write_text(str(summary.get("markdown") or ""), encoding="utf-8")
