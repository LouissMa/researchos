"""Typed domain models — the vocabulary the whole system speaks.

Kept deliberately small and provider-agnostic. A ``Paper`` from arXiv and a ``Paper``
from Semantic Scholar are the same type; only ``source``/``source_id`` differ.
"""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel, Field


def _stable_id(*parts: str) -> str:
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
    full_text: str | None = None  # populated only when PDF ingestion is enabled

    def ensure_id(self) -> Paper:
        if not self.id:
            self.id = _stable_id(self.source, self.source_id or self.title)
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
