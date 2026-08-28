"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from researchos.api.routes import router
from researchos.config import get_settings
from researchos.logging import setup_logging
from researchos.orchestration.orchestrator import SequentialOrchestrator


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    # One orchestrator per process (embedded Qdrant holds a single-writer lock).
    app.state.orchestrator = SequentialOrchestrator(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ResearchOS",
        version="1.0.0",
        description="An Autonomous AI Research Operating System.",
        lifespan=_lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
