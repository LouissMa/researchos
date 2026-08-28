"""API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from researchos.api.dashboard import DASHBOARD_HTML
from researchos.api.schemas import (
    EventItem,
    GraphEdgeItem,
    GraphResponse,
    GraphVizEdge,
    GraphVizNode,
    GraphVizResponse,
    IdeaItem,
    KeyPaper,
    MemoryItem,
    PaperItem,
    RunRequest,
    RunResponse,
    RunSummary,
)
from researchos.memory.graph import SqliteGraphStore
from researchos.memory.manager import MemoryManager
from researchos.orchestration.orchestrator import SequentialOrchestrator
from researchos.persistence.event_log import EventLog
from researchos.persistence.store import Store

router = APIRouter()


def _orch(request: Request) -> SequentialOrchestrator:
    return request.app.state.orchestrator


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/projects/{project_id}/runs", response_model=RunResponse)
def create_run(project_id: str, body: RunRequest, request: Request) -> RunResponse:
    orch = _orch(request)
    state = orch.start_run(project_id, body.goal, limit=body.limit, top_cards=body.top_cards)
    ls = state.landscape
    key_papers = []
    if ls:
        for pid in ls.key_papers:
            p = state.papers.get(pid)
            if p:
                key_papers.append(KeyPaper(id=p.id, title=p.title, url=p.url))
    artifacts = Store().list_artifacts(state.run_id)
    return RunResponse(
        run_id=state.run_id,
        project_id=project_id,
        goal=state.goal,
        papers=len(state.papers),
        clusters=len(state.clusters),
        key_papers=key_papers,
        summary=ls.summary if ls else "",
        report_uri=artifacts[0].uri if artifacts else None,
    )


@router.get("/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    return [
        RunSummary(run_id=r.id, project_id=r.project_id, goal=r.goal, status=r.status)
        for r in Store().list_runs()
    ]


@router.get("/runs/{run_id}/events", response_model=list[EventItem])
def run_events(run_id: str) -> list[EventItem]:
    rows = EventLog().list(run_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No events for run")
    return [
        EventItem(ts=r.ts.isoformat(), actor=r.actor, type=r.type, payload=r.payload) for r in rows
    ]


@router.get("/projects/{project_id}/papers", response_model=list[PaperItem])
def list_papers(project_id: str) -> list[PaperItem]:
    return [
        PaperItem(id=p.id, title=p.title, source=p.source, url=p.url, published=p.published)
        for p in Store().list_papers(project_id)
    ]


@router.get("/projects/{project_id}/memory", response_model=list[MemoryItem])
def list_memory(project_id: str, kind: str | None = None) -> list[MemoryItem]:
    return [
        MemoryItem(
            ref_type=m.ref_type,
            ref_id=m.ref_id,
            content=m.content,
            salience=m.salience,
            pinned=m.pinned,
        )
        for m in MemoryManager().list_items(project_id, ref_type=kind)
    ]


@router.get("/projects/{project_id}/graph", response_model=GraphResponse)
def project_graph(project_id: str) -> GraphResponse:
    """Knowledge-graph (structural memory) stats + a sample of provenance-carrying edges."""
    store = SqliteGraphStore()
    stats = store.stats(project_id)
    sample_edges = [
        GraphEdgeItem(
            relation=e.relation,
            source=e.source_id,
            target=e.target_id,
            confidence=e.confidence,
            provenance=e.provenance,
        )
        for e in store.edges(project_id, limit=25)
    ]
    return GraphResponse(
        project_id=project_id,
        nodes=stats["nodes"],
        edges=stats["edges"],
        by_type=stats["by_type"],
        sample_edges=sample_edges,
    )


@router.get("/projects/{project_id}/graph/viz", response_model=GraphVizResponse)
def project_graph_viz(project_id: str) -> GraphVizResponse:
    """Full node/edge dump for client-side graph rendering (dashboard Graph tab)."""
    store = SqliteGraphStore()
    nodes = [
        GraphVizNode(id=n.id, label=n.label[:64], node_type=n.node_type)
        for n in store.nodes(project_id, limit=200)
    ]
    edges = [
        GraphVizEdge(source=e.source_id, target=e.target_id, relation=e.relation)
        for e in store.edges(project_id, limit=400)
        if any(e.source_id == n.id for n in nodes) and any(e.target_id == n.id for n in nodes)
    ]
    return GraphVizResponse(nodes=nodes, edges=edges)


@router.get("/projects/{project_id}/ideas", response_model=list[IdeaItem])
def list_ideas(project_id: str) -> list[IdeaItem]:
    """Grounded research proposals from the Idea agent."""
    return [
        IdeaItem(
            id=i.id,
            title=i.title,
            hypothesis=i.hypothesis,
            gap=i.gap,
            grounding=[str(g) for g in (i.grounding or [])],
            novelty=i.novelty,
            feasibility=i.feasibility,
            generated_by=i.generated_by,
        )
        for i in Store().list_ideas(project_id)
    ]
