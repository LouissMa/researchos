"""MemoryManager — the tiered-memory operations (ADR-0002).

Implements the three long-term memory operations beyond plain retrieval:

- **consolidate**: collapse a run's clusters into higher-level *concept* memories, so the
  system remembers themes, not just individual papers.
- **reflect**: derive a durable *interest profile* from the episodic record of past runs.
- **decay** (forgetting): exponentially reduce the salience of non-pinned memories so the
  working set stays sharp; low-salience items sink but are never deleted.

These operate on the relational ``memory_item`` table; semantic (vector) retrieval lives
in :class:`~researchos.memory.store.SemanticMemory`.
"""

from __future__ import annotations

import re

from sqlalchemy import select

from researchos.core.state import ResearchState
from researchos.persistence.db import get_session
from researchos.persistence.models import MemoryItemRow, RunRow

_TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "using",
    "based",
    "via",
    "from",
    "into",
    "research",
    "study",
    "studies",
    "approach",
    "method",
    "methods",
    "model",
    "models",
    "learning",
    "system",
    "systems",
    "novel",
    "new",
    "toward",
    "towards",
}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class MemoryManager:
    # ------------------------------------------------------------- record
    def record_paper_memories(self, state: ResearchState) -> int:
        """Register each paper as a semantic memory item (idempotent)."""
        n = 0
        with get_session() as s:
            for paper in state.papers.values():
                mid = f"{state.project_id}:paper:{paper.id}"
                if s.get(MemoryItemRow, mid) is not None:
                    continue
                s.add(
                    MemoryItemRow(
                        id=mid,
                        project_id=state.project_id,
                        ref_type="paper",
                        ref_id=paper.id,
                        content=paper.title,
                        salience=1.0,
                    )
                )
                n += 1
            s.commit()
        return n

    # -------------------------------------------------------- consolidate
    def consolidate(self, state: ResearchState) -> int:
        """Collapse the run's clusters into concept memories (many papers → one concept)."""
        n = 0
        with get_session() as s:
            for cluster in state.clusters:
                mid = f"{state.project_id}:concept:{cluster.id}:{state.run_id}"
                content = (
                    f"Concept '{cluster.label}': {len(cluster.paper_ids)} papers; "
                    f"keywords: {', '.join(cluster.keywords) or 'n/a'}."
                )
                s.merge(
                    MemoryItemRow(
                        id=mid,
                        project_id=state.project_id,
                        ref_type="concept",
                        ref_id=cluster.id,
                        content=content,
                        salience=1.2,  # concepts start slightly more salient than raw papers
                    )
                )
                n += 1
            s.commit()
        return n

    # ------------------------------------------------------------ reflect
    def reflect(self, project_id: str) -> str:
        """Derive a durable interest profile from the goals of past runs."""
        with get_session() as s:
            goals = list(
                s.scalars(select(RunRow.goal).where(RunRow.project_id == project_id)).all()
            )
        counts: dict[str, int] = {}
        for goal in goals:
            for tok in _tokens(goal):
                counts[tok] = counts.get(tok, 0) + 1
        top = [t for t, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]]
        profile = "Recurring interests: " + (", ".join(top) if top else "none yet")
        with get_session() as s:
            s.merge(
                MemoryItemRow(
                    id=f"{project_id}:interest:profile",
                    project_id=project_id,
                    ref_type="interest",
                    ref_id="profile",
                    content=profile,
                    salience=2.0,
                    pinned=True,  # the interest profile never decays
                )
            )
            s.commit()
        return profile

    # ------------------------------------------------------------- decay
    def decay(self, project_id: str, rate: float = 0.95) -> int:
        """Exponential forgetting: multiply non-pinned salience by ``rate`` per cycle."""
        n = 0
        with get_session() as s:
            rows = s.scalars(
                select(MemoryItemRow).where(MemoryItemRow.project_id == project_id)
            ).all()
            for row in rows:
                if row.pinned:
                    continue
                row.salience = round(row.salience * rate, 4)
                n += 1
            s.commit()
        return n

    # -------------------------------------------------------------- reads
    def list_items(
        self, project_id: str, ref_type: str | None = None, limit: int = 100
    ) -> list[MemoryItemRow]:
        with get_session() as s:
            stmt = select(MemoryItemRow).where(MemoryItemRow.project_id == project_id)
            if ref_type:
                stmt = stmt.where(MemoryItemRow.ref_type == ref_type)
            stmt = stmt.order_by(MemoryItemRow.salience.desc()).limit(limit)
            return list(s.scalars(stmt).all())
