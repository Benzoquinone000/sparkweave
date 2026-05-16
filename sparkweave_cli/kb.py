"""CLI commands for SparkWeave knowledge bases."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
import typer

from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.knowledge.reindex import reindex_knowledge_base
from sparkweave.services.paths import get_path_service
from sparkweave.services.rag import rag_search
from sparkweave.services.rag_support.diagnostics import diagnose_rag, preflight_rag_environment
from sparkweave.services.rag_support.evaluation import (
    STRATEGY_PRESETS,
    load_cases,
    parse_strategy,
    run_evaluation_sync,
    strategies_for_preset,
    write_report_json,
    write_report_markdown,
)
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER, normalize_provider_name
from sparkweave.services.rag_support.file_routing import FileTypeRouter

console = Console()


def _get_kb_manager() -> KnowledgeBaseManager:
    """Return a KnowledgeBaseManager rooted at the canonical project-level KB directory."""
    base_dir = get_path_service().project_root / "data" / "knowledge_bases"
    return KnowledgeBaseManager(base_dir=str(base_dir))


def _collect_documents(docs: list[str], docs_dir: Optional[str]) -> list[str]:
    """Collect and de-duplicate document files from explicit paths and a directory."""
    candidates: list[Path] = []

    for doc in docs:
        path = Path(doc).expanduser().resolve()
        if path.exists() and path.is_file():
            candidates.append(path)

    if docs_dir:
        base = Path(docs_dir).expanduser().resolve()
        if not base.exists() or not base.is_dir():
            raise typer.BadParameter(f"docs directory does not exist: {base}")
        for pattern in FileTypeRouter.get_glob_patterns():
            candidates.extend(path for path in base.rglob(pattern) if path.is_file())

    unique: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)

    return unique


def register(app: typer.Typer) -> None:
    @app.command("list")
    def kb_list(
        fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
    ) -> None:
        """List all knowledge bases."""
        mgr = _get_kb_manager()
        kb_names = mgr.list_knowledge_bases()
        if not kb_names:
            if fmt == "json":
                console.print_json("[]")
            else:
                console.print("[dim]No knowledge bases found.[/]")
            return

        if fmt == "json":
            items = []
            for name in kb_names:
                info = mgr.get_info(name)
                stats = info.get("statistics", {})
                metadata = info.get("metadata", {})
                items.append({
                    "name": name,
                    "status": info.get("status", "unknown"),
                    "documents": stats.get("raw_documents", 0),
                    "rag_provider": metadata.get("rag_provider", stats.get("rag_provider", DEFAULT_PROVIDER)),
                    "is_default": bool(info.get("is_default")),
                })
            console.print_json(json.dumps(items, ensure_ascii=False, default=str))
            return

        table = Table(title="Knowledge Bases")
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Documents", justify="right")
        table.add_column("RAG Provider")
        table.add_column("Default")

        for name in kb_names:
            info = mgr.get_info(name)
            stats = info.get("statistics", {})
            metadata = info.get("metadata", {})
            table.add_row(
                name,
                str(info.get("status", "unknown")),
                str(stats.get("raw_documents", 0)),
                str(metadata.get("rag_provider", stats.get("rag_provider", DEFAULT_PROVIDER))),
                "yes" if info.get("is_default") else "",
            )

        console.print(table)

    @app.command("info")
    def kb_info(name: str = typer.Argument(..., help="Knowledge base name.")) -> None:
        """Show details of a knowledge base."""
        mgr = _get_kb_manager()
        try:
            info = mgr.get_info(name)
        except Exception as exc:
            console.print(f"[red]Knowledge base '{name}' not found: {exc}[/]")
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(info, indent=2, ensure_ascii=False, default=str))

    @app.command("doctor")
    def kb_doctor(
        name: Optional[str] = typer.Argument(None, help="Optional knowledge base name."),
        fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
        no_connect: bool = typer.Option(False, "--no-connect", help="Skip Milvus connection check."),
    ) -> None:
        """Inspect RAG provider, Milvus connectivity, and collection markers."""
        mgr = _get_kb_manager()
        if name and name not in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' not found.[/]")
            raise typer.Exit(code=1)

        report = diagnose_rag(
            kb_base_dir=mgr.base_dir,
            kb_name=name,
            check_connection=not no_connect,
        )
        if fmt == "json":
            console.print_json(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            return

        table = Table(title=f"RAG Diagnostics{f' · {name}' if name else ''}")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Message")
        for check in report.get("checks", []):
            table.add_row(
                str(check.get("name") or "-"),
                str(check.get("status") or "-"),
                str(check.get("message") or "-"),
            )
        console.print(f"[bold]Provider:[/] {report.get('provider')}")
        console.print(f"[bold]URI:[/] {report.get('uri') or '-'}")
        if report.get("collection_name"):
            console.print(f"[bold]Collection:[/] {report.get('collection_name')}")
        console.print(table)

    @app.command("preflight")
    def kb_preflight(
        name: Optional[str] = typer.Argument(None, help="Optional knowledge base name."),
        fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
        no_connect: bool = typer.Option(False, "--no-connect", help="Skip Milvus connection check."),
        no_docker: bool = typer.Option(False, "--no-docker", help="Skip Docker availability check."),
    ) -> None:
        """Run an operator-focused RAG preflight before rebuilding or E2E testing."""
        mgr = _get_kb_manager()
        if name and name not in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' not found.[/]")
            raise typer.Exit(code=1)

        report = preflight_rag_environment(
            kb_base_dir=mgr.base_dir,
            kb_name=name,
            check_connection=not no_connect,
            check_docker=not no_docker,
        )
        if fmt == "json":
            console.print_json(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            return

        console.print(f"[bold]RAG preflight:[/] {report.get('label')}")
        if report.get("summary"):
            console.print(str(report.get("summary")))
        if report.get("primary_action"):
            console.print(f"[bold]Next:[/] {report.get('primary_action')}")

        diagnostic = report.get("diagnostic") if isinstance(report.get("diagnostic"), dict) else {}
        docker = report.get("docker") if isinstance(report.get("docker"), dict) else {}
        table = Table(title="Runtime")
        table.add_column("Item")
        table.add_column("Value")
        table.add_row("Milvus URI", str(diagnostic.get("uri") or "-"))
        table.add_row("Indexed URI", str(diagnostic.get("indexed_uri") or "-"))
        table.add_row("Connection", str(diagnostic.get("connection_error_kind") or diagnostic.get("status") or "-"))
        table.add_row("Docker", "running" if docker.get("docker_running") else str(docker.get("error") or "not running"))
        console.print(table)

        commands = [str(item) for item in report.get("recommended_commands") or []]
        if commands:
            console.print("[bold]Recommended commands:[/]")
            for command in commands:
                console.print(f"  {command}")

    @app.command("audit")
    def kb_audit(
        prune_missing: bool = typer.Option(
            False,
            "--prune-missing",
            help="Remove config entries whose knowledge-base directory is missing.",
        ),
        dry_run: bool = typer.Option(
            True,
            "--dry-run/--apply",
            help="Preview by default. Use --apply with --prune-missing to write changes.",
        ),
        fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
    ) -> None:
        """Audit the knowledge-base registry and optionally prune stale entries."""
        mgr = _get_kb_manager()
        report = (
            mgr.prune_missing_configs(dry_run=dry_run)
            if prune_missing
            else mgr.audit_registry()
        )
        if fmt == "json":
            console.print_json(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            return

        audit = report.get("audit", report)
        table = Table(title="Knowledge Base Registry Audit")
        table.add_column("State")
        table.add_column("Count", justify="right")
        table.add_row("Available", str(audit.get("available_count", 0)))
        table.add_row("Missing config entries", str(audit.get("missing_count", 0)))
        table.add_row("Discovered unregistered dirs", str(audit.get("discovered_count", 0)))
        console.print(table)

        missing = audit.get("missing") or []
        if missing:
            console.print("[yellow]Missing entries:[/]")
            for item in missing:
                console.print(f"  - {item.get('name')} -> {item.get('path')}")

        if prune_missing:
            removed = report.get("removed") or []
            if report.get("dry_run"):
                console.print("[dim]Dry run only. Use --apply to write cleanup changes.[/]")
            elif removed:
                console.print(f"[green]Removed {len(removed)} stale config entries: {', '.join(removed)}[/]")
            else:
                console.print("[green]No stale config entries needed removal.[/]")

    @app.command("set-default")
    def kb_set_default(name: str = typer.Argument(..., help="Knowledge base name.")) -> None:
        """Set the default knowledge base."""
        mgr = _get_kb_manager()
        try:
            mgr.set_default(name)
        except Exception as exc:
            console.print(f"[red]Failed to set default KB '{name}': {exc}[/]")
            raise typer.Exit(code=1) from exc
        console.print(f"[green]Set '{name}' as default knowledge base.[/]")

    @app.command("create")
    def kb_create(
        name: str = typer.Argument(..., help="New KB name."),
        docs: list[str] = typer.Option([], "--doc", "-d", help="Document paths."),
        docs_dir: Optional[str] = typer.Option(None, "--docs-dir", help="Directory of documents."),
    ) -> None:
        """Initialize a new knowledge base from documents."""
        mgr = _get_kb_manager()
        if name in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' already exists.[/]")
            raise typer.Exit(code=1)

        try:
            doc_paths = _collect_documents(docs, docs_dir)
        except typer.BadParameter as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1) from exc

        if not doc_paths:
            console.print("[red]Provide at least one supported document (--doc or --docs-dir).[/]")
            raise typer.Exit(code=1)

        console.print(
            f"Creating KB [bold]{name}[/] with {len(doc_paths)} document(s) via [bold]{DEFAULT_PROVIDER}[/]..."
        )
        from sparkweave.knowledge.initializer import initialize_knowledge_base

        try:
            asyncio.run(
                initialize_knowledge_base(
                    kb_name=name,
                    source_files=doc_paths,
                    base_dir=str(mgr.base_dir),
                )
            )
        except Exception as exc:
            console.print(f"[red]KB creation failed: {exc}[/]")
            raise typer.Exit(code=1) from exc
        console.print("[green]Knowledge base created successfully.[/]")

    @app.command("add")
    def kb_add(
        name: str = typer.Argument(..., help="KB name."),
        docs: list[str] = typer.Option([], "--doc", "-d", help="Document paths to add."),
        docs_dir: Optional[str] = typer.Option(None, "--docs-dir", help="Directory of documents."),
    ) -> None:
        """Add documents to an existing knowledge base."""
        mgr = _get_kb_manager()
        if name not in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' not found.[/]")
            raise typer.Exit(code=1)

        try:
            doc_paths = _collect_documents(docs, docs_dir)
        except typer.BadParameter as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1) from exc

        if not doc_paths:
            console.print("[red]Provide at least one supported document.[/]")
            raise typer.Exit(code=1)

        console.print(f"Adding {len(doc_paths)} document(s) to [bold]{name}[/]...")
        from sparkweave.knowledge.add_documents import add_documents

        try:
            processed_count = asyncio.run(
                add_documents(
                    kb_name=name,
                    source_files=doc_paths,
                    base_dir=str(mgr.base_dir),
                    allow_duplicates=False,
                )
            )
        except Exception as exc:
            console.print(f"[red]Document upload failed: {exc}[/]")
            raise typer.Exit(code=1) from exc

        if processed_count:
            console.print(f"[green]Done. Indexed {processed_count} document(s).[/]")
        else:
            console.print("[yellow]No new unique documents were indexed.[/]")

    @app.command("reindex")
    def kb_reindex(
        name: str = typer.Argument(..., help="KB name."),
        provider: Optional[str] = typer.Option(None, "--provider", "-p", help="RAG provider: milvus | llamaindex."),
        no_backup: bool = typer.Option(False, "--no-backup", help="Skip local index backup before rebuilding."),
    ) -> None:
        """Rebuild a knowledge-base index from its raw files."""
        mgr = _get_kb_manager()
        if name not in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' not found.[/]")
            raise typer.Exit(code=1)

        selected_provider = normalize_provider_name(provider or DEFAULT_PROVIDER)
        console.print(
            f"Rebuilding [bold]{name}[/] with [bold]{selected_provider}[/]. "
            "Raw files stay in place."
        )
        try:
            rebuilt = asyncio.run(
                reindex_knowledge_base(
                    kb_name=name,
                    base_dir=str(mgr.base_dir),
                    rag_provider=selected_provider,
                    backup=not no_backup,
                )
            )
        except Exception as exc:
            console.print(f"[red]Reindex failed: {exc}[/]")
            raise typer.Exit(code=1) from exc
        console.print(f"[green]Done. Rebuilt index from {rebuilt} raw file(s).[/]")

    @app.command("delete")
    def kb_delete(
        name: str = typer.Argument(..., help="KB name."),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
    ) -> None:
        """Delete a knowledge base."""
        if not force:
            confirm = typer.confirm(f"Delete knowledge base '{name}'?")
            if not confirm:
                raise typer.Abort()

        mgr = _get_kb_manager()
        try:
            deleted = mgr.delete_knowledge_base(name, confirm=True)
        except Exception as exc:
            console.print(f"[red]Failed to delete '{name}': {exc}[/]")
            raise typer.Exit(code=1) from exc

        if deleted:
            console.print(f"[green]Deleted '{name}'.[/]")
        else:
            console.print(f"[yellow]Knowledge base '{name}' was not deleted.[/]")

    @app.command("search")
    def kb_search(
        name: str = typer.Argument(..., help="KB name."),
        query: str = typer.Argument(..., help="Search query."),
        mode: str = typer.Option("hybrid", help="Search mode."),
        fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
    ) -> None:
        """Search a knowledge base."""
        mgr = _get_kb_manager()
        if name not in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' not found.[/]")
            raise typer.Exit(code=1)

        try:
            result = asyncio.run(
                rag_search(
                    query=query,
                    kb_name=name,
                    mode=mode,
                    kb_base_dir=str(mgr.base_dir),
                )
            )
        except Exception as exc:
            console.print(f"[red]Search failed: {exc}[/]")
            raise typer.Exit(code=1) from exc

        if fmt == "json":
            console.print_json(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            return

        answer = result.get("answer") or result.get("content", "")
        provider = result.get("provider", DEFAULT_PROVIDER)
        console.print(f"[bold]Provider:[/] {provider}")
        console.print(f"[bold]Answer:[/]\n{answer}")

    @app.command("eval")
    def kb_eval(
        name: str = typer.Argument(..., help="KB name."),
        dataset: Path = typer.Argument(..., help="JSONL RAG evaluation dataset."),
        provider: Optional[str] = typer.Option(None, "--provider", "-p", help="RAG provider: milvus | llamaindex."),
        strategy: list[str] = typer.Option(
            [],
            "--strategy",
            "-s",
            help="Strategy definition, e.g. baseline:top_k=5,max_context_chars=8000",
        ),
        output: Path = typer.Option(
            Path("dist/rag-eval-report.md"),
            "--output",
            help="Markdown report path.",
        ),
        json_output: Path = typer.Option(
            Path("dist/rag-eval-report.json"),
            "--json-output",
            help="JSON report path.",
        ),
        baseline_strategy: str = typer.Option("baseline", "--baseline-strategy", help="Baseline strategy name."),
        preset: str = typer.Option(
            "default",
            "--preset",
            help=f"Built-in strategy preset when --strategy is omitted: {', '.join(sorted(STRATEGY_PRESETS))}.",
        ),
        fmt: str = typer.Option("rich", "--format", "-f", help="Output format: rich | json."),
    ) -> None:
        """Evaluate retrieval quality for a knowledge base with a JSONL dataset."""
        mgr = _get_kb_manager()
        if name not in mgr.list_knowledge_bases():
            console.print(f"[red]Knowledge base '{name}' not found.[/]")
            raise typer.Exit(code=1)
        if not dataset.exists():
            console.print(f"[red]Dataset not found: {dataset}[/]")
            raise typer.Exit(code=1)

        try:
            cases = load_cases(dataset)
            strategies = [parse_strategy(item) for item in strategy] if strategy else strategies_for_preset(preset)
            kb_entry = mgr._load_config().get("knowledge_bases", {}).get(name, {})
            selected_provider = normalize_provider_name(provider or kb_entry.get("rag_provider") or DEFAULT_PROVIDER)
            report = run_evaluation_sync(
                cases=cases,
                strategies=strategies,
                default_kb=name,
                default_provider=selected_provider,
                baseline_strategy=baseline_strategy,
            )
            write_report_markdown(output, report)
            write_report_json(json_output, report)
        except Exception as exc:
            console.print(f"[red]RAG evaluation failed: {exc}[/]")
            raise typer.Exit(code=1) from exc

        if fmt == "json":
            console.print_json(json.dumps(report, ensure_ascii=False, default=str))
            return

        table = Table(title=f"RAG Evaluation - {name}")
        table.add_column("Strategy", style="bold")
        table.add_column("Cases", justify="right")
        table.add_column("Success", justify="right")
        table.add_column("Keyword Recall", justify="right")
        table.add_column("Source Hit", justify="right")
        table.add_column("P95 Latency", justify="right")
        for row in report.get("summary", []):
            table.add_row(
                str(row.get("strategy") or "-"),
                _metric_cell(row.get("cases")),
                _metric_cell(row.get("success_rate")),
                _metric_cell(row.get("keyword_recall")),
                _metric_cell(row.get("source_hit_rate")),
                _metric_cell(row.get("p95_latency_ms")),
            )
        console.print(table)
        profile = report.get("dataset_profile")
        if isinstance(profile, dict):
            console.print(
                "[bold]Dataset:[/] "
                f"{profile.get('label_status_label') or '-'} - {profile.get('headline') or '-'}"
            )
        console.print(f"[green]Wrote {output}[/]")
        console.print(f"[green]Wrote {json_output}[/]")


def _metric_cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)

