# ResearchOS — Roadmap

Depth-first, not breadth-first. A complete, trustworthy literature system is worth more — to users
and as infrastructure — than a shallow end-to-end pipeline. Each phase ships something that
**runs** and is **observable**.

Legend: ✅ done · 🟡 in progress · ⬜ planned

---

## Phase 0 — Skeleton & observability
> *Deliverable: an empty run streams a trace end-to-end. Observability first.*

- ✅ Repo, packaging (`uv`/hatchling), Apache-2.0
- ✅ Core interfaces: `Agent`, `Orchestrator`, `MemoryStore`, `Tool`, `EmbeddingProvider`, `LLM`
- ✅ `ResearchState` + `Task` + typed models
- ✅ Append-only **event log** (SQLite) + event emitter
- ✅ FastAPI shell + CLI
- ⬜ OpenTelemetry spans + LLM tracing (LangFuse/Phoenix)

## Phase 1 — MVP: literature discovery (runnable foundation)
> *Deliverable: "Study long-term memory for LLM agents" → ranked, deduplicated, clustered
> landscape with a defensible reading order, every recommendation traceable to why.*

- ✅ arXiv tool (real API) behind the `Tool` interface
- ✅ Ingestion: metadata + chunking (+ optional PDF full text via PyMuPDF)
- ✅ Embedding providers: local deterministic (offline) · OpenAI-compatible
- ✅ Embedded Qdrant vector store + semantic retrieval
- ✅ Planner + Literature + Knowledge agents over `ResearchState`
- ✅ Research cards (heuristic; LLM-authored when a key is configured)
- ✅ Landscape report artifact + reasoning-trace inspection
- ✅ Semantic Scholar + OpenAlex tools (behind the shared `SourceClient` HTTP layer)
- ✅ Multi-source search + cross-source dedup (union by DOI / arXiv id / title)
- ✅ GitHub Actions CI (ruff + offline pytest, Python 3.12 & 3.13)
- ✅ GitHub repository search tool + code linking for key papers
- ✅ Citation-coverage check ("did we miss seminal work?") — in the Critic
- ✅ Web dashboard: project view + reasoning-trace timeline (no-build; React SPA still planned)

## Phase 2 — Memory & Critic  *(complete)*
> *Deliverable: the memory system becomes real infrastructure, and quality is gated.*

- ✅ **Critic** agent (coverage / balance / score) + **bounded reflection loop**
- ✅ Tiered memory operations: **consolidation** (themes → concepts), **reflection**
  (interest profile), **forgetting** (salience decay) on the `memory_item` store
- ✅ Structural (knowledge-graph) memory tier — graph-in-SQLite behind a `GraphStore`
  interface (ADR-0003): paper/concept nodes + provenance-carrying edges (ungrounded
  edges rejected at write time); built per run in two deterministic phases so hybrid
  rankings stay reproducible
- ✅ `RetrievalStrategy` variants — **vector** vs **graph** vs **hybrid** (RRF fusion),
  swappable via `RESEARCHOS_RETRIEVAL_STRATEGY` and benchmarked head-to-head
- ✅ `benchmarks/` frozen scenarios (19-paper corpus, 4 topics) + eval CI:
  recall@5, grounding@5, MRR per strategy, per-scenario thresholds

## Phase 3 — Ideas & Review  *(complete)*
- ✅ **Idea** agent: gap analysis over the knowledge graph → grounded research proposals
  (cross-cluster bridges · under-explored themes · recurring-interest alignment ·
  isolated contributions); heuristic offline + LLM mode
- ✅ **Reviewer** capability (strengths/weaknesses/novelty/feasibility/score) + frozen
  offline benchmark (`benchmarks/run_reviewer_eval.py`, tier ordering + score bands) in CI
- ✅ Knowledge-graph visualization — dashboard **Graph tab** (SVG, node-type colors) +
  `/projects/{id}/graph/viz` endpoint
- ✅ Lightweight graph analytics in SQLite (degree centrality → seminal candidates,
  connected components → communities) via `researchos graph analytics`; **Neo4j remains
  the v2 drop-in** per ADR-0003 once multi-hop analytics dominate

## Phase 4 — Experiments (highest risk, deliberately last)  *(complete, assisted-first)*
- ✅ **Experiment** agent: plan → code template → sandboxed run → analyze (assisted-first:
  the human approves/edits every command before it runs)
- ✅ Sandboxed `python-exec` tool — command vetting (network/install/destructive blocklist),
  timeout, working-dir isolation, secrets-stripped env, **explicit human approval gate**
  (containers remain the hard-isolation upgrade)
- ✅ Experiment tracking + baseline comparison + reproduction workflow (`experiment` table,
  `researchos experiment plan|run|list`, baseline-match verdicts)
- ✅ Ships first as *assisted* reproduction (human runs, system records); autonomous
  execution stays gated behind explicit approval

## Phase 5 — Writing & polish
- ⬜ **Writing** agent: LaTeX drafts, related work from the KG, consistency checks
- ⬜ Full `examples/`, tutorials, API docs
- ⬜ 1.0 launch

---

## Future extensions
- VS Code / Zotero / Overleaf integrations
- Multi-user collaborative projects + shared team memory
- Self-improving retrieval (learns per-user strategy from feedback)
- "Research replication leaderboard" — community benchmark of reproduced papers
- Local-first / open-weight model support for privacy-sensitive labs
- Temporal-backed durable orchestration for month-long research campaigns
