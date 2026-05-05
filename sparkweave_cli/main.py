"""CLI entry point for the standalone ``sparkweave-cli`` package."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional

import typer

from sparkweave.runtime.mode import RunMode, set_mode
from sparkweave.services.setup import get_backend_port

from .bot import register as register_bot
from .chat import register as register_chat
from .common import build_turn_request, console, maybe_run
from .config_cmd import register as register_config
from .kb import register as register_kb
from .learning_effect import register as register_learning_effect
from .memory import register as register_memory
from .notebook import register as register_notebook
from .plugin import register as register_plugin
from .provider_cmd import register as register_provider
from .session_cmd import register as register_session

set_mode(RunMode.CLI)

app = typer.Typer(
    name="sparkweave",
    help="SparkWeave CLI: agent-first interface for capabilities, tools, and knowledge.",
    no_args_is_help=True,
    add_completion=False,
)

bot_app = typer.Typer(help="Manage SparkBot instances.")
chat_app = typer.Typer(help="Interactive chat REPL.")
kb_app = typer.Typer(help="Manage knowledge bases.")
memory_app = typer.Typer(help="View and manage lightweight memory.")
plugin_app = typer.Typer(help="List plugins.")
config_app = typer.Typer(help="Inspect configuration.")
session_app = typer.Typer(help="Manage shared sessions.")
notebook_app = typer.Typer(help="Manage notebooks and imported markdown records.")
provider_app = typer.Typer(help="Manage provider OAuth login.")
learning_effect_app = typer.Typer(help="Inspect learning-effect closed-loop reports.")

app.add_typer(bot_app, name="bot")
app.add_typer(bot_app, name="sparkbot")
app.add_typer(chat_app, name="chat")
app.add_typer(kb_app, name="kb")
app.add_typer(memory_app, name="memory")
app.add_typer(plugin_app, name="plugin")
app.add_typer(config_app, name="config")
app.add_typer(session_app, name="session")
app.add_typer(notebook_app, name="notebook")
app.add_typer(provider_app, name="provider")
app.add_typer(learning_effect_app, name="learning-effect")

register_bot(bot_app)
register_chat(chat_app)
register_kb(kb_app)
register_memory(memory_app)
register_plugin(plugin_app)
register_config(config_app)
register_session(session_app)
register_notebook(notebook_app)
register_provider(provider_app)
register_learning_effect(learning_effect_app)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _project_script_cmd(script_name: str, args: list[str]) -> list[str]:
    return [sys.executable, str(_repo_root() / "scripts" / script_name), *args]


def _run_project_script(script_name: str, args: list[str]) -> None:
    root = _repo_root()
    result = subprocess.run(_project_script_cmd(script_name, args), cwd=root, check=False)
    raise typer.Exit(code=result.returncode)


def _default_readiness_report() -> Path:
    return _repo_root() / "dist" / "competition-readiness.json"


def _default_competition_package() -> Path:
    return _repo_root() / "dist" / "competition_package"


def _render_readiness_summary(report: Path, summary: Path) -> None:
    root = _repo_root()
    result = subprocess.run(
        _project_script_cmd("render_competition_summary.py", [str(report), "--output", str(summary)]),
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)


def _verify_competition_package(package: Path, *, report: Optional[Path] = None) -> None:
    root = _repo_root()
    args = [str(package)]
    if report is not None:
        args.extend(["--output", str(report)])
    result = subprocess.run(
        _project_script_cmd("verify_competition_package.py", args),
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)


def _append_package_verification_summary(summary: Path, verify_report: Path) -> None:
    if not summary.exists() or not verify_report.exists():
        return
    try:
        report = json.loads(verify_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    ok = bool(report.get("ok"))
    status = "OK" if ok else "需要处理"
    path = str(report.get("path") or verify_report)
    file_count = int(report.get("file_count") or 0)
    checksum_count = int(report.get("checksum_count") or 0)
    archive_entries = int(report.get("archive_entries") or 0)
    headline = str(report.get("headline") or "").strip()
    errors = [str(item) for item in report.get("errors") or [] if str(item).strip()]

    lines = [
        "",
        "## 最终提交包验证",
        "",
        f"- {status} **提交包完整性**：{headline or path}",
        f"- 产物：`{path}`",
        f"- 文件数：{file_count}；SHA256 校验项：{checksum_count}；zip 条目：{archive_entries}",
    ]
    if errors:
        lines.append("- 需要处理：" + "；".join(errors[:3]))

    with summary.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _npm_command() -> str:
    if sys.platform == "win32":
        return shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
    return shutil.which("npm") or "npm"


@app.command("run")
def run_capability(
    capability: str = typer.Argument(
        ...,
        help="Capability name (e.g. chat, deep_solve, deep_question, deep_research, math_animator).",
    ),
    message: str = typer.Argument(..., help="Message to send."),
    session: Optional[str] = typer.Option(None, "--session", help="Existing session id."),
    tool: list[str] = typer.Option([], "--tool", "-t", help="Enabled tool(s)."),
    kb: list[str] = typer.Option([], "--kb", help="Knowledge base name."),
    notebook_ref: list[str] = typer.Option([], "--notebook-ref", help="Notebook references."),
    history_ref: list[str] = typer.Option([], "--history-ref", help="Referenced session ids."),
    language: str = typer.Option("en", "--language", "-l", help="Response language."),
    config: list[str] = typer.Option([], "--config", help="Capability config key=value."),
    config_json: Optional[str] = typer.Option(
        None, "--config-json", help="Capability config as JSON."
    ),
    runtime: str = typer.Option(
        "",
        "--runtime",
        help=(
            "Runtime engine: langgraph | auto | compatibility. "
            "The legacy alias is still accepted; compatibility falls back to NG "
            "when no injected runtime is available."
        ),
    ),
    fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
) -> None:
    """Run any capability in a single turn (agent-first entry point)."""
    from sparkweave.app import SparkWeaveApp

    from .common import run_turn_and_render

    request = build_turn_request(
        content=message,
        capability=capability,
        session_id=session,
        tools=tool,
        knowledge_bases=kb,
        language=language,
        config_items=config,
        config_json=config_json,
        runtime=runtime,
        notebook_refs=notebook_ref,
        history_refs=history_ref,
    )
    maybe_run(run_turn_and_render(app=SparkWeaveApp(), request=request, fmt=fmt))


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind address."),
    port: int = typer.Option(get_backend_port(), help="Port number."),
    reload: bool = typer.Option(False, help="Enable auto-reload for development."),
) -> None:
    """Start the SparkWeave API server."""
    import asyncio

    set_mode(RunMode.SERVER)

    # Windows: uvicorn defaults to SelectorEventLoop which does not support
    # asyncio.create_subprocess_exec.  Switch to ProactorEventLoop so that
    # child-process APIs (used by Math Animator renderer, etc.) work correctly.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        import uvicorn
    except ImportError:
        console.print(
            "[bold red]Error:[/] API server dependencies not installed.\n"
            "Run: pip install -r requirements/server.txt"
        )
        raise typer.Exit(code=1)

    uvicorn.run(
        "sparkweave.api.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_excludes=["web/*", "data/*"] if reload else None,
    )


@app.command("competition-check")
def competition_check(
    fmt: str = typer.Option("text", "--format", "-f", help="Output format: text | json."),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write a JSON readiness report.",
    ),
    summary: Optional[Path] = typer.Option(
        None,
        "--summary",
        help="Optional path to write a concise Markdown readiness summary.",
    ),
) -> None:
    """Check whether key competition submission materials are ready."""

    if summary is not None and output is None:
        output = _default_readiness_report()
    cmd = ["--format", fmt]
    if output is not None:
        cmd.extend(["--output", str(output)])
    root = _repo_root()
    result = subprocess.run(_project_script_cmd("check_competition_readiness.py", cmd), cwd=root, check=False)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)
    if summary is not None:
        _render_readiness_summary(output or _default_readiness_report(), summary)


@app.command("competition-templates")
def competition_templates(
    fmt: str = typer.Option("text", "--format", "-f", help="Output format: text | json."),
) -> None:
    """List built-in course templates suitable for demo and submission packages."""

    template_dir = _repo_root() / "data" / "course_templates"
    templates: list[dict[str, str]] = []
    for path in sorted(template_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        templates.append(
            {
                "id": str(payload.get("id") or path.stem),
                "course_name": str(payload.get("course_name") or payload.get("title") or path.stem),
                "path": str(path.relative_to(_repo_root())).replace("\\", "/"),
            }
        )

    if fmt == "json":
        print(json.dumps(templates, ensure_ascii=False))
        return

    console.print("[bold]Competition course templates[/]")
    for item in templates:
        console.print(f"- [cyan]{item['id']}[/]：{item['course_name']}")


@app.command("competition-demo")
def competition_demo(
    template: str = typer.Option(
        "ai_learning_agents_systems",
        "--template",
        "-t",
        help="Course template id for demo materials.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory. Defaults to dist/demo_materials.",
    ),
) -> None:
    """Export offline PPT outline, recording script, scorecard, and defense notes."""

    cmd = ["--template", template]
    if output is not None:
        cmd.extend(["--output", str(output)])
    _run_project_script("export_demo_materials.py", cmd)


@app.command("competition-package")
def competition_package(
    template: str = typer.Option(
        "ai_learning_agents_systems",
        "--template",
        "-t",
        help="Course template id for demo materials.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory. Defaults to dist/competition_package.",
    ),
    no_clean: bool = typer.Option(False, "--no-clean", help="Do not remove output before exporting."),
    archive: Optional[Path] = typer.Option(
        None,
        "--archive",
        help="Optional zip archive path to create after exporting.",
    ),
) -> None:
    """Export a competition submission package with docs, screenshots, runtime files, and demo materials."""

    cmd = ["--template", template]
    if output is not None:
        cmd.extend(["--output", str(output)])
    if no_clean:
        cmd.append("--no-clean")
    if archive is not None:
        cmd.extend(["--archive", str(archive)])
    _run_project_script("export_competition_package.py", cmd)


@app.command("competition-verify")
def competition_verify(
    package: Path = typer.Argument(
        Path("dist/competition_package"),
        help="Competition package directory or zip archive to verify.",
    ),
    fmt: str = typer.Option("text", "--format", "-f", help="Output format: text | json."),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write the verification report.",
    ),
) -> None:
    """Verify an exported competition package directory or zip archive."""

    cmd = [str(package), "--format", fmt]
    if output is not None:
        cmd.extend(["--output", str(output)])
    _run_project_script("verify_competition_package.py", cmd)


@app.command("competition-preflight")
def competition_preflight(
    template: str = typer.Option(
        "ai_learning_agents_systems",
        "--template",
        "-t",
        help="Course template id for the exported package.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory. Defaults to dist/competition_package.",
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Optional JSON readiness report path.",
    ),
    with_build: bool = typer.Option(
        False,
        "--with-build",
        help="Also run the web production build before exporting the package.",
    ),
    summary: Optional[Path] = typer.Option(
        None,
        "--summary",
        help="Optional path to write a concise Markdown readiness summary.",
    ),
    archive: Optional[Path] = typer.Option(
        None,
        "--archive",
        help="Optional zip archive path to create after exporting.",
    ),
    verify_report: Optional[Path] = typer.Option(
        None,
        "--verify-report",
        help="Optional JSON verification report for the final exported package or archive.",
    ),
) -> None:
    """Run readiness checks, optionally build the web UI, then export a competition package."""

    root = _repo_root()
    if summary is not None and report is None:
        report = _default_readiness_report()
    check_args = ["--format", "text"]
    if report is not None:
        check_args.extend(["--output", str(report)])
    check_result = subprocess.run(
        _project_script_cmd("check_competition_readiness.py", check_args),
        cwd=root,
        check=False,
    )
    if check_result.returncode != 0:
        raise typer.Exit(code=check_result.returncode)
    if summary is not None:
        _render_readiness_summary(report or _default_readiness_report(), summary)

    if with_build:
        console.print("[bold]Building web frontend before packaging...[/]")
        build_result = subprocess.run([_npm_command(), "run", "build"], cwd=root / "web", check=False)
        if build_result.returncode != 0:
            raise typer.Exit(code=build_result.returncode)

    package_args = ["--template", template]
    if output is not None:
        package_args.extend(["--output", str(output)])
    if archive is not None:
        package_args.extend(["--archive", str(archive)])
    package_result = subprocess.run(
        _project_script_cmd("export_competition_package.py", package_args),
        cwd=root,
        check=False,
    )
    if package_result.returncode != 0:
        raise typer.Exit(code=package_result.returncode)

    package_dir = output or _default_competition_package()
    _verify_competition_package(package_dir, report=verify_report if archive is None else None)
    if archive is not None:
        _verify_competition_package(archive, report=verify_report)
    if summary is not None and verify_report is not None:
        _append_package_verification_summary(summary, verify_report)
    raise typer.Exit(code=0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

