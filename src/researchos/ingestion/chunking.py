"""Turn a paper into retrievable chunks.

Always chunks the abstract; if full text is present (PDF ingestion enabled), it is split
into overlapping windows. Chunk ids are deterministic so re-ingestion is idempotent.
"""

from __future__ import annotations

from researchos.core.models import Paper, PaperChunk


def _windows(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def chunk_paper(paper: Paper) -> list[PaperChunk]:
    chunks: list[PaperChunk] = []
    title_abstract = f"{paper.title}. {paper.abstract}".strip()
    if title_abstract:
        chunks.append(
            PaperChunk(
                id=f"{paper.id}:abstract:0",
                paper_id=paper.id,
                section="abstract",
                index=0,
                text=title_abstract,
            )
        )
    if paper.full_text:
        for i, body in enumerate(_windows(paper.full_text)):
            chunks.append(
                PaperChunk(
                    id=f"{paper.id}:body:{i}",
                    paper_id=paper.id,
                    section="body",
                    index=i,
                    text=body,
                )
            )
    return chunks
