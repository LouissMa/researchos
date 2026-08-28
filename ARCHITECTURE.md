# ResearchOS — Architecture

This document is the design contract for ResearchOS. It describes the target system; the
current repository implements the **runnable foundation** (see [ROADMAP.md](ROADMAP.md) for
what is built vs. planned). Load-bearing decisions have dedicated records in [docs/adr/](docs/adr/).

---

## 1. Framing

Real research is **not a linear pipeline** (Question → Discovery → … → Writing). It is a loop
with backtracking: a gap found while reading sends you back to search; a failed experiment
rewrites the hypothesis. So ResearchOS is **not** a chain of prompts. It is a **stateful,
multi-agent research environment** where a planner orchestrates specialist agents over a shared,
persistent research state. This is the single decision that separates ResearchOS from a wrapper.

**Product principles (ranked, because they conflict):**
1. **Traceability over magic** — every claim links to a source; every action is logged.
2. **Human-in-the-loop by default** — the agent proposes; the human approves state-changing steps.
3. **Modularity over cleverness** — retrieval, memory, planning are swappable so the system can study itself.
4. **Reproducibility** — any workflow re-runs from its event log + artifact store.

**Non-goals (v1):** general chatbot; running arbitrary code on the host (experiments are sandboxed);
claiming to autonomously *do* novel science. It is a collaborator that amplifies.

---

## 2. Layered architecture

```
CLIENT          React UI · CLI · (future) VS Code / Zotero / Overleaf
                       │  REST + WebSocket (streaming reasoning trace)
API / GATEWAY   FastAPI · auth · request→run mapping · SSE
                       │
ORCHESTRATION   Planner (graph) · Agent Runtime · shared ResearchState · Checkpointer
   │                 │                 │                    │
AGENTS          TOOL LAYER        MEMORY               SERVICES
Literature      MCP servers:      Working (run)        Paper ingest (GROBID/PyMuPDF)
Knowledge        arxiv, s2,       Episodic (events)    Embedding
Idea             openalex,        Semantic (vector)    Sandbox (exec)
Critic           github,          Structural (graph)
Experiment       python-exec,     Reflection /
Writing          latex            Consolidation / Forgetting
                       │
PERSISTENCE     Postgres (relational + event log) · Qdrant (vector) · Neo4j (graph) · Object store
                       │
OBSERVABILITY   OpenTelemetry · LLM tracing · structured event log · eval harness
```

### Central abstraction: `Run` over `ResearchState`
- A **Run** is one invocation of the orchestration graph. It has an id, status, checkpoint
  history, and emits an event stream.
- **ResearchState** is the shared, typed working set passed between graph nodes. It is *not* the
  source of truth for long-term data — durable facts are committed to the databases through the
  memory layer. **Transient run state ≠ persistent project memory.** Conflating them is the #1
  way these systems become unreproducible.

### Orchestration engine — LangGraph, wrapped
LangGraph is the chosen backbone (explicit graph, durable checkpoints, human-in-the-loop
interrupts, typed shared state, step streaming). But it is hidden behind our own `Orchestrator`
interface so it can be swapped for a hand-rolled state machine or a Temporal-backed engine later
without touching agents. See [ADR-0001](docs/adr/0001-orchestration-langgraph.md). The foundation
ships a dependency-free `SequentialOrchestrator` implementing that same interface.

---

## 3. Agents

Every agent implements one contract, so agents are uniformly testable, swappable, observable:

```python
class Agent(Protocol):
    role: str
    def run(self, state: ResearchState, task: Task) -> AgentResult: ...
# AgentResult = { output, state_delta, tool_calls, reasoning_trace, cost }
```

**Hard rule:** agents return a `state_delta`; they never mutate global state directly. The runtime
applies deltas, so every change is diffable and reversible — the basis for audit and replay.

