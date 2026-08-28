<div align="center">

# ResearchOS

### An Autonomous AI Research Operating System

*A multi-agent research collaborator that helps you discover, understand, and conduct scientific research — not another chatbot wrapper.*

[![CI](https://github.com/LouissMa/researchos/actions/workflows/ci.yml/badge.svg)](https://github.com/LouissMa/researchos/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](ROADMAP.md)

</div>

---

## What is this?

Most "AI research assistants" stop at *summarize this PDF*. ResearchOS is designed as a **stateful, multi-agent research environment**: a researcher opens a persistent **Project**, and specialist agents operate inside it with durable memory, an auditable trace of every decision, and reproducible artifacts.

It is built to support the *entire* research workflow — literature discovery, deep paper understanding, knowledge organization, research-gap and hypothesis generation, experiment design, and paper writing — as a loop with backtracking, not a one-shot pipeline.

> **Design philosophy:** traceability over magic · human-in-the-loop by default · every component swappable · reproducible by construction. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Why it's different

| Typical "paper chatbot" | ResearchOS |
|---|---|
| Stateless prompt → answer | Persistent **Project** with 4-tier memory |
| One model does everything | **Planner → Worker → Critic** multi-agent graph |
| "Trust me" answers | Every claim is **traceable** to a source; full event log |
| RAG over PDFs | Vector **+** knowledge-graph **+** episodic memory with reflection / consolidation / forgetting |
| Hard-coded pipeline | Retrieval, memory, orchestration are **swappable strategies** you can benchmark |

## Status

🚧 **Alpha.** This repository currently ships a **runnable foundation**: a real end-to-end *literature discovery* run that works **offline with zero external services or API keys**.

- ✅ Real multi-source search — **arXiv + OpenAlex** (Semantic Scholar opt-in), merged and **de-duplicated across sources**
- ✅ Paper ingestion + chunking (+ optional PDF full text)
- ✅ Local deterministic **embeddings** (no downloads) → **embedded Qdrant** vector store
- ✅ **GitHub code linking** — finds implementations for the key papers
- ✅ **Planner → Literature → Knowledge → Critic** agents over a shared `ResearchState`
- ✅ **Critic agent**: citation-coverage review ("are we missing seminal work?") + a bounded **reflection loop** that adds the gaps and re-ranks
- ✅ **Tiered memory operations** — consolidation (themes → concepts), reflection (interest profile), forgetting (salience decay)
- ✅ **Structural memory tier** — a knowledge graph (SQLite-backed, Neo4j-swappable) of papers/concepts with **provenance-carrying edges**; ungrounded edges are rejected at write time
- ✅ **Swappable retrieval strategies** — `vector` (embeddings) · `graph` (structural traversal) · `hybrid` (RRF fusion), selected via `RESEARCHOS_RETRIEVAL_STRATEGY`
- ✅ **Idea agent** — gap analysis over the landscape (cross-theme bridges, under-explored themes, recurring-interest alignment, isolated contributions) → grounded research proposals
- ✅ **Reviewer capability** — per-paper strengths / weaknesses / novelty / score (`researchos review`), with a frozen offline benchmark in CI
- ✅ **Graph analytics + visualization** — degree centrality (seminal candidates), community detection, and a dashboard Graph tab (SVG)
- ✅ **Frozen offline benchmarks** (`benchmarks/`) — recall@k + grounding per strategy on 4 scenarios + reviewer tier ordering, run in CI
- ✅ Append-only **event log** (SQLite) — every run is replayable
- ✅ Landscape report artifact + streaming reasoning trace
- ✅ FastAPI service, a **no-build web dashboard**, and a CLI

Everything heavy or paid (LLM, GROBID, server-mode Qdrant, Neo4j, BGE embeddings) is **optional and pluggable** behind an interface. See the [ROADMAP](ROADMAP.md) for what's next.

## Quickstart

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) (or plain `pip`).

```bash
git clone https://github.com/LouissMa/researchos.git
cd researchos

# Install (default profile = fully offline)
uv sync                     # or: pip install -e .

# Run a literature-discovery workflow — no API key needed
uv run researchos discover "long-term memory mechanisms for LLM agents" --limit 15
```

You'll get a ranked, deduplicated, clustered research landscape, with a reading order and a saved report under `./data/artifacts/`. Inspect the reasoning trace:

```bash
uv run researchos runs list
uv run researchos runs trace <run_id>
```

Inspect long-term memory (concepts consolidated, interest profile, salience):

```bash
uv run researchos memory list
```

Inspect the knowledge graph — the structural memory tier:

```bash
uv run researchos graph stats     # nodes / edges by type
uv run researchos graph edges     # provenance-carrying relations
uv run researchos graph analytics # degree centrality + communities (seminal candidates)
```

Explore what's worth doing next and how strong each paper looks:

```bash
uv run researchos ideas list                 # grounded research proposals (Idea agent)
uv run researchos review <paper_id>          # strengths / weaknesses / novelty / score
```

Compare retrieval strategies against the frozen benchmark suite (offline):

```bash
uv run researchos benchmark                 # all strategies, all scenarios
uv run researchos benchmark --strategy hybrid
# or directly:  uv run python -m benchmarks.run_eval
```

Or run it as a service with a **web dashboard** (project view + reasoning-trace timeline):

```bash
uv run researchos serve            # dashboard at http://127.0.0.1:8000/  ·  API docs at /docs
```

```bash
curl -X POST http://127.0.0.1:8000/projects/default/runs \
  -H 'content-type: application/json' \
  -d '{"goal": "retrieval-augmented generation for code"}'
```

### Turn on the LLM (optional)

Point ResearchOS at any OpenAI-compatible endpoint (OpenAI, vLLM, DeepSeek, Together, Ollama, …) to unlock LLM-written research cards and summaries:

```bash
cp .env.example .env
# set RESEARCHOS_LLM_PROVIDER=openai, RESEARCHOS_LLM_MODEL, OPENAI_API_KEY, ...
```

Without a key, the same pipeline runs and produces **heuristic** (extractive) cards clearly marked as such — nothing breaks.

## How it works (30 seconds)

```
User goal
  → Planner decomposes into tasks
  → Literature Agent  → arXiv + OpenAlex → dedup → ingest → embed → Qdrant → rank
  → Knowledge Agent   → cluster → research cards → GitHub code links → landscape
  → Critic Agent      → citation-coverage review + score
  → Reflection loop   → add missing seminal papers → re-rank (bounded, once)
  → Memory ops        → consolidate themes · reflect interests · decay salience
  → Knowledge graph   → paper/concept nodes + grounded edges (structural tier)
  → Idea Agent        → gap analysis → grounded research proposals
  → Artifacts + replayable trace      ← every step emits events
```

Ranking uses the configured **retrieval strategy** (default `hybrid` = vector + graph
fused with reciprocal-rank fusion); the knowledge graph is rebuilt per run from the
landscape in two deterministic phases, so rankings stay reproducible across runs.

Runs are stateful and checkpointable; agents never mutate global state directly — they return **state deltas** that the runtime applies, so every change is diffable, auditable, and replayable from the event log.

## Repository layout

```
src/researchos/
  core/           ResearchState, models, the core interfaces (the seams)
  orchestration/  Orchestrator interface + planner + bounded reflection (LangGraph-swappable)
  agents/         base · literature · knowledge · critic · idea  (Experiment/Writing next)
  tools/          MCP-style tools: arXiv · OpenAlex · Semantic Scholar · GitHub
  ingestion/      PDF (PyMuPDF, optional) · chunking · dedup · embedding providers
  memory/         vector store (Qdrant) · graph store + builder · retrieval strategies · MemoryManager
  llm/            LLM interface: null (heuristic) · OpenAI-compatible
  persistence/    SQLAlchemy models (incl. kg_node / kg_edge) · append-only event log
  observability/  event types + emitter (OpenTelemetry next)
  api/            FastAPI app · routes · schemas · no-build web dashboard
  cli.py          typer CLI (discover · runs · memory · graph · benchmark · serve)
benchmarks/       frozen corpus + scenarios + run_eval.py (recall@k, grounding)
docs/adr/         architecture decision records
examples/         runnable scripts
tests/            unit + integration
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — full system design: agents, memory, knowledge graph, data model, tool system, evaluation
- [ROADMAP.md](ROADMAP.md) — phased plan from foundation to full research workflow
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to get involved
- [docs/adr/](docs/adr/) — the load-bearing design decisions and their trade-offs

## License

[Apache 2.0](LICENSE) © 2026 LouissMa
