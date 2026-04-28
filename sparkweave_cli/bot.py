"""
CLI commands for managing SparkBot instances.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.table import Table
import typer

console = Console()


def register(app: typer.Typer) -> None:

    @app.command("list")
    def bot_list() -> None:
        """List all SparkBot instances."""
        from sparkweave.services.sparkbot import get_sparkbot_manager

        bots = get_sparkbot_manager().list_bots()
        if not bots:
            console.print("[dim]No SparkBots configured.[/]")
            return

        table = Table(title="SparkBots")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Model", style="dim")
        table.add_column("Channels", style="dim")

        for b in bots:
            status = "[green]running[/]" if b.get("running") else "[dim]stopped[/]"
            table.add_row(
                b["bot_id"],
                b.get("name", ""),
                status,
                b.get("model") or "(default)",
                ", ".join(b.get("channels", [])) or "-",
            )
        console.print(table)

    @app.command("start")
    def bot_start(
        name: str = typer.Argument(..., help="Bot ID to start."),
    ) -> None:
        """Start a SparkBot instance."""
        from sparkweave.services.sparkbot import get_sparkbot_manager

        mgr = get_sparkbot_manager()
        try:
            instance = asyncio.get_event_loop().run_until_complete(mgr.start_bot(name))
            console.print(f"[green]Started SparkBot '{instance.config.name}' ({name})[/]")
        except RuntimeError as e:
            console.print(f"[red]Failed to start: {e}[/]")
            raise typer.Exit(1)

    @app.command("stop")
    def bot_stop(
        name: str = typer.Argument(..., help="Bot ID to stop."),
    ) -> None:
        """Stop a running SparkBot instance."""
        from sparkweave.services.sparkbot import get_sparkbot_manager

        mgr = get_sparkbot_manager()
        stopped = asyncio.get_event_loop().run_until_complete(mgr.stop_bot(name))
        if stopped:
            console.print(f"[green]Stopped SparkBot '{name}'[/]")
        else:
            console.print(f"[yellow]Bot '{name}' not found or not running.[/]")

    @app.command("create")
    def bot_create(
        name: str = typer.Argument(..., help="Bot ID."),
        display_name: str = typer.Option("", "--name", "-n", help="Display name."),
        persona: str = typer.Option("", "--persona", "-p", help="Persona description."),
        model: str = typer.Option("", "--model", "-m", help="Model override."),
    ) -> None:
        """Create a new SparkBot configuration and start it."""
        from sparkweave.services.sparkbot import BotConfig, get_sparkbot_manager

        config = BotConfig(
            name=display_name or name,
            persona=persona,
            model=model or None,
        )
        mgr = get_sparkbot_manager()
        try:
            instance = asyncio.get_event_loop().run_until_complete(
                mgr.start_bot(name, config)
            )
            console.print(f"[green]Created and started SparkBot '{instance.config.name}' ({name})[/]")
        except RuntimeError as e:
            console.print(f"[red]Failed: {e}[/]")
            raise typer.Exit(1)