| Agent | Owns | Key risk it manages |
|---|---|---|
| **Planner** | task decomposition, routing, loop/budget control | infinite loops → hard step/cost budget |
| **Literature** | multi-source search, dedup, ranking, reading order | source bias, cross-source duplicates |
| **Knowledge** | memory writes, KG construction, clustering, research cards | hallucinated relations → require citable source span |
| **Idea** | gap analysis, hypothesis generation | plausible-but-unfounded ideas → gated by Critic |
| **Critic** | review, reflection, self-check | sycophancy → adversarial prompt, separate settings |
| **Experiment** | plan → code → sandboxed run → analyze | arbitrary code exec → strict sandbox |
| **Writing** | LaTeX drafting, related work, consistency | fabricated citations → cite only from KG |

**Two deliberate patterns:** (1) a **Planner–Worker–Critic** triangle where the Critic is a
first-class control loop gating Idea/Writing output; (2) a **reflection loop with a budget** —
agents may retry after Critic feedback, but the Planner enforces max-iterations and cost.

The MVP ships **2 agents** (Literature + Knowledge) behind this interface. Adding the rest is
config, not rearchitecture. Phase 3 adds **Idea** (gap analysis over the landscape) and the
standalone **Reviewer** capability; Experiment and Writing follow in Phase 4/5.

---

## 4. Memory (4 tiers)

```
WORKING     Current run's ResearchState + conversation window. Volatile, token-bounded.
EPISODIC    Append-only event log: "what happened." Source of truth for replay & reflection.
SEMANTIC    Papers, note chunks, concepts, cards as embeddings (Qdrant). "What we know."
STRUCTURAL  Typed relations in a knowledge graph. "How things connect."
```

Four operations make this research infrastructure rather than "RAG over PDFs":
- **Retrieval** — hybrid: vector (semantic) + graph traversal (structural) + metadata filter. A
  `MemoryRouter`/`RetrievalStrategy` chooses the mix per query; strategies are swappable and
  **benchmarkable**.
- **Reflection** — a periodic/Critic-triggered pass over episodic memory producing *derived*
  memories (e.g. "user consistently reads memory-augmentation papers → strengthen that interest").
- **Consolidation** — dedup + summarize near-duplicate memories into concept nodes to keep
  retrieval sharp and context small.
- **Forgetting** — `salience = f(recency, access_count, user_pin, project_relevance)`; low-salience
  items are demoted (archived, not deleted). Pinned memories never decay.

```python
class MemoryStore(Protocol):
    def write(self, item, tier) -> None: ...
    def retrieve(self, query, k, strategy) -> list[Memory]: ...
    def reflect(self, project_id) -> list[DerivedMemory]: ...
    def consolidate(self, project_id) -> ConsolidationReport: ...
    def decay(self, project_id, policy) -> None: ...
```

See [ADR-0002](docs/adr/0002-tiered-memory.md).

---

## 5. Knowledge graph

**Ontology.** Nodes: `Paper, Author, Method, Dataset, Concept, Venue, Problem, Hypothesis,
Experiment, Note, Project`. Edges: `CITES, AUTHORED_BY, USES_METHOD, EVALUATED_ON, IMPROVES_ON,
CONTRADICTS, INTRODUCES, ADDRESSES, DERIVED_FROM, PART_OF, SUPPORTS/REFUTES`.

**Is Neo4j justified?** Not for the MVP. A few-thousand-node citation/method graph fits Postgres
with an `edges` table + recursive CTEs. Neo4j earns its place when multi-hop queries dominate and
graph algorithms (centrality for seminal papers, community detection for sub-fields) become core
UX. The foundation ships graph-in-SQLite behind a `GraphStore` interface; Neo4j is a v2 drop-in.
See [ADR-0003](docs/adr/0003-graph-postgres-then-neo4j.md).

**Anti-hallucination:** every edge carries `provenance` (source paper + text span or asserting
tool) and `confidence`. Ungrounded edges are rejected at write time. Hard rule.

---

## 6. Data model

**Relational (Postgres/SQLite):** `project, paper, research_card, note, hypothesis, experiment,
edge, memory_item, run, event (APPEND-ONLY), tool_call, artifact`. The `event` table is the
**reproducibility backbone** — never mutated or deleted; any run replays from it.

