"""FastAPI service exposing runs, event traces, papers, and artifacts."""

from researchos.api.app import create_app

__all__ = ["create_app"]
