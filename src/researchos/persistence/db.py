"""Database engine and session management.

SQLite by default — the foundation runs from a single file with no server. The same
SQLAlchemy models target Postgres unchanged when you scale up.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def init_db(db_path: Path) -> Engine:
    """Create the engine and tables. Idempotent."""
    global _engine, _SessionFactory
    if _engine is None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{db_path}", future=True)
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
        # Import models so metadata is populated before create_all.
        from researchos.persistence import models  # noqa: F401

        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized — call init_db() first.")
    return _SessionFactory()


def close_db() -> None:
    """Dispose the engine and release the database file (frees SQLite locks).

    Call when the process is done with persistence, e.g. before cleaning up temp
    data directories (benchmarks) or on graceful server shutdown.
    """
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
