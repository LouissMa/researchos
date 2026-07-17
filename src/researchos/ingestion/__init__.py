"""Ingestion: embeddings, chunking, and optional PDF full-text extraction."""

from researchos.ingestion.chunking import chunk_paper
from researchos.ingestion.dedup import dedup_papers
from researchos.ingestion.embedding import get_embedding_provider

__all__ = ["chunk_paper", "get_embedding_provider", "dedup_papers"]
