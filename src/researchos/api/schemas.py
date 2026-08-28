"""API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    goal: str = Field(..., description="The research question or topic")
    limit: int = Field(20, ge=1, le=100)
    top_cards: int = Field(5, ge=0, le=20)


class KeyPaper(BaseModel):
    id: str
    title: str
    url: str


class RunResponse(BaseModel):
    run_id: str
    project_id: str
    goal: str
    papers: int
    clusters: int
    key_papers: list[KeyPaper]
    summary: str
    report_uri: str | None = None


class EventItem(BaseModel):
    ts: str
    actor: str
    type: str
    payload: dict


class PaperItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    published: str | None = None


class RunSummary(BaseModel):
    run_id: str
    project_id: str
    goal: str
    status: str


class MemoryItem(BaseModel):
    ref_type: str
    ref_id: str
    content: str
    salience: float
    pinned: bool


class GraphEdgeItem(BaseModel):
    relation: str
    source: str
    target: str
    confidence: float
    provenance: dict


class GraphResponse(BaseModel):
    project_id: str
    nodes: int
    edges: int
    by_type: dict[str, int]
    sample_edges: list[GraphEdgeItem]
