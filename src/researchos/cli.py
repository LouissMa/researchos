"""ResearchOS command-line interface."""

from __future__ import annotations

import contextlib
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from researchos.config import get_settings
from researchos.logging import setup_logging
from researchos.observability.events import Event, EventType
from researchos.persistence.db import init_db
from researchos.persistence.event_log import EventLog
from researchos.persistence.store import Store

# Windows consoles often default to a non-UTF-8 codepage (e.g. GBK); make output
# encoding-safe so rich never crashes on box-drawing or non-ASCII characters.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

app = typer.Typer(
    help="ResearchOS — an autonomous AI research operating system.", no_args_is_help=True
)
runs_app = typer.Typer(help="Inspect past runs.")
app.add_typer(runs_app, name="runs")
console = Console()

_ICONS = {
    EventType.RUN_STARTED: "[green]start[/green]",
    EventType.PLAN_CREATED: "[magenta]plan [/magenta]",
    EventType.TASK_STARTED: "[blue]task>[/blue]",
    EventType.TASK_FINISHED: "[green]done [/green]",
    EventType.AGENT_MESSAGE: "[dim]msg  [/dim]",
    EventType.TOOL_CALL: "[yellow]tool [/yellow]",
    EventType.PAPERS_FOUND: "[cyan]found[/cyan]",
    EventType.PAPERS_INGESTED: "[cyan]index[/cyan]",
    EventType.MEMORY_WRITE: "[cyan]mem  [/cyan]",
    EventType.ARTIFACT_SAVED: "[green]save [/green]",
    EventType.RUN_FINISHED: "[green]fin  [/green]",
    EventType.RUN_FAILED: "[red]fail [/red]",
}


@app.command()
def discover(
    query: str = typer.Argument(..., help="Research question or topic"),
    limit: int = typer.Option(20, help="Max papers to retrieve"),
    top_cards: int = typer.Option(5, help="How many key papers to deep-read"),
    project: str = typer.Option("default", help="Project id (memory namespace)"),
) -> None:
    """Run a literature-discovery workflow and print the resulting landscape."""
    # Import here so `--help` stays fast and avoids heavy deps until needed.
    from researchos.orchestration.orchestrator import SequentialOrchestrator

    settings = get_settings()
    setup_logging(settings.log_level)
    console.rule("[bold]ResearchOS · discover[/bold]")
    console.print(f"[dim]goal:[/dim] {query}\n")

    def on_event(ev: Event) -> None:
        icon = _ICONS.get(ev.type, "[dim]-    [/dim]")
        text = ev.payload.get("text") or ev.payload.get("output") or ""
        detail = (
            f" [dim]{text}[/dim]" if text else f" [dim]{ev.payload}[/dim]" if ev.payload else ""
        )
        console.print(f"{icon} [cyan]{ev.actor}[/cyan] {ev.type.value}{detail}")

    orch = SequentialOrchestrator(settings)
    state = orch.start_run(project, query, limit=limit, top_cards=top_cards, on_event=on_event)

    ls = state.landscape
    console.print()
    if ls and ls.summary:
        console.print(Panel(ls.summary, title="Research landscape", border_style="green"))
    if ls and ls.reading_order:
        table = Table(title="Recommended reading order", show_lines=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Paper")
        table.add_column("Year", justify="right")
        for i, pid in enumerate(ls.reading_order[:15], 1):
            p = state.papers.get(pid)
            if p:
                star = "* " if pid in ls.key_papers else ""
                table.add_row(str(i), f"{star}{p.title}", str(p.year or "-"))
        console.print(table)
    console.print(
        f"\n[green]✓[/green] run [bold]{state.run_id}[/bold] · "
        f"{len(state.papers)} papers · {len(state.clusters)} themes"
    )
    console.print(f"[dim]report: {settings.artifacts_dir / (state.run_id + '.md')}[/dim]")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the FastAPI service (interactive docs at /docs)."""
    import uvicorn

    console.print(f"[green]ResearchOS API[/green] → http://{host}:{port}/docs")
    uvicorn.run("researchos.api.app:app", host=host, port=port, reload=False)


@runs_app.command("list")
def runs_list() -> None:
    """List past runs."""
    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    table = Table(title="Runs")
    table.add_column("run_id")
    table.add_column("project")
    table.add_column("status")
    table.add_column("goal")
    for r in Store().list_runs():
        table.add_row(r.id, r.project_id, r.status, r.goal[:60])
    console.print(table)


@runs_app.command("trace")
def runs_trace(run_id: str) -> None:
    """Print the full reasoning trace (event log) of a run."""
    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    rows = EventLog().list(run_id)
    if not rows:
        console.print(f"[red]No events for run {run_id}[/red]")
        raise typer.Exit(1)
    for r in rows:
        console.print(
            f"[dim]{r.ts:%H:%M:%S}[/dim] [cyan]{r.actor:>10}[/cyan] "
            f"[bold]{r.type}[/bold] [dim]{r.payload}[/dim]"
        )


if __name__ == "__main__":
    app()
