# ADR-0003: Knowledge graph on Postgres first, Neo4j later

- **Status:** Accepted
- **Date:** 2026-07-17
- **Context tags:** knowledge-graph, persistence, ops-cost

## Context

ResearchOS models a knowledge graph (papers, methods, datasets, concepts, and typed relations).
The obvious choice is Neo4j. But an early-stage, self-hostable open-source project pays a real
operational tax for every extra stateful service, and most early queries are shallow.

## Decision

Ship the knowledge graph as **graph-in-Postgres** (an `edge` table with recursive CTEs) behind a
`GraphStore` interface. Introduce **Neo4j** as a drop-in implementation in Phase 3, when:

1. multi-hop queries (3+ hops, e.g. method-evolution chains) dominate, **and**
2. graph algorithms become core UX — centrality to surface seminal papers, community detection to
   discover sub-fields.

Every edge carries `provenance` (source paper + span or asserting tool) and `confidence`;
ungrounded edges are rejected at write time, regardless of backend.

## Consequences

- **Positive:** the foundation runs with just SQLite/Postgres + embedded Qdrant — even a single
  container. No premature ops burden. Agents are unaffected by the backend swap.
- **Negative:** recursive CTEs are clunkier than Cypher and won't scale to deep analytics — which
  is exactly the trigger to adopt Neo4j.
- **Revisit when:** the triggers above are met, or graph size/latency degrades CTE queries.
