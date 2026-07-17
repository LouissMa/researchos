"""SequentialOrchestrator — the dependency-free reference ``Orchestrator`` (ADR-0001).

Wires the subsystems, runs the planner, executes tasks by routing each to the owning
agent, applies typed state deltas, and emits a full event trace. LangGraph will provide
an alternative implementation of the same interface without touching agents.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from researchos.agents.knowledge import KnowledgeAgent
from researchos.agents.literature import LiteratureAgent
from researchos.config import Settings, get_settings
from researchos.core.state import ResearchState, TaskKind
from researchos.ingestion.embedding import get_embedding_provider
from researchos.ingestion.pdf import fetch_pdf_text
from researchos.llm.client import get_llm
from researchos.logging import get_logger
from researchos.memory.store import SemanticMemory
from researchos.memory.vector_store import QdrantVectorStore
from researchos.observability.events import Event, EventEmitter, EventType
from researchos.orchestration.planner import Planner
from researchos.orchestration.report import render_markdown
from researchos.persistence.db import init_db
from researchos.persistence.store import Store
from researchos.tools.base import ToolRegistry
from researchos.tools.factory import build_search_tools

log = get_logger(__name__)


class SequentialOrchestrator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        init_db(self.settings.db_path)

        # Embeddings — probe the true dimension so the vector store matches any provider.
        self.embedder = get_embedding_provider(self.settings)
        dim = len(self.embedder.embed(["dimension probe"])[0])
        self.vector_store = QdrantVectorStore(
            dim=dim,
            mode=self.settings.qdrant_mode,
            path=self.settings.qdrant_path,
            url=self.settings.qdrant_url,
        )
        self.memory = SemanticMemory(self.embedder, self.vector_store)
        self.llm = get_llm(self.settings)

        self.tools = ToolRegistry()
        search_tools = build_search_tools(self.settings)
        for tool in search_tools:
            self.tools.register(tool)

        self.literature = LiteratureAgent(search_tools, self.memory)
        self.knowledge = KnowledgeAgent(self.memory, self.embedder, self.llm)
        self.planner = Planner()
        self.store = Store()

        self._router = {
            TaskKind.SEARCH: self.literature,
            TaskKind.RANK: self.literature,
            TaskKind.INGEST: self.knowledge,
            TaskKind.CLUSTER: self.knowledge,
            TaskKind.CARD: self.knowledge,
            TaskKind.LANDSCAPE: self.knowledge,
        }
        self._events: list[Event] = []

    # ---------------------------------------------------------------- public
    def start_run(
        self,
        project_id: str,
        goal: str,
        *,
        limit: int = 20,
        top_cards: int = 5,
        on_event: Callable[[Event], None] | None = None,
    ) -> ResearchState:
        run_id = uuid.uuid4().hex[:16]
        state = ResearchState(project_id=project_id, run_id=run_id, goal=goal)
        self._events = []

        emitter = EventEmitter(run_id)
        emitter.subscribe(self._events.append)
        if on_event:
            emitter.subscribe(on_event)

        self.store.create_run(run_id, project_id, goal)
        emitter.emit("system", EventType.RUN_STARTED, {"goal": goal, "limit": limit})

        tasks = self.planner.plan(goal, limit=limit, top_cards=top_cards)
        emitter.emit("planner", EventType.PLAN_CREATED, {"tasks": [t.kind.value for t in tasks]})

        try:
            for task in tasks:
                state.step += 1
                if state.step > state.max_steps:
                    emitter.emit(
                        "system", EventType.AGENT_MESSAGE, {"text": "Step budget reached."}
                    )
                    break
                agent = self._router[task.kind]
                emitter.emit(
                    agent.role,
                    EventType.TASK_STARTED,
                    {"task": task.kind.value, "description": task.description},
                )

                result = agent.run(state, task)

                if not result.ok:
                    emitter.emit(
                        agent.role,
                        EventType.TASK_FINISHED,
                        {"task": task.kind.value, "ok": False, "error": result.error},
                    )
                    continue  # degrade, don't crash the run

                state.apply(result.delta)
                self._emit_step_events(emitter, agent.role, task.kind, result)
                emitter.emit(
                    agent.role,
                    EventType.TASK_FINISHED,
                    {"task": task.kind.value, "ok": True, "output": result.output},
                )

                # Optional PDF enrichment right after search (best-effort, off by default).
                if task.kind == TaskKind.SEARCH and self.settings.fetch_pdf:
                    self._enrich_pdfs(state, emitter)

            saved = self.store.save_papers(state)
            emitter.emit("system", EventType.MEMORY_WRITE, {"papers_persisted": saved})

            artifact_uri = self._write_report(state)
            emitter.emit(
                "system",
                EventType.ARTIFACT_SAVED,
                {"kind": "landscape_report", "uri": artifact_uri},
            )
            self.store.add_artifact(project_id, run_id, "landscape_report", artifact_uri)

            emitter.emit(
                "system",
                EventType.RUN_FINISHED,
                {"papers": len(state.papers), "clusters": len(state.clusters)},
            )
            self.store.finish_run(run_id, "completed")
        except Exception as exc:  # unrecoverable — persist partial progress + surface
            log.exception("Run %s failed", run_id)
            self.store.save_papers(state)
            emitter.emit("system", EventType.RUN_FAILED, {"error": str(exc)})
            self.store.finish_run(run_id, "failed")
            raise

        return state

    def stream(self):
        """Yield events from the most recent run (post-hoc). Live streaming uses
        the ``on_event`` callback in :meth:`start_run`."""
        yield from self._events

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _emit_step_events(emitter: EventEmitter, actor: str, kind: TaskKind, result) -> None:
        for tc in result.tool_calls:
            emitter.emit(actor, EventType.TOOL_CALL, {"tool": tc})
        for line in result.reasoning:
            emitter.emit(actor, EventType.AGENT_MESSAGE, {"text": line})
        if kind == TaskKind.SEARCH:
            emitter.emit(actor, EventType.PAPERS_FOUND, {"count": len(result.delta.add_papers)})
        if kind == TaskKind.INGEST:
            emitter.emit(
                actor,
                EventType.PAPERS_INGESTED,
                {"chunks": result.delta.scratch.get("ingested_chunks", 0)},
            )

    def _enrich_pdfs(self, state: ResearchState, emitter: EventEmitter) -> None:
        enriched = 0
        for paper in state.ranked_papers()[:5]:
            text = fetch_pdf_text(paper.pdf_url)
            if text:
                paper.full_text = text
                enriched += 1
        if enriched:
            self.memory.write_papers(state)  # re-index with body text
            emitter.emit("system", EventType.PAPERS_INGESTED, {"pdf_enriched": enriched})

    def _write_report(self, state: ResearchState) -> str:
        path = self.settings.artifacts_dir / f"{state.run_id}.md"
        path.write_text(render_markdown(state), encoding="utf-8")
        return str(path)
