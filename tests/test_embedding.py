import numpy as np

from researchos.core.models import Paper
from researchos.ingestion.chunking import chunk_paper
from researchos.ingestion.embedding import LocalEmbeddingProvider


def test_local_embedding_is_deterministic_and_correct_dim():
    p = LocalEmbeddingProvider(dim=64)
    a = p.embed(["memory augmented transformers"])[0]
    b = p.embed(["memory augmented transformers"])[0]
    assert a == b
    assert len(a) == 64


def test_local_embedding_captures_lexical_similarity():
    p = LocalEmbeddingProvider(dim=512)
    v = np.array(
        p.embed(
            [
                "long term memory for llm agents",
                "memory mechanisms in language model agents",
                "convolutional networks for image classification",
            ]
        )
    )
    related = float(v[0] @ v[1])
    unrelated = float(v[0] @ v[2])
    assert related > unrelated


def test_chunk_paper_produces_abstract_chunk():
    p = Paper(source="arxiv", source_id="1", title="Title", abstract="Body text").ensure_id()
    chunks = chunk_paper(p)
    assert len(chunks) == 1
    assert chunks[0].section == "abstract"
    assert "Title" in chunks[0].text