**Vector (Qdrant):** collections `papers, note_chunks, concepts, research_cards`; every point
carries `payload{project_id, ref_id, source, section}` for filtered search and hard project
isolation.

Full schema sketch is in the design notes; the foundation implements `project, run, event,
paper, artifact, memory_item, kg_node, kg_edge` in SQLite via SQLAlchemy.

---

## 7. Tool system (MCP)

Tools are modeled as **MCP servers**: process isolation, uniform schema, independent scaling, and
community-extensible (add a `pubmed` server without touching core).

```python
class ToolSpec:  # name, input_schema, output_schema, side_effects, cost_hint, auth_scope
```

- **Read tools** (arxiv/s2/openalex/github search) — free to call, cached, rate-limited below the
  tool via a shared `SourceClient` so we are good API citizens.
- **Side-effecting tools** (python-exec, latex-build, memory-write) — require Planner
  authorization; `python-exec` runs in a **network-restricted, ephemeral, resource-capped
  container** scoped to the experiment's artifact dir, gated behind explicit human approval. This
  is the biggest risk surface in the system and is treated as such.

The foundation ships a real **arXiv** tool implementing the tool interface; Semantic Scholar,
OpenAlex, and GitHub are next and slot in behind the same interface.

---

## 8. State management, errors, observability

**State.** Run state via a checkpointer (resumable, HITL-interruptible); project state in the
databases, committed via the memory layer. State deltas are merged by typed reducers — no
last-write-wins.

**Error handling (layered).** Tool-level typed errors (RateLimited/NotFound/ExecFailed) with
per-type retry/backoff; agent-level `FailedResult` that the Planner routes (retry / reroute /
degrade / ask-human); run-level unrecoverable failures checkpoint and surface the full trace.
**Golden rule:** partial progress is always persisted — a crash never loses ingested papers or
written memories.

**Observability is a feature, not an afterthought.** OpenTelemetry spans across
API→orchestrator→agent→tool; LLM tracing (prompts/tokens/cost per node); and a **Reasoning Trace**
rendered from the event log — every paper considered, every one rejected and why. This transparency
*is* the trust story.

---

## 9. Evaluation framework

A serious research-infra project measures itself, from day one.

| Capability | Metric | Method |
|---|---|---|
| Retrieval | recall@k vs curated gold seminal-paper sets | offline benchmark topics |
| Research card | factual grounding (every claim → source span) | LLM-judge + human spot-check |
| Idea generation | novelty + feasibility (blind) | Critic + human rubric |
| Reviewer | agreement with real reviews (OpenReview) | correlation |
| Memory | quality with consolidation/forgetting on/off | ablation |
| End-to-end | task success on scripted scenarios | replayable suite |

Because every run is an event log, **evals are replayable**. `benchmarks/` ships a frozen
suite (19-paper corpus, 4 topics) measuring **recall@k, grounding@k, and MRR** for every
`RetrievalStrategy` (vector / graph / hybrid); it runs in CI with per-scenario thresholds
so retrieval regressions across model/strategy changes fail the build.

---

## 10. Where this design could be wrong (self-critique)

1. **Multi-agent may be overkill** — a strong single agent with good tools might match a 6-agent
   system at far less complexity. *Mitigation:* the interface supports both; MVP proves value with
   2 agents first.
2. **Three databases is heavy for self-hosters.** *Mitigation:* the foundation runs on
   SQLite + embedded Qdrant (even single-container); Neo4j/Postgres are opt-in.
3. **The Experiment Agent is a research project unto itself.** *Mitigation:* scoped last,
   sandboxed, shippable first as assisted (human-run) reproduction.
4. **LLM-judge evals are noisy/gameable.** *Mitigation:* anchor every capability to ≥1 objective
   metric plus human spot-checks.
5. **Ambition vs. focus** — the real failure mode is 20% of ten features. *Mitigation:* the roadmap
   is depth-first: a complete, trustworthy literature system beats a shallow full pipeline.
