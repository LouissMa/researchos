# Changelog

All notable changes to ResearchOS are documented here.

## [1.0.0] — 2026-08

The full research loop, assisted-first.

### Added (Phases 2–5)
- **Structural memory tier** — knowledge graph in SQLite behind a `GraphStore` interface
  (ADR-0003): paper/concept nodes, provenance-carrying edges (ungrounded edges rejected),
  built per run in two deterministic phases so rankings stay reproducible.
- **Retrieval strategies** — `vector` / `graph` / `hybrid` (RRF fusion), swappable via
  `RESEARCHOS_RETRIEVAL_STRATEGY`; benchmarked in CI.
- **Idea agent** — gap analysis over the landscape (cross-cluster bridges, under-explored
  themes, recurring-interest alignment, isolated contributions) → grounded proposals.
- **Reviewer** — per-paper strengths / weaknesses / novelty / feasibility / score with a
  frozen offline benchmark.
- **Graph analytics + visualization** — degree centrality (seminal candidates), community
  detection, dashboard Graph tab (SVG).
- **Experiment workflow (assisted-first)** — reproduction plans from research cards,
  sandboxed `python-exec` (command vetting, timeout, directory isolation, secrets-stripped
  env, human-approval gate), tracking with baseline-match verdicts.
- **Writing agent** — LaTeX related-work drafts grounded in the knowledge graph, with
  citation-consistency checks (no fabricated references).
- **Frozen offline benchmarks** — retrieval (recall@k / grounding@k / MRR) and reviewer
  (tier ordering) suites in CI.
- CLI: `discover`, `runs`, `memory`, `graph stats|edges|analytics`, `ideas list`,
  `review`, `experiment plan|run|list`, `write draft|check`, `benchmark`, `serve`.
- Fully offline example: `examples/offline_discovery.py` (zero network / zero keys).

### Changed
- Project status: Alpha → **1.0.0** (Production/Stable classifier).
- **Project-scoped paper rows** — `paper` is now keyed by `(project_id, paper_id)`, so the
  same paper ingested in two projects is two rows and `list_papers(project)` is correct.
  *Pre-1.0 alpha databases: re-run ingestion (or start from a fresh `data/` dir).*

## [0.1.0] — 2026-07

- Alpha foundation: multi-source literature discovery (arXiv/OpenAlex/Semantic Scholar),
  Planner → Literature → Knowledge → Critic pipeline, bounded reflection loop, tiered
  memory operations (consolidation / reflection / decay), append-only event log, FastAPI
  + dashboard + CLI, GitHub Actions CI, fully offline defaults.
