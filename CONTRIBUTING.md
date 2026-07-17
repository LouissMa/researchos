# Contributing to ResearchOS

Thanks for your interest! ResearchOS aims to be a serious, well-engineered piece of AI research
infrastructure. Contributions of all sizes are welcome — from typo fixes to new agents and tools.

## Ground rules

1. **Respect the interfaces.** Every subsystem (`Orchestrator`, `MemoryStore`, `Tool`,
   `EmbeddingProvider`, `LLM`, `GraphStore`) is a seam. New capabilities should be a new
   *implementation* of an existing interface wherever possible, not a change to core.
2. **Traceability is non-negotiable.** New agent behavior must emit events. New knowledge-graph
   edges must carry provenance and confidence.
3. **Offline-first defaults.** The default install must keep running with zero external services or
   API keys. Anything heavy (LLM, GROBID, Neo4j, server-mode Qdrant, model downloads) goes behind
   an optional extra and a config flag.
4. **Agents return state deltas** — they never mutate global state directly.

## Development setup

```bash
git clone https://github.com/LouissMa/researchos.git
cd researchos
uv sync --extra dev
```

Run the checks:

```bash
uv run pytest -m "not network"     # unit tests (offline)
uv run pytest                      # include tests that hit external APIs
uv run ruff check .
uv run ruff format .
uv run mypy src
```

Try the end-to-end run:

```bash
uv run researchos discover "retrieval augmented generation" --limit 10
```

## Where to contribute

- **New tools** (`src/researchos/tools/`) — Semantic Scholar, OpenAlex, GitHub, PubMed. Implement
  the `Tool` interface; add rate limiting via the shared source-client layer.
- **New agents** (`src/researchos/agents/`) — Critic, Idea, Reviewer, Experiment, Writing.
- **Retrieval / memory strategies** (`src/researchos/memory/`) — new `RetrievalStrategy`
  implementations to benchmark.
- **Evaluation** (`benchmarks/`) — frozen research scenarios and gold sets.

Open an issue describing the design before large changes, so we can align on interfaces first.

## Pull requests

- Keep PRs focused; one concern per PR.
- Add or update tests. Offline tests must pass without network.
- Update `ARCHITECTURE.md` / `ROADMAP.md` if you change a design decision, and add an ADR under
  `docs/adr/` for load-bearing choices.
- Follow the existing code style (`ruff format`).

## Code of conduct

Be kind, be rigorous, assume good faith. We're here to build good research tools together.
