"""Central configuration.

Everything has an offline-safe default: the default profile runs with zero external
services or API keys. Override via environment variables (prefix ``RESEARCHOS_``) or a
``.env`` file. See ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RESEARCHOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- General ----
    data_dir: Path = Path("./data")
    log_level: str = "INFO"

    # ---- Embeddings ----
    embedding_provider: str = "local"  # local | openai | bge
    embedding_dim: int = 384

    # ---- LLM ----
    llm_provider: str = "null"  # null | openai
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_temperature: float = 0.2
    # Read from the conventional (unprefixed) env var.
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    # ---- Vector store ----
    qdrant_mode: str = "embedded"  # embedded | server
    qdrant_url: str = "http://localhost:6333"

    # ---- Memory & retrieval ----
    # Retrieval policy over the memory tiers: "vector" | "graph" | "hybrid" (RRF fusion).
    # "graph"/"hybrid" fall back to "vector" when the structural tier is disabled.
    retrieval_strategy: str = "hybrid"
    # Build and use the structural (knowledge-graph) memory tier.
    graph_enabled: bool = True

    # ---- Sources ----
    # Comma-separated list: any of arxiv, semantic_scholar, openalex.
    sources: str = "arxiv,openalex"
    # A contact email puts OpenAlex requests in the faster "polite pool" (optional).
    openalex_mailto: str | None = None
    semantic_scholar_api_key: str | None = Field(
        default=None, validation_alias="SEMANTIC_SCHOLAR_API_KEY"
    )
    # Code discovery: link papers to GitHub implementations.
    code_search: bool = True
    github_token: str | None = Field(default=None, validation_alias="GITHUB_TOKEN")

    # ---- Ingestion ----
    fetch_pdf: bool = False

    # ---- Experiments (Phase 4, assisted-first) ----
    # Timeout for a single sandboxed command.
    experiment_timeout_s: int = 60
    # Approval gate for python-exec: default OFF — execution requires explicit human
    # approval (CLI --yes / typer.confirm). Never enable for unattended automation.
    experiment_allow_exec: bool = False

    @property
    def source_list(self) -> list[str]:
        return [s.strip() for s in self.sources.split(",") if s.strip()]

    # ---- Derived paths ----
    @property
    def db_path(self) -> Path:
        return self.data_dir / "researchos.sqlite"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def qdrant_path(self) -> Path:
        return self.data_dir / "qdrant"

    @property
    def experiment_dir(self) -> Path:
        return self.data_dir / "experiments"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton settings."""
    return Settings()
