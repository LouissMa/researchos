# ADR-0002: Four-tier memory with explicit reflection/consolidation/forgetting

- **Status:** Accepted
- **Date:** 2026-07-17
- **Context tags:** memory, retrieval, research-value

## Context

A research collaborator must have durable, structured memory — not a stateless RAG pass. Most
comparable projects stop at "embed PDFs, do vector search." That neither models how knowledge
connects nor keeps the working set sharp over months of use.

## Decision

Adopt a **four-tier** memory model with a uniform `MemoryStore` interface:

- **Working** — current run's `ResearchState` + conversation window (volatile, token-bounded).
- **Episodic** — append-only event log; the source of truth for replay and reflection.
- **Semantic** — vector store (Qdrant) of papers/notes/concepts/cards.
- **Structural** — knowledge graph of typed, provenance-carrying relations.

And **four operations** as first-class, swappable strategies:

- **Retrieval** — hybrid vector + graph + metadata; strategy chosen per query and benchmarkable.
- **Reflection** — periodic/Critic-triggered derivation of higher-level memories from episodic log.
- **Consolidation** — dedup + summarize near-duplicates into concept nodes.
- **Forgetting** — salience decay `f(recency, access, pin, project_relevance)`; demote, don't delete.

## Consequences

- **Positive:** this is genuine research infrastructure — retrieval/memory strategies become
  measurable experiment axes (a paper's worth of ablations for free); context stays small; the
  system explains what it knows and why.
- **Negative:** more moving parts than plain RAG; consolidation/forgetting policies need tuning and
  evaluation to avoid dropping useful memories.
- **Foundation scope:** ships semantic (vector) retrieval + episodic event log. Reflection,
  consolidation, forgetting, and the structural tier land in Phase 2/3 behind the same interface.
