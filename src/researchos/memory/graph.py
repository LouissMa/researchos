"""Structural memory tier — a knowledge graph behind the ``GraphStore`` interface.

Implements ADR-0003 (graph-in-SQLite first, Neo4j later): typed nodes and edges where
**every edge carries provenance + confidence** and ungrounded edges are rejected at write
time (ARCHITECTURE.md §5 anti-hallucination rule).

The graph is rebuilt from each run's landscape in two deterministic phases:

- **skeleton** (:meth:`GraphMemory.write_skeleton`) — reset the project's graph, then
  write paper nodes + keyword-grounded ``RELATED_TO`` edges. Runs right after ingestion,
  *before* ranking, so hybrid retrieval sees a corpus-deterministic graph and rankings
  stay reproducible across runs.
- **landscape** (:meth:`GraphMemory.write_landscape`) — merge concept nodes and
  cluster-grounded edges (``BELONGS_TO``, co-cluster ``RELATED_TO``) on top of the
  skeleton once clusters exist.

Retrieval (:meth:`SqliteGraphStore.search`) keyword-seeds paper *and* concept nodes, then
traverses edges weighted by confidence — a structural signal distinct from embeddings.
"""

from __future__ import annotations

import re

from sqlalchemy import delete, select

from researchos.core.interfaces import GraphStore
from researchos.core.models import GraphEdge, GraphNode
from researchos.core.state import ResearchState
from researchos.persistence.db import get_session
from researchos.persistence.models import KGEdgeRow, KGNodeRow

_TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "our",
    "can",
    "using",
    "used",
    "use",
    "based",
    "via",
    "such",
    "which",
    "these",
    "than",
    "into",
    "also",
    "paper",
    "papers",
    "method",
    "methods",
    "model",
    "models",
    "approach",
    "approaches",
    "results",
    "result",
    "show",
    "shows",
    "propose",
    "proposed",
    "novel",
    "new",
    "learning",
    "task",
    "tasks",
    "data",
    "we",
    "in",
    "on",
    "of",
    "to",
    "a",
    "an",
    "is",
    "as",
    "by",
    "research",
    "study",
    "studies",
    "system",
    "systems",
}

