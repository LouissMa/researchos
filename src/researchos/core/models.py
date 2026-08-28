"""Typed domain models — the vocabulary the whole system speaks.

Kept deliberately small and provider-agnostic. A ``Paper`` from arXiv and a ``Paper``
from Semantic Scholar are the same type; only ``source``/``source_id`` differ.
"""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel, Field


def stable_id(*parts: str) -> str:
    """Deterministic short id from its parts — makes runs reproducible and dedup easy."""
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


class Paper(BaseModel):
    """A scholarly paper, normalized across sources."""

    id: str = ""  # stable, content-derived; filled by ``ensure_id``
    source: str  # "arxiv" | "semantic_scholar" | "openalex" | ...
    source_id: str  # e.g. arXiv id "2401.01234"
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    published: date | None = None
    url: str = ""
    pdf_url: str = ""
    categories: list[str] = Field(default_factory=list)
    doi: str | None = None
    citation_count: int | None = None
    code_urls: list[str] = Field(default_factory=list)  # linked code repos (GitHub)
    full_text: str | None = None  # populated only when PDF ingestion is enabled

    def ensure_id(self) -> Paper:
        if not self.id:
            self.id = stable_id(self.source, self.source_id or self.title)
        return self

    @property
    def year(self) -> int | None:
        return self.published.year if self.published else None


class PaperChunk(BaseModel):
    """A retrievable chunk of a paper (abstract or a slice of full text)."""

    id: str
    paper_id: str
    section: str  # "abstract" | "body"
    index: int
    text: str


class ResearchCard(BaseModel):
    """Structured deep-understanding of a paper — not just a summary.

    Fields mirror how a researcher actually reads a paper. When no LLM is configured
    these are filled heuristically (extractive) and ``generated_by`` records that, so
    downstream consumers never mistake a heuristic card for an analyzed one.
    """

    paper_id: str
    problem: str = ""
    motivation: str = ""
    key_idea: str = ""
    method: str = ""
    results: str = ""
    limitations: str = ""
    future_work: str = ""
    repro_difficulty: str = ""  # "low" | "medium" | "high" | "unknown"
    opportunities: str = ""
    generated_by: str = "heuristic"  # "heuristic" | "llm:<model>"


class Cluster(BaseModel):
    """A thematic cluster of papers within a landscape."""

    id: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)


class Landscape(BaseModel):
    """The output of a literature-discovery run."""

    query: str
    summary: str = ""
    clusters: list[Cluster] = Field(default_factory=list)
    key_papers: list[str] = Field(default_factory=list)  # paper ids, most central first
    reading_order: list[str] = Field(default_factory=list)  # paper ids, recommended order


class Review(BaseModel):
    """The Critic's assessment of a landscape (coverage, balance, gaps)."""

    coverage: str = ""
    cluster_balance: str = ""
    missing_seminal: list[str] = Field(default_factory=list)  # titles possibly missed
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    score: float = 0.0  # 0–10
    reviewed_by: str = "critic"


class GraphNode(BaseModel):
    """A node in the structural (knowledge-graph) memory tier (ADR-0003).

    ``ref_id`` links back to the domain object (a ``Paper.id`` or a ``Cluster.id``);
    ``node_type`` is the ontology label (``paper``, ``concept``, ``method``, ...).
    """

    id: str  # stable: "{project_id}:{node_type}:{ref_id}"
    node_type: str
    ref_id: str
    label: str
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A typed, provenance-carrying relation between two graph nodes.

    **Anti-hallucination rule (ARCHITECTURE.md §5):** every edge must carry provenance —
    at least one of ``source_paper`` / ``span`` / ``tool`` — or the store rejects it at
    write time. ``confidence`` ∈ [0, 1].
    """

    relation: str
    source_id: str
    target_id: str
    provenance: dict = Field(default_factory=dict)
    confidence: float = 1.0


class ResearchIdea(BaseModel):
    """A research proposal derived from gap analysis over the knowledge graph (Phase 3).

    Every idea must be **grounded**: ``grounding`` lists the cluster/paper ids that
    support the gap claim, so proposals stay traceable (never free-floating hunches).
    """

    id: str
    title: str
    hypothesis: str
    rationale: str  # why this gap matters
    gap: str  # what the landscape is missing
    grounding: list[str] = Field(default_factory=list)  # cluster ids / paper ids
    novelty: float = 0.0  # 0–1 heuristic
    feasibility: float = 0.0  # 0–1 heuristic
    generated_by: str = "heuristic"  # "heuristic" | "llm:<model>"


class PaperReview(BaseModel):
    """The Reviewer's assessment of a single paper (strengths/weaknesses/novelty/score)."""

    paper_id: str
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    novelty: float = 0.0  # 0–1
    feasibility: float = 0.0  # 0–1
    score: float = 0.0  # 0–10
    reviewed_by: str = "heuristic"  # "heuristic" | "llm:<model>"


class ExperimentPlan(BaseModel):
    """A reproduction plan for one paper (Phase 4, assisted-first).

    ``commands`` are the exact sandboxed commands to run (human-approved before
    execution); ``baseline`` is what the paper claims, for later comparison.
    """

    id: str
    paper_id: str
    title: str
    steps: list[str] = Field(default_factory=list)  # reproduction narrative
    commands: list[str] = Field(default_factory=list)  # exact commands
    baseline: str = ""  # expected result from the paper
    generated_by: str = "heuristic"  # "heuristic" | "llm:<model>"


class Draft(BaseModel):
    """A LaTeX draft generated by the Writing agent (Phase 5).

    Related work is built **only from the project's knowledge graph** — every
    ``\\cite`` resolves to a ``\\bibitem`` in the same document (no fabricated
    references; ARCHITECTURE.md §5). ``inconsistencies`` reports any dangling cites.
    """

    id: str
    project_id: str
    run_id: str
    tex: str = ""
    sections: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)  # paper ids cited
    inconsistencies: list[str] = Field(default_factory=list)
    generated_by: str = "heuristic"  # "heuristic" | "llm:<model>"
