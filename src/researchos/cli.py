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
    EventType.IDEAS_GENERATED: "[yellow]idea [/yellow]",
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


@graph_app.command("analytics")
def graph_analytics(project: str = typer.Option("default", help="Project id")) -> None:
    """Graph analytics: degree centrality (seminal candidates) + communities."""
    from researchos.memory.graph import SqliteGraphStore

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    store = SqliteGraphStore()
    stats = store.stats(project)
    console.print(
        f"[green]Graph analytics · {project}[/green]: {stats['nodes']} nodes, "
        f"{stats['edges']} edges"
    )

    labels = {n.id: f"[{n.node_type}] {n.label[:48]}" for n in store.nodes(project, limit=500)}
    top = store.centrality(project, limit=8)
    if top:
        console.print("\n[bold]Most connected (seminal candidates):[/bold]")
        for nid, degree, _norm in top:
            console.print(f"  {degree:>3} links · {labels.get(nid, nid)}")
    comps = [c for c in store.components(project) if len(c) > 1]
    if comps:
        console.print("\n[bold]Communities (connected components):[/bold]")
        for comp in comps[:6]:
            shown = ", ".join(labels.get(n, n) for n in comp[:4])
            more = f" … +{len(comp) - 4}" if len(comp) > 4 else ""
            console.print(f"  [{len(comp):>3}] {shown}{more}")


ideas_app = typer.Typer(help="Inspect research proposals (Idea agent).")
app.add_typer(ideas_app, name="ideas")


@ideas_app.command("list")
def ideas_list(
    project: str = typer.Option("default", help="Project id"),
    limit: int = typer.Option(20, help="Max ideas to show"),
) -> None:
    """List grounded research proposals from past runs."""
    from researchos.persistence.store import Store

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    ideas = Store().list_ideas(project, limit=limit)
    if not ideas:
        console.print(f"[red]No ideas for project {project}[/red]")
        raise typer.Exit(1)
    for idea in ideas:
        console.print(f"\n[bold]{idea.title}[/bold] [dim]({idea.generated_by})[/dim]")
        console.print(f"  novelty {idea.novelty:.2f} · feasibility {idea.feasibility:.2f}")
        if idea.hypothesis:
            console.print(f"  [dim]hypothesis:[/dim] {idea.hypothesis[:160]}")
        if idea.grounding:
            console.print(f"  [dim]grounded in:[/dim] {', '.join(idea.grounding[:6])}")


@app.command()
def review(
    paper_id: str = typer.Argument(..., help="Paper id from a previous run"),
    project: str = typer.Option("default", help="Project id (context corpus)"),
) -> None:
    """Review a paper's research card: strengths / weaknesses / novelty / score."""
    from researchos.agents.knowledge import heuristic_card
    from researchos.agents.reviewer import Reviewer
    from researchos.core.models import Paper
    from researchos.llm.client import get_llm
    from researchos.persistence.store import Store

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    store = Store()
    rows = store.list_papers(project, limit=500)
    target = next((r for r in rows if r.id == paper_id), None)
    if target is None:
        console.print(f"[red]Paper {paper_id} not found in project {project}[/red]")
        raise typer.Exit(1)
    paper = Paper(
        id=target.id,
        source=target.source,
        source_id=target.source_id,
        title=target.title,
        abstract=target.abstract,
        url=target.url,
    )
    context = [
        Paper(
            id=r.id,
            source=r.source,
            source_id=r.source_id,
            title=r.title,
            abstract=r.abstract,
            url=r.url,
        )
        for r in rows
    ]
    result = Reviewer(get_llm(settings)).review(paper, heuristic_card(paper), context)
    panel = Panel(
        f"[bold]{paper.title}[/bold]\n\n"
        f"score: [bold]{result.score:.1f}/10[/bold] · "
        f"novelty {result.novelty:.2f} · feasibility {result.feasibility:.2f} · "
        f"[dim]{result.reviewed_by}[/dim]" + ("\n\n" + result.summary if result.summary else ""),
        title="Paper review",
        border_style="yellow",
    )
    console.print(panel)
    if result.strengths:
        console.print("\n[green]Strengths:[/green]")
        for s in result.strengths:
            console.print(f"  + {s}")
    if result.weaknesses:
        console.print("\n[red]Weaknesses:[/red]")
        for w in result.weaknesses:
            console.print(f"  - {w}")


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


