"""ORM models. The ``EventRow`` table is append-only — the reproducibility backbone."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from researchos.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RunRow(Base):
    __tablename__ = "run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EventRow(Base):
    """Append-only. Never updated or deleted. Any run replays from here."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    actor: Mapped[str] = mapped_column(String(64))  # agent/tool/system name
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class PaperRow(Base):
    __tablename__ = "paper"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class MemoryItemRow(Base):
    """Long-term memory item with salience for consolidation/forgetting (ADR-0002).

    ref_type: "paper" (semantic), "concept" (consolidated theme), "interest" (reflection).
    """

    __tablename__ = "memory_item"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    ref_type: Mapped[str] = mapped_column(String(32), index=True)
    ref_id: Mapped[str] = mapped_column(String(96))
    content: Mapped[str] = mapped_column(Text, default="")
    salience: Mapped[float] = mapped_column(Float, default=1.0)
    pinned: Mapped[bool] = mapped_column(default=False)
    last_access: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ArtifactRow(Base):
    __tablename__ = "artifact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    uri: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