_PROVENANCE_KEYS = ("source_paper", "span", "tool")
_RELATIONS = frozenset(
    {
        "BELONGS_TO",
        "RELATED_TO",
        "CITES",
        "USES_METHOD",
        "EVALUATED_ON",
        "IMPROVES_ON",
        "CONTRADICTS",
        "INTRODUCES",
        "ADDRESSES",
        "DERIVED_FROM",
        "PART_OF",
        "SUPPORTS",
        "REFUTES",
    }
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


def _top_tokens(text: str, top: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for tok in tokenize(text):
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [tok for tok, _ in ranked[:top]]


def _node_id(project_id: str, node_type: str, ref_id: str) -> str:
    return f"{project_id}:{node_type}:{ref_id}"


class SqliteGraphStore:
    """Graph-in-SQLite: the reference ``GraphStore`` implementation (ADR-0003)."""

    # ------------------------------------------------------------ writes
    def clear(self, project_id: str) -> None:
        """Reset the project's structural tier (rebuild per run, see module docstring)."""
        with get_session() as s:
            s.execute(delete(KGNodeRow).where(KGNodeRow.project_id == project_id))
            s.execute(delete(KGEdgeRow).where(KGEdgeRow.project_id == project_id))
            s.commit()

    def upsert_nodes(self, nodes: list[GraphNode], project_id: str) -> int:
        n = 0
        with get_session() as s:
            for node in nodes:
                row = s.get(KGNodeRow, node.id)
                if row is None:
                    s.add(
                        KGNodeRow(
                            id=node.id,
                            project_id=project_id,
                            node_type=node.node_type,
                            ref_id=node.ref_id,
                            label=node.label,
                            properties=node.properties,
                        )
                    )
                    n += 1
                else:
                    row.label = node.label
                    row.properties = node.properties
            s.commit()
        return n

    def upsert_edges(self, edges: list[GraphEdge], project_id: str) -> int:
        """Validate provenance/confidence, then upsert idempotently per (relation, pair)."""
        n = 0
        with get_session() as s:
            for edge in edges:
                self._validate(edge)
                existing = s.scalars(
                    select(KGEdgeRow).where(
                        KGEdgeRow.project_id == project_id,
                        KGEdgeRow.relation == edge.relation,
                        KGEdgeRow.source_id == edge.source_id,
                        KGEdgeRow.target_id == edge.target_id,
                    )
                ).first()
                if existing is None:
                    s.add(
                        KGEdgeRow(
                            project_id=project_id,
                            relation=edge.relation,
                            source_id=edge.source_id,
                            target_id=edge.target_id,
                            provenance=edge.provenance,
                            confidence=edge.confidence,
                        )
                    )
                    n += 1
                else:
                    existing.provenance = edge.provenance
                    existing.confidence = edge.confidence
            s.commit()
        return n

    @staticmethod
    def _validate(edge: GraphEdge) -> None:
        if edge.relation not in _RELATIONS:
            raise ValueError(
                f"Unknown graph relation {edge.relation!r} (allowed: {sorted(_RELATIONS)})"
            )
        if not any(key in edge.provenance for key in _PROVENANCE_KEYS):
            raise ValueError(
                f"Ungrounded edge rejected: {edge.relation} {edge.source_id}->{edge.target_id} "
                "needs provenance (source_paper / span / tool)"
            )
        if not 0.0 <= edge.confidence <= 1.0:
            raise ValueError(f"Confidence out of range for {edge.relation}: {edge.confidence}")

    # ------------------------------------------------------------- reads
    def stats(self, project_id: str) -> dict:
        with get_session() as s:
            nodes = list(s.scalars(select(KGNodeRow).where(KGNodeRow.project_id == project_id)))
            edges = list(s.scalars(select(KGEdgeRow).where(KGEdgeRow.project_id == project_id)))
        by_type: dict[str, int] = {}
        for n in nodes:
            by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
        return {"nodes": len(nodes), "edges": len(edges), "by_type": by_type}

    def nodes(
        self, project_id: str, node_type: str | None = None, limit: int = 200
    ) -> list[GraphNode]:
        with get_session() as s:
            stmt = select(KGNodeRow).where(KGNodeRow.project_id == project_id)
            if node_type:
                stmt = stmt.where(KGNodeRow.node_type == node_type)
            stmt = stmt.order_by(KGNodeRow.label).limit(limit)
            rows = s.scalars(stmt).all()
        return [
            GraphNode(
                id=r.id,
                node_type=r.node_type,
                ref_id=r.ref_id,
                label=r.label,
                properties=r.properties,
            )
            for r in rows
        ]

    def edges(
        self, project_id: str, relation: str | None = None, limit: int = 200
    ) -> list[GraphEdge]:
        with get_session() as s:
            stmt = select(KGEdgeRow).where(KGEdgeRow.project_id == project_id)
            if relation:
                stmt = stmt.where(KGEdgeRow.relation == relation)
            stmt = stmt.order_by(KGEdgeRow.id.desc()).limit(limit)
            rows = s.scalars(stmt).all()
        return [
            GraphEdge(
                relation=r.relation,
                source_id=r.source_id,
                target_id=r.target_id,
                provenance=r.provenance,
                confidence=r.confidence,
            )
            for r in rows
        ]

    # --------------------------------------------------------- analytics
    def centrality(self, project_id: str, limit: int = 20) -> list[tuple[str, int, float]]:
        """Degree centrality — top-connected nodes (seminal-paper candidates).

        Edges are treated as undirected and de-duplicated per node pair, so degrees stay
        bounded by the node count. Returns ``(node_id, degree, normalized)`` best-first.
        Lightweight stand-in for Neo4j centrality until multi-hop analytics dominate
        (ADR-0003).
        """
        with get_session() as s:
            edges = list(s.scalars(select(KGEdgeRow).where(KGEdgeRow.project_id == project_id)))
        pairs = {frozenset((e.source_id, e.target_id)) for e in edges}
        degrees: dict[str, int] = {}
        for a, b in pairs:
            degrees[a] = degrees.get(a, 0) + 1
            degrees[b] = degrees.get(b, 0) + 1
        n = max(len(degrees), 2)
        ranked = sorted(degrees.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(nid, d, round(d / (n - 1), 3)) for nid, d in ranked[:limit]]

    def components(self, project_id: str) -> list[list[str]]:
        """Connected components over the graph — lightweight community detection."""
        with get_session() as s:
            nodes = list(s.scalars(select(KGNodeRow).where(KGNodeRow.project_id == project_id)))
            edges = list(s.scalars(select(KGEdgeRow).where(KGEdgeRow.project_id == project_id)))
        parent = {n.id: n.id for n in nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for e in edges:
            if e.source_id in parent and e.target_id in parent:
                union(e.source_id, e.target_id)
        groups: dict[str, list[str]] = {}
        for nid in parent:
            groups.setdefault(find(nid), []).append(nid)
        comps = sorted(groups.values(), key=len, reverse=True)
        return [sorted(c) for c in comps]

    # ---------------------------------------------------------- retrieval
    def search(self, query: str, k: int, project_id: str) -> list[tuple[str, float]]:
        """Structural retrieval: keyword-seed nodes, then traverse weighted edges.

        Concept seeds fan out to their member papers via ``BELONGS_TO``; paper seeds
        propagate through ``RELATED_TO`` one hop. Returns ``(paper_id, score)``.
        """
        qset = set(tokenize(query))
        if not qset:
            return []
        with get_session() as s:
            nodes = list(s.scalars(select(KGNodeRow).where(KGNodeRow.project_id == project_id)))
            edges = list(s.scalars(select(KGEdgeRow).where(KGEdgeRow.project_id == project_id)))
        if not nodes:
            return []

        info = {n.id: (n.node_type, n.ref_id, n.label, n.properties or {}) for n in nodes}
        paper_of = {
            nid: ref for nid, (ntype, ref, _label, _props) in info.items() if ntype == "paper"
        }
        outgoing: dict[str, list[tuple[str, float]]] = {}
        for e in edges:
            outgoing.setdefault(e.source_id, []).append((e.target_id, e.confidence))

        seed: dict[str, float] = {}
        for nid, (_ntype, _ref, label, props) in info.items():
            matched = sum(
                1
                for t in set(tokenize(label) + tokenize(" ".join(props.get("keywords", []))))
                if t in qset
            )
            if matched:
                seed[nid] = matched / max(len(qset), 1)

        scores: dict[str, float] = {}
        for nid, sc in seed.items():
            ntype, ref_id = info[nid][0], info[nid][1]
            if ntype == "paper":
                scores[ref_id] = max(scores.get(ref_id, 0.0), sc)
                for nb, conf in outgoing.get(nid, []):
                    if nb in paper_of:  # one hop through RELATED_TO
                        scores[paper_of[nb]] = max(scores.get(paper_of[nb], 0.0), sc * conf * 0.9)
            elif ntype == "concept":
                for nb, conf in outgoing.get(nid, []):
                    if nb not in paper_of:
                        continue
                    scores[paper_of[nb]] = max(scores.get(paper_of[nb], 0.0), sc * conf)
                    for nb2, conf2 in outgoing.get(nb, []):  # members' neighbors
                        if nb2 in paper_of:
                            scores[paper_of[nb2]] = max(
                                scores.get(paper_of[nb2], 0.0),
                                sc * conf * conf2 * 0.8,
                            )

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:k]


class GraphMemory:
    """Builds the knowledge graph from a run's working state (nodes + grounded edges)."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    def write_skeleton(self, state: ResearchState) -> dict:
        """Phase 1 (pre-ranking): reset the graph, write paper nodes + keyword edges."""
        self._store.clear(state.project_id)
        nodes = self._paper_nodes(state)
        edges = self._keyword_edges(state)
        self._store.upsert_nodes(nodes, state.project_id)
        written = self._store.upsert_edges(edges, state.project_id)
        return {"written_nodes": len(nodes), "written_edges": written}

    def write_landscape(self, state: ResearchState) -> dict:
        """Phase 2 (post-clustering): merge concept nodes + cluster-grounded edges."""
        nodes = self._concept_nodes(state)
        edges = self._cluster_edges(state)
        self._store.upsert_nodes(nodes, state.project_id)
        written = self._store.upsert_edges(edges, state.project_id)
        return {"written_nodes": len(nodes), "written_edges": written}

    # ------------------------------------------------------------ builders
    def _paper_nodes(self, state: ResearchState) -> list[GraphNode]:
        return [
            GraphNode(
                id=_node_id(state.project_id, "paper", p.id),
                node_type="paper",
                ref_id=p.id,
                label=p.title,
                properties={
                    "year": p.year,
                    "source": p.source,
                    "keywords": _top_tokens(f"{p.title} {p.abstract}"),
                },
            )
            for p in state.papers.values()
        ]

    def _concept_nodes(self, state: ResearchState) -> list[GraphNode]:
        return [
            GraphNode(
                id=_node_id(state.project_id, "concept", c.id),
                node_type="concept",
                ref_id=c.id,
                label=c.label,
                properties={"keywords": c.keywords},
            )
            for c in state.clusters
        ]

    def _keyword_edges(self, state: ResearchState) -> list[GraphEdge]:
        """Paper→paper ``RELATED_TO`` grounded in shared keywords of the papers' own text."""
        papers = list(state.papers.values())
        kw = {p.id: set(_top_tokens(f"{p.title} {p.abstract}", top=12)) for p in papers}
        edges: list[GraphEdge] = []
        for i, a in enumerate(papers):
            for b in papers[i + 1 :]:
                overlap = len(kw[a.id] & kw[b.id])
                if overlap >= 2:
                    edges.append(
                        GraphEdge(
                            relation="RELATED_TO",
                            source_id=_node_id(state.project_id, "paper", a.id),
                            target_id=_node_id(state.project_id, "paper", b.id),
                            provenance={"tool": "knowledge.keywords", "source_paper": a.id},
                            confidence=min(0.9, 0.4 + 0.1 * overlap),
                        )
                    )
        return edges

    def _cluster_edges(self, state: ResearchState) -> list[GraphEdge]:
        """BELONGS_TO (paper→concept) and co-cluster RELATED_TO, grounded in clustering."""
        edges: list[GraphEdge] = []
        for cluster in state.clusters:
            concept_id = _node_id(state.project_id, "concept", cluster.id)
            for pid in cluster.paper_ids:
                paper_id = _node_id(state.project_id, "paper", pid)
                edges.append(
                    GraphEdge(
                        relation="BELONGS_TO",
                        source_id=paper_id,
                        target_id=concept_id,
                        provenance={"tool": "knowledge.cluster", "source_paper": pid},
                        confidence=1.0,
                    )
                )
        co_cluster: dict[str, set[str]] = {}
        for cluster in state.clusters:
            for pid in cluster.paper_ids:
                co_cluster.setdefault(pid, set()).update(cluster.paper_ids)
        for pid, peers in co_cluster.items():
            for peer in sorted(peers):
                if peer <= pid:  # skip self + duplicate pairs
                    continue
                edges.append(
                    GraphEdge(
                        relation="RELATED_TO",
                        source_id=_node_id(state.project_id, "paper", pid),
                        target_id=_node_id(state.project_id, "paper", peer),
                        provenance={"tool": "knowledge.cluster", "source_paper": pid},
                        confidence=0.8,
                    )
                )
        return edges