experiment_app = typer.Typer(
    help="Experiment planning & assisted reproduction (Phase 4, human-in-the-loop)."
)
app.add_typer(experiment_app, name="experiment")


@experiment_app.command("plan")
def experiment_plan(
    paper_id: str = typer.Argument(..., help="Paper id from a previous run"),
    project: str = typer.Option("default", help="Project id"),
) -> None:
    """Generate a reproduction plan from the paper's research card."""
    from researchos.agents.experiment import ExperimentAgent
    from researchos.agents.knowledge import heuristic_card
    from researchos.core.models import Paper
    from researchos.llm.client import get_llm
    from researchos.persistence.models import ExperimentRow
    from researchos.persistence.store import Store

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    store = Store()
    rows = store.list_papers(project, limit=500)
    target = next((r for r in rows if r.id == paper_id), None)
    if target is None:
        console.print(f"[red]Paper {paper_id} not found in project {project}[/red]")
        raise typer.Exit(1)
    paper = Paper(
        id=target.id,
        source=target.source,
        source_id=target.source_id,
        title=target.title,
        abstract=target.abstract,
        url=target.url,
    )
    plan = ExperimentAgent(get_llm(settings)).plan(paper, heuristic_card(paper))
    store.upsert_experiment(
        ExperimentRow(
            id=plan.id,
            project_id=project,
            paper_id=paper_id,
            title=plan.title,
            plan=plan.model_dump(),
            status="planned",
            baseline=plan.baseline,
        )
    )
    console.print(
        Panel(
            f"[bold]{plan.title}[/bold] · [dim]{plan.generated_by}[/dim]",
            title="Experiment plan",
            border_style="cyan",
        )
    )
    for i, step in enumerate(plan.steps, 1):
        console.print(f"  {i}. {step}")
    if plan.commands:
        console.print("\n[bold]Commands (human-edit before running):[/bold]")
        for c in plan.commands:
            console.print(f"  [dim]$[/dim] {c}")
    if plan.baseline:
        console.print(f"\n[bold]Baseline claim:[/bold] {plan.baseline[:200]}")
    console.print(
        f"\n[dim]plan id: {plan.id} → run with: researchos experiment run {plan.id}[/dim]"
    )


@experiment_app.command("run")
def experiment_run(
    experiment_id: str = typer.Argument(..., help="Plan/experiment id"),
    command: str = typer.Option(None, help="Command to run (default: plan's first command)"),
    yes: bool = typer.Option(False, help="Approve execution (bypasses the confirmation prompt)"),
    project: str = typer.Option("default", help="Project id"),
) -> None:
    """Run a planned command in the sandbox — approval required (--yes or prompt)."""
    from researchos.agents.experiment import baseline_match
    from researchos.core.models import ExperimentPlan
    from researchos.persistence.models import ExperimentRow
    from researchos.persistence.store import Store
    from researchos.tools.python_exec import PythonExecTool

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    store = Store()
    row = store.get_experiment(experiment_id)
    if row is None:
        console.print(f"[red]Unknown experiment {experiment_id} — plan it first.[/red]")
        raise typer.Exit(1)
    plan = ExperimentPlan(**row.plan)
    cmd = command or (plan.commands[0] if plan.commands else None)
    if not cmd:
        console.print("[red]No command to run — provide --command or a plan with commands.[/red]")
        raise typer.Exit(1)

    approved = yes or settings.experiment_allow_exec
    if not approved:
        approved = typer.confirm(f"Run in sandbox: [bold]{cmd}[/bold]?")
    if not approved:
        console.print("[yellow]Aborted — command not run.[/yellow]")
        raise typer.Exit(1)

    workdir = settings.experiment_dir / project / experiment_id
    tool = PythonExecTool(
        workdir,
        timeout_s=settings.experiment_timeout_s,
        allow_exec=True,  # approval already granted by the caller
    )
    result = tool.invoke(command=cmd, approved=True)
    data = result.data or {}
    output = str(data.get("output", ""))
    matched = baseline_match(plan.baseline, output)
    status = "ok" if result.ok else "failed"
    store.upsert_experiment(
        ExperimentRow(
            id=experiment_id,
            project_id=project,
            paper_id=row.paper_id,
            title=row.title,
            plan=row.plan,
            command=cmd,
            status=status,
            output=output,
            exit_code=data.get("exit_code"),
            duration_ms=int(data.get("duration_ms", 0)),
            baseline=plan.baseline,
            baseline_matched=matched,
        )
    )

    icon = "[green]ok[/green]" if result.ok else "[red]failed[/red]"
    console.print(
        f"\nexperiment {experiment_id} · {icon} · exit {data.get('exit_code')} · "
        f"{data.get('duration_ms')}ms"
    )
    tail = "\n".join(output.splitlines()[-12:])
    if tail:
        console.print(Panel(tail, title="output (tail)", border_style="dim"))
    if plan.baseline:
        verdict = {
            True: "[green]matches baseline claim[/green]",
            False: "[yellow]does NOT match baseline — review[/yellow]",
            None: "[dim]baseline not comparable (no claim)[/dim]",
        }[matched]
        console.print(f"baseline: {verdict}")
        console.print(f"[dim]claimed:[/dim] {plan.baseline[:160]}")


