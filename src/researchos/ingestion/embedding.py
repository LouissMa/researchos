"""Embedding providers.

Default ``local`` provider is a deterministic hashed bag-of-words embedding: no model
download, no network, fully reproducible. It captures lexical overlap well enough for
retrieval and clustering in the foundation. Swap in ``openai`` (or ``bge``) for real
semantic embeddings via config — the ``EmbeddingProvider`` interface is unchanged.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from researchos.config import Settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _stable_hash(token: str) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)


class LocalEmbeddingProvider:
    """Deterministic, offline hashed embedding. Good enough for the foundation."""

    name = "local"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            tokens = _tokenize(text)
            for tok in tokens:
                h = _stable_hash(tok)
                idx = h % self.dim
                sign = 1.0 if (h >> 1) % 2 == 0 else -1.0  # signed hashing reduces collisions
                vec[idx] += sign
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            out.append(vec.tolist())
        return out


class OpenAIEmbeddingProvider:
    """Embeddings via any OpenAI-compatible endpoint. Requires ``researchos[llm]``."""

    name = "openai"

    def __init__(self, settings: Settings, model: str = "text-embedding-3-small") -> None:
        self.model = model
        self.dim = settings.embedding_dim
        self.available = False
        self._client = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=settings.openai_api_key, base_url=settings.llm_base_url
                )
                self.available = True
            except Exception:
                self.available = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._client:
            raise RuntimeError("OpenAI embeddings unavailable — no API key or client.")
        resp = self._client.embeddings.create(model=self.model, input=texts)
        vectors = [d.embedding for d in resp.data]
        self.dim = len(vectors[0]) if vectors else self.dim
        return vectors


def get_embedding_provider(settings: Settings):
    """Factory. Falls back to the local provider if a richer one is unavailable."""
    if settings.embedding_provider == "openai":
        provider = OpenAIEmbeddingProvider(settings)
        if provider.available:
            return provider
        # Degrade gracefully rather than crash offline.
        return LocalEmbeddingProvider(dim=settings.embedding_dim)
    return LocalEmbeddingProvider(dim=settings.embedding_dim)
