"""Persistence for runs, papers, and artifacts (relational source of truth)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from researchos.core.state import ResearchState
from researchos.persistence.db import get_session
from researchos.persistence.models import ArtifactRow, PaperRow, RunRow


class Store:
    """Small repository over the relational tables."""

    # ---- runs ----
    def create_run(self, run_id: str, project_id: str, goal: str) -> None:
        with get_session() as s:
            s.add(RunRow(id=run_id, project_id=project_id, goal=goal, status="running"))
            s.commit()

    def finish_run(self, run_id: str, status: str = "completed", cost: float = 0.0) -> None:
        with get_session() as s:
            row = s.get(RunRow, run_id)
            if row is not None:
                row.status = status
                row.cost = cost
                row.ended_at = datetime.now(UTC)
                s.commit()

    def list_runs(self, limit: int = 50) -> list[RunRow]:
        with get_session() as s:
            stmt = select(RunRow).order_by(RunRow.started_at.desc()).limit(limit)
            return list(s.scalars(stmt).all())

    def get_run(self, run_id: str) -> RunRow | None:
        with get_session() as s:
            return s.get(RunRow, run_id)

    # ---- papers ----
    def save_papers(self, state: ResearchState) -> int:
        n = 0
        with get_session() as s:
            for paper in state.papers.values():
                if s.get(PaperRow, paper.id) is not None:
                    continue
                s.add(
                    PaperRow(
                        id=paper.id,
                        project_id=state.project_id,
                        source=paper.source,
                        source_id=paper.source_id,
                        title=paper.title,
                        abstract=paper.abstract,
                        url=paper.url,
                        published=paper.published.isoformat() if paper.published else None,
                    )
                )
                n += 1
            s.commit()
        return n

    def list_papers(self, project_id: str, limit: int = 200) -> list[PaperRow]:
        with get_session() as s:
            stmt = (
                select(PaperRow)
                .where(PaperRow.project_id == project_id)
                .order_by(PaperRow.ingested_at.desc())
                .limit(limit)
            )
            return list(s.scalars(stmt).all())

    # ---- artifacts ----
    def add_artifact(self, project_id: str, run_id: str, kind: str, uri: str) -> None:
        with get_session() as s:
            s.add(ArtifactRow(project_id=project_id, run_id=run_id, kind=kind, uri=uri))
            s.commit()

    def list_artifacts(self, run_id: str) -> list[ArtifactRow]:
        with get_session() as s:
            stmt = select(ArtifactRow).where(ArtifactRow.run_id == run_id)
            return list(s.scalars(stmt).all())
