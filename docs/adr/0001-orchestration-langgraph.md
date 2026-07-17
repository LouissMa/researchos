# ADR-0001: LangGraph for orchestration, behind our own interface

- **Status:** Accepted
- **Date:** 2026-07-17
- **Context tags:** orchestration, agents, reproducibility

## Context

ResearchOS runs long, branchy, interruptible workflows (a run may pause for hours awaiting human
approval, then resume). We need explicit control flow, durable checkpoints, human-in-the-loop
interrupts, a shared typed state passed between steps, and streaming of intermediate steps for the
reasoning-trace UI.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **LangGraph** | explicit graph, durable checkpoints, HITL interrupts, typed shared state, step streaming | verbose; LangChain gravity |
| CrewAI / AutoGen | fast to prototype role-play agents | conversation-centric; weak durable state & checkpointing → hurts reproducibility |
| Plain asyncio state machine | zero deps, full control | we'd rebuild checkpointing + interrupts |
| Temporal / durable workflow | industrial-grade durability | overkill for v1 |

## Decision

Use **LangGraph** as the orchestration backbone — but **wrap it behind our own `Orchestrator`
interface** so agents never import LangGraph types. This lets us swap to a hand-rolled state
machine or a Temporal-backed engine later without touching agent business logic.

The runnable foundation ships a dependency-free `SequentialOrchestrator` implementing the same
`Orchestrator` interface, so the system runs today and LangGraph can be introduced as a drop-in.

## Consequences

- **Positive:** durability/HITL/streaming come mostly for free; agents stay portable; we can
  benchmark orchestration strategies.
- **Negative:** an extra indirection layer; two orchestrator implementations to keep in sync
  against the interface.
- **Revisit when:** runs become month-long campaigns (→ Temporal) or LangGraph limits our control
  flow.