@experiment_app.command("list")
def experiment_list(
    project: str = typer.Option("default", help="Project id"),
    limit: int = typer.Option(20, help="Max experiments to show"),
) -> None:
    """List tracked experiments (plans and runs)."""
    from researchos.persistence.store import Store

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    rows = Store().list_experiments(project, limit=limit)
    if not rows:
        console.print(f"[red]No experiments for project {project}[/red]")
        raise typer.Exit(1)
    table = Table(title=f"Experiments · {project}")
    table.add_column("id")
    table.add_column("status")
    table.add_column("exit")
    table.add_column("ms")
    table.add_column("baseline")
    table.add_column("title")
    for r in rows:
        match = {True: "✓", False: "✗", None: "-"}.get(r.baseline_matched, "-")
        table.add_row(
            r.id[:12],
            r.status,
            str(r.exit_code if r.exit_code is not None else "-"),
            str(r.duration_ms),
            match,
            r.title[:44],
        )
    console.print(table)


writing_app = typer.Typer(help="LaTeX drafting & consistency checks (Phase 5).")
app.add_typer(writing_app, name="write")


@writing_app.command("draft")
def write_draft(
    project: str = typer.Option("default", help="Project id"),
    run_id: str = typer.Option(None, help="Optional run id to attribute the draft"),
) -> None:
    """Generate a related-work LaTeX draft grounded in the project's knowledge graph."""
    from researchos.agents.writing import WritingAgent
    from researchos.llm.client import get_llm

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    draft = WritingAgent(get_llm(settings)).draft(project, run_id=run_id)

    artifact_uri = settings.artifacts_dir / f"draft-{project}.tex"
    artifact_uri.write_text(draft.tex, encoding="utf-8")
    Store().add_artifact(project, run_id or "writing", "latex_draft", str(artifact_uri))

    console.print(
        Panel(
            f"[bold]{len(draft.sections)} sections[/bold] · "
            f"{len(draft.citations)} citations · [dim]{draft.generated_by}[/dim]",
            title=f"LaTeX draft · {project}",
            border_style="magenta",
        )
    )
    console.print(f"[dim]saved: {artifact_uri}[/dim]")
    if draft.inconsistencies:
        console.print("\n[yellow]Consistency issues:[/yellow]")
        for issue in draft.inconsistencies:
            console.print(f"  - {issue}")
    else:
        console.print("\n[green]Consistency check passed — every citation resolves.[/green]")


@writing_app.command("check")
def write_check(
    project: str = typer.Option("default", help="Project id"),
) -> None:
    """Verify that a draft's citations all resolve to bibliography entries."""
    from researchos.agents.writing import WritingAgent
    from researchos.llm.client import get_llm

    settings = get_settings()
    settings.ensure_dirs()
    init_db(settings.db_path)
    draft = WritingAgent(get_llm(settings)).draft(project)
    if draft.inconsistencies:
        console.print(f"[red]{len(draft.inconsistencies)} consistency issue(s):[/red]")
        for issue in draft.inconsistencies:
            console.print(f"  - {issue}")
        raise typer.Exit(1)
    console.print("[green]All citations resolve — no dangling references.[/green]")


if __name__ == "__main__":
    app()
