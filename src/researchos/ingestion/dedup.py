"""Cross-source paper deduplication and metadata merging.

The same paper often appears on arXiv, Semantic Scholar, and OpenAlex with partial
metadata each. Two records are considered the same paper if they share *any* identity
signal — DOI, normalized arXiv id, or normalized title. We union all such records
(so arXiv↔OpenAlex↔S2 chains collapse transitively) and merge fields into the richest
surviving record.
"""

from __future__ import annotations

import re

from researchos.core.models import Paper

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ARXIV_VER = re.compile(r"v\d+$")


def _norm_title(title: str) -> str:
    return _NON_ALNUM.sub("", title.lower())


def _arxiv_id(paper: Paper) -> str | None:
    if paper.source == "arxiv" and paper.source_id:
        return _ARXIV_VER.sub("", paper.source_id)
    return None


def _signals(paper: Paper) -> list[str]:
    """Identity signals for a paper. Sharing any one marks two records as duplicates."""
    signals: list[str] = []
    if paper.doi:
        signals.append(f"doi:{paper.doi.lower()}")
    ax = _arxiv_id(paper)
    if ax:
        signals.append(f"arxiv:{ax}")
    title = _norm_title(paper.title)
    if title:
        signals.append(f"title:{title}")
    return signals


def _merge(primary: Paper, other: Paper) -> Paper:
    """Fold ``other`` into ``primary`` (kept), preferring richer values."""
    if len(other.abstract) > len(primary.abstract):
        primary.abstract = other.abstract
    if len(other.authors) > len(primary.authors):
        primary.authors = other.authors
    primary.doi = primary.doi or other.doi
    primary.pdf_url = primary.pdf_url or other.pdf_url
    primary.url = primary.url or other.url
    primary.published = primary.published or other.published
    if other.citation_count is not None:
        primary.citation_count = max(primary.citation_count or 0, other.citation_count)
    primary.categories = list(dict.fromkeys([*primary.categories, *other.categories]))
    return primary


def dedup_papers(papers: list[Paper]) -> list[Paper]:
    """Return unique papers, merging duplicates. First-appearance order is preserved."""
    n = len(papers)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)  # keep the earlier index as root

    signal_owner: dict[str, int] = {}
    for i, paper in enumerate(papers):
        paper.ensure_id()
        for sig in _signals(paper):
            if sig in signal_owner:
                union(i, signal_owner[sig])
            else:
                signal_owner[sig] = i

    components: dict[int, list[int]] = {}
    for i in range(n):
        components.setdefault(find(i), []).append(i)

    result: list[Paper] = []
    for root in sorted(components):  # roots are the earliest index → stable order
        idxs = components[root]
        primary = papers[idxs[0]]
        for j in idxs[1:]:
            _merge(primary, papers[j])
        result.append(primary)
    return result
