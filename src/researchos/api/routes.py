"""API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from researchos.api.schemas import (
    EventItem,
    KeyPaper,
    PaperItem,
    RunRequest,
    RunResponse,
    RunSummary,
)
from researchos.orchestration.orchestrator import SequentialOrchestrator
from researchos.persistence.event_log import EventLog
from researchos.persistence.store import Store

router = APIRouter()


def _orch(request: Request) -> SequentialOrchestrator:
    return request.app.state.orchestrator


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
