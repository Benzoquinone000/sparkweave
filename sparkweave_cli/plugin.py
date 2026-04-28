"""
CLI Plugin Command
==================

List and inspect registered plugins (tools, capabilities, playground).
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
import typer

console = Console()


def _discover_playground_plugins():
    try:
        from sparkweave.plugins.loader import discover_plugins
    except Exception:
        return []
    return discover_plugins()


def register(app: typer.Typer) -> None:

    @app.command("list")
    def plugin_list() -> None:
        """List all registered tools, capabilities, and playground plugins."""
        from sparkweave.app import get_capability_registry
        from sparkweave.tools.registry import get_tool_registry

        tr = get_tool_registry()
        cr = get_capability_registry()

        table = Table(title="Registered Plugins")
        table.add_column("Name", style="bold")
        table.add_column("Type")
        table.add_column("Description")

        for defn in tr.get_definitions():
            table.add_row(defn.name, "tool", defn.description[:80])

        for m in cr.get_manifests():
            table.add_row(m["name"], "capability", m["description"][:80])

        for manifest in _discover_playground_plugins():
            table.add_row(manifest.name, f"plugin:{manifest.type}", manifest.description[:80])

        console.print(table)

    @app.command("info")
    def plugin_info(name: str = typer.Argument(..., help="Tool, capability, or plugin name.")) -> None:
        """Show details of a tool, capability, or playground plugin."""
        import json

        from sparkweave.app import get_capability_registry
        from sparkweave.tools.registry import get_tool_registry

        tr = get_tool_registry()
        cr = get_capability_registry()

        tool = tr.get(name)
        if tool:
            defn = tool.get_definition()
            console.print_json(json.dumps(defn.to_openai_schema(), indent=2))
            return

        cap = cr.get_manifest(name)
        if cap:
            console.print_json(json.dumps(cap, indent=2))
            return

        for manifest in _discover_playground_plugins():
            if manifest.name == name:
                console.print_json(json.dumps(manifest.to_dict(), indent=2))
                return

        console.print(f"[red]'{name}' not found.[/]")
        raise typer.Exit(code=1)

