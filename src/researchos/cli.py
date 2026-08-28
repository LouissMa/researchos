"""ResearchOS command-line interface."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

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
memory_app = typer.Typer(help="Inspect long-term memory.")
graph_app = typer.Typer(help="Inspect the knowledge graph (structural memory tier).")
app.add_typer(runs_app, name="runs")
app.add_typer(memory_app, name="memory")
app.add_typer(graph_app, name="graph")
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
    EventType.GRAPH_WRITE: "[magenta]graph[/magenta]",
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
    if state.review:
        rv = state.review
        console.print(f"\n[bold]Critic score:[/bold] {rv.score}/10 [dim]({rv.reviewed_by})[/dim]")
        if rv.missing_seminal:
            console.print("[yellow]Possibly missing seminal work:[/yellow]")
            for t in rv.missing_seminal:
                console.print(f"  - {t}")
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


@memory_app.command("list")
def memory_list(
    project: str = typer.Option("default", help="Project id"),
    kind: str = typer.Option(None, help="Filter: paper | concept | interest"),
) -> None:
    """List long-term memory items by salience."""
    from researchos.memory.manager import MemoryManager

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    table = Table(title=f"Memory · {project}")
    table.add_column("type")
    table.add_column("salience", justify="right")
    table.add_column("pinned", justify="center")
    table.add_column("content")
    for item in MemoryManager().list_items(project, ref_type=kind):
        table.add_row(
            item.ref_type, f"{item.salience:.3f}", "*" if item.pinned else "", item.content[:80]
        )
    console.print(table)


@memory_app.command("reflect")
def memory_reflect(project: str = typer.Option("default", help="Project id")) -> None:
    """Re-derive the interest profile from past runs."""
    from researchos.memory.manager import MemoryManager

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    profile = MemoryManager().reflect(project)
    console.print(f"[green]{profile}[/green]")


@graph_app.command("stats")
def graph_stats(project: str = typer.Option("default", help="Project id")) -> None:
    """Show knowledge-graph node/edge counts for a project."""
    from researchos.memory.graph import SqliteGraphStore

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    stats = SqliteGraphStore().stats(project)
    console.print(
        f"[green]Knowledge graph · {project}[/green]: "
        f"{stats['nodes']} nodes · {stats['edges']} edges"
    )
    for node_type, count in sorted(stats["by_type"].items()):
        console.print(f"  [dim]{node_type}:[/dim] {count}")


@graph_app.command("edges")
def graph_edges(
    project: str = typer.Option("default", help="Project id"),
    relation: str = typer.Option(None, help="Filter by relation, e.g. BELONGS_TO"),
) -> None:
    """List knowledge-graph edges with provenance + confidence."""
    from researchos.memory.graph import SqliteGraphStore

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    edges = SqliteGraphStore().edges(project, relation=relation)
    if not edges:
        console.print(f"[red]No edges for project {project}[/red]")
        raise typer.Exit(1)
    table = Table(title=f"Graph edges · {project}")
    table.add_column("relation")
    table.add_column("source")
    table.add_column("target")
    table.add_column("confidence", justify="right")
    table.add_column("provenance")
    for e in edges[:50]:
        prov = e.provenance.get("tool") or e.provenance.get("source_paper") or ""
        table.add_row(e.relation, e.source_id, e.target_id, f"{e.confidence:.2f}", prov)
    console.print(table)


@app.command()
def benchmark(
    strategy: str = typer.Option(None, help="Limit to one strategy: vector | graph | hybrid"),
) -> None:
    """Run the frozen offline retrieval benchmarks (benchmarks/scenarios.json).

    Evaluates recall@k and grounding for every retrieval strategy on each scenario.
    """
    import subprocess
    import sys

    script = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "run_eval.py"
    if not script.exists():
        console.print(f"[red]Benchmarks not found: {script}[/red]")
        raise typer.Exit(1)
    cmd = [sys.executable, "-m", "benchmarks.run_eval"]
    if strategy:
        cmd.extend(["--strategy", strategy])
    # -m needs the repository root (where the benchmarks package lives) on sys.path.
    raise typer.Exit(subprocess.call(cmd, cwd=str(script.parent.parent)))


if __name__ == "__main__":
    app()
