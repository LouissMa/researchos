"""The append-only event log — episodic memory and the reproducibility backbone.

Events are only ever appended and read. Any run's full reasoning trace is reconstructed
by reading its events in order.
"""

from __future__ import annotations

from sqlalchemy import select

from researchos.persistence.db import get_session
from researchos.persistence.models import EventRow


class EventLog:
    """Thin, append-only accessor over the ``event`` table."""

    def append(self, run_id: str, actor: str, type: str, payload: dict | None = None) -> int:
        with get_session() as s:
            row = EventRow(run_id=run_id, actor=actor, type=type, payload=payload or {})
            s.add(row)
            s.commit()
            return row.id

    def list(self, run_id: str) -> list[EventRow]:
        with get_session() as s:
            stmt = select(EventRow).where(EventRow.run_id == run_id).order_by(EventRow.id)
            return list(s.scalars(stmt).all())
