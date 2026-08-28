"""Frozen offline retrieval benchmark (Roadmap Phase 2): recall@k + grounding.

Runs every retrieval strategy (``vector`` / ``graph`` / ``hybrid``) against the frozen
scenarios in ``benchmarks/scenarios.json`` over the frozen corpus in
``benchmarks/corpus.py`` — no network, no API keys. Prints a comparison table and exits
non-zero when a scenario's hybrid recall@k falls below its declared threshold, which
guards CI against retrieval regressions.

Usage:
    uv run python -m benchmarks.run_eval
    uv run python -m benchmarks.run_eval --strategy hybrid
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from benchmarks import corpus
from researchos.config import Settings
from researchos.core.models import Cluster, Paper
from researchos.core.state import ResearchState
from researchos.ingestion.embedding import LocalEmbeddingProvider
from researchos.memory.graph import GraphMemory, SqliteGraphStore, tokenize
from researchos.memory.retrieval import get_retrieval_strategy
from researchos.memory.store import SemanticMemory
from researchos.memory.vector_store import QdrantVectorStore
from researchos.persistence.db import close_db, init_db

_SCENARIOS = Path(__file__).resolve().parent / "scenarios.json"
_K = 5  # evaluation depth for recall@k / grounding@k
_STRATEGIES = ("vector", "graph", "hybrid")


def _papers() -> list[Paper]:
    return [Paper(**d).ensure_id() for d in corpus.PAPERS]


def _state(project_id: str) -> ResearchState:
    papers = _papers()
    by_title = {p.title: p for p in papers}
    clusters = [
        Cluster(
            id=c["id"],
            label=c["label"],
            keywords=c["keywords"],
            paper_ids=[by_title[t].id for t in c["titles"]],
        )
        for c in corpus.CLUSTERS
    ]
    return ResearchState(
        project_id=project_id,
        run_id="bench",
        goal="",
        papers={p.id: p for p in papers},
        clusters=clusters,
    )


def _build_memory(settings: Settings) -> tuple[SemanticMemory, SqliteGraphStore, QdrantVectorStore]:
    init_db(settings.db_path)
    embedder = LocalEmbeddingProvider(dim=settings.embedding_dim)
    dim = len(embedder.embed(["dimension probe"])[0])
    vector_store = QdrantVectorStore(dim=dim, mode="embedded", path=settings.qdrant_path)
    memory = SemanticMemory(embedder, vector_store)

    state = _state("bench")
    memory.write_papers(state)
    graph = SqliteGraphStore()
    builder = GraphMemory(graph)
    builder.write_skeleton(state)
    builder.write_landscape(state)
    return memory, graph, vector_store


def _retrievers(memory: SemanticMemory, graph: SqliteGraphStore):
    return {
        name: get_retrieval_strategy(name, vector_fn=memory.vector_retrieve, graph=graph)
        for name in _STRATEGIES
    }


def _token_overlap(query: str, text: str) -> float:
    """Fraction of query content tokens present in the text (grounding proxy)."""
    qtoks = set(tokenize(query))
    if not qtoks:
        return 0.0
    text_toks = set(tokenize(text))
    return len(qtoks & text_toks) / len(qtoks)


def _evaluate(scenario: dict, retrievers, papers_by_id: dict) -> dict:
    query = scenario["query"]
    gold = {next(p.id for p in papers_by_id.values() if p.title == t) for t in scenario["gold"]}
    results: dict[str, dict] = {}
    for name, retriever in retrievers.items():
        hits = retriever.retrieve(query, _K, "bench")
        top = [pid for pid, _score in hits]
        recalled = len(set(top) & gold)
        grounding = sum(
            _token_overlap(query, f"{papers_by_id[pid].title} {papers_by_id[pid].abstract}")
            for pid in top
        ) / max(len(top), 1)
        mrr = 0.0
        for rank, pid in enumerate(top, start=1):
            if pid in gold:
                mrr = 1.0 / rank
                break
        results[name] = {
            "recall@5": recalled / len(gold),
            "grounding@5": grounding,
            "mrr": mrr,
        }
    return results


def _print_table(results: dict, scenario_id: str) -> None:
    print(f"\nScenario: {scenario_id}")
    print(f"  {'strategy':<8} {'recall@5':<10} {'grounding@5':<13} {'mrr':<6}")
    for name, r in results.items():
        print(f"  {name:<8} {r['recall@5']:<10.3f} {r['grounding@5']:<13.3f} {r['mrr']:<6.3f}")


def run_benchmarks(strategy: str | None = None) -> bool:
    with tempfile.TemporaryDirectory(prefix="researchos_bench_") as tmp:
        settings = Settings(data_dir=Path(tmp), embedding_dim=256, qdrant_mode="embedded")
        memory, graph, vector_store = _build_memory(settings)
        try:
            retrievers = _retrievers(memory, graph)
            if strategy:
                retrievers = {strategy: retrievers[strategy]}
            papers_by_id = {p.id: p for p in _papers()}
            scenarios = json.loads(_SCENARIOS.read_text(encoding="utf-8"))["scenarios"]

            ok = True
            for sc in scenarios:
                results = _evaluate(sc, retrievers, papers_by_id)
                _print_table(results, sc["id"])
                if "hybrid" in results:
                    hybrid_recall = results["hybrid"]["recall@5"]
                    threshold = sc["recall_at_5_threshold"]
                    status = "PASS" if hybrid_recall >= threshold else "FAIL"
                    print(
                        f"  hybrid recall@5 {hybrid_recall:.3f} vs threshold {threshold} → {status}"
                    )
                    if status == "FAIL":
                        ok = False
            return ok
        finally:
            vector_store.close()  # release the on-disk storage lock before tmp cleanup
            close_db()  # release the SQLite engine handle before tmp cleanup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        choices=list(_STRATEGIES),
        help="Limit evaluation to a single strategy (default: all).",
    )
    args = parser.parse_args()
    ok = run_benchmarks(args.strategy)
    print("\n" + ("ALL SCENARIOS PASS" if ok else "BENCHMARK FAILURES — see table above"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
