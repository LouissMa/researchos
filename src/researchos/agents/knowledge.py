"""Knowledge Agent — memory writes, clustering, research cards, and the landscape.

Owns knowledge organization. Clustering and centrality use the embedding provider;
research cards use the LLM when available and fall back to honest heuristics otherwise.
"""

from __future__ import annotations

import json
import re

import numpy as np

from researchos.agents.base import BaseAgent
from researchos.core.interfaces import LLM, EmbeddingProvider
from researchos.core.models import Cluster, Landscape, Paper, ResearchCard
from researchos.core.state import AgentResult, ResearchState, StateDelta, Task, TaskKind
from researchos.memory.store import SemanticMemory
from researchos.tools.base import BaseTool

_TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")
_STOPWORDS = {
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
}

_CARD_SYSTEM = (
    "You are a meticulous research analyst. Read the paper metadata and produce a structured "
    "research card. Base every field ONLY on the provided text; if unknown, say 'unknown'. "
    "Respond with a single JSON object and no prose."
)


class KnowledgeAgent(BaseAgent):
    role = "knowledge"

    def __init__(
        self,
        memory: SemanticMemory,
        embedder: EmbeddingProvider,
        llm: LLM,
        code_tool: BaseTool | None = None,
    ) -> None:
        self._memory = memory
        self._embedder = embedder
        self._llm = llm
        self._code_tool = code_tool

    def run(self, state: ResearchState, task: Task) -> AgentResult:
        if task.kind == TaskKind.INGEST:
            return self._ingest(state)
        if task.kind == TaskKind.CLUSTER:
            return self._cluster(state)
        if task.kind == TaskKind.CARD:
            return self._cards(state, task)
        if task.kind == TaskKind.CODE:
            return self._code(state, task)
        if task.kind == TaskKind.LANDSCAPE:
            return self._landscape(state)
        return self._result(ok=False, error=f"Knowledge agent cannot handle {task.kind}")

    # ----------------------------------------------------------------- code
    def _code(self, state: ResearchState, task: Task) -> AgentResult:
        if self._code_tool is None:
            return self._result(output="Code discovery disabled (no GitHub tool).")
        n = int(task.payload.get("top_n", 3))
        targets = [state.papers[pid] for pid in state.ranking[:n] if pid in state.papers]
        enriched: list[Paper] = []
        found = 0
        for paper in targets:
            # GitHub repo search rarely matches a full paper title; use the salient
            # leading words (drops trailing subtitles) for a better hit rate.
            query = " ".join(paper.title.split(":")[0].split()[:6])
            result = self._code_tool.invoke(query=query, limit=2)
            if not result.ok or not result.data:
                continue
            urls = [r["url"] for r in result.data if r.get("url")]
            if urls:
                updated = paper.model_copy(update={"code_urls": urls})
                enriched.append(updated)
                found += 1
        return self._result(
            output=f"Linked GitHub code for {found}/{len(targets)} key papers.",
            delta=StateDelta(add_papers=enriched),
            reasoning=[f"Searched GitHub for implementations of {len(targets)} key papers."],
            tool_calls=[self._code_tool.name] if targets else [],
        )

    # --------------------------------------------------------------- ingest
    def _ingest(self, state: ResearchState) -> AgentResult:
        n = self._memory.write_papers(state)
        return self._result(
            output=f"Wrote {n} chunks to semantic memory.",
            delta=StateDelta(scratch={"ingested_chunks": n}),
            reasoning=[f"Embedded and indexed {len(state.papers)} papers ({n} chunks)."],
        )

    # -------------------------------------------------------------- cluster
    def _cluster(self, state: ResearchState) -> AgentResult:
        papers = state.ranked_papers()
        if len(papers) < 2:
            cluster = Cluster(id="c0", label="all", paper_ids=[p.id for p in papers])
            return self._result(
                output="Single cluster (too few papers to partition).",
                delta=StateDelta(add_clusters=[cluster]),
            )
        texts = [f"{p.title}. {p.abstract}" for p in papers]
        vectors = np.asarray(self._embedder.embed(texts), dtype=np.float32)
        k = max(2, min(5, len(papers) // 3))
        labels = _kmeans(vectors, k)
        clusters: list[Cluster] = []
        for c in range(int(labels.max()) + 1):
            members = [papers[i] for i in range(len(papers)) if labels[i] == c]
            if not members:
                continue
            keywords = _cluster_keywords(members)
            clusters.append(
                Cluster(
                    id=f"c{c}",
                    label=" / ".join(keywords) or f"cluster {c}",
                    keywords=keywords,
                    paper_ids=[p.id for p in members],
                )
            )
        return self._result(
            output=f"Organized papers into {len(clusters)} thematic clusters.",
            delta=StateDelta(add_clusters=clusters),
            reasoning=[f"k-means over paper embeddings (k={k}) → {len(clusters)} clusters."]
            + [f"Cluster {c.id}: {c.label} ({len(c.paper_ids)} papers)" for c in clusters],
        )

    # ---------------------------------------------------------------- cards
    def _cards(self, state: ResearchState, task: Task) -> AgentResult:
        n = int(task.payload.get("top_n", 5))
        targets = [state.papers[pid] for pid in state.ranking[:n] if pid in state.papers]
        cards = [self._make_card(p) for p in targets]
        mode = self._llm.name if self._llm.available else "heuristic"
        return self._result(
            output=f"Generated {len(cards)} research cards ({mode}).",
            delta=StateDelta(add_cards=cards),
            reasoning=[f"Built cards for the top {len(cards)} papers using {mode}."],
        )

    def _make_card(self, paper: Paper) -> ResearchCard:
        if self._llm.available:
            card = self._llm_card(paper)
            if card is not None:
                return card
        return _heuristic_card(paper)

    def _llm_card(self, paper: Paper) -> ResearchCard | None:
        prompt = (
            f"Title: {paper.title}\n"
            f"Authors: {', '.join(paper.authors[:8])}\n"
            f"Abstract: {paper.abstract}\n\n"
            "Return JSON with keys: problem, motivation, key_idea, method, results, "
            "limitations, future_work, repro_difficulty (low|medium|high|unknown), opportunities."
        )
        try:
            raw = self._llm.complete(prompt, system=_CARD_SYSTEM)
            data = json.loads(_extract_json(raw))
            return ResearchCard(
                paper_id=paper.id,
                problem=str(data.get("problem", "")),
                motivation=str(data.get("motivation", "")),
                key_idea=str(data.get("key_idea", "")),
                method=str(data.get("method", "")),
                results=str(data.get("results", "")),
                limitations=str(data.get("limitations", "")),
                future_work=str(data.get("future_work", "")),
                repro_difficulty=str(data.get("repro_difficulty", "unknown")),
                opportunities=str(data.get("opportunities", "")),
                generated_by=f"llm:{self._llm.name}",
            )
        except Exception:
            return None

    # ------------------------------------------------------------ landscape
    def _landscape(self, state: ResearchState) -> AgentResult:
        ranking = state.ranking or list(state.papers)
        key_papers = ranking[:5]
        remaining = [pid for pid in ranking if pid not in key_papers]
        remaining.sort(key=lambda pid: state.papers[pid].year or 9999)  # older/foundational first
        reading_order = key_papers + remaining
        summary = self._landscape_summary(state)
        landscape = Landscape(
            query=state.goal,
            summary=summary,
            clusters=state.clusters,
            key_papers=key_papers,
            reading_order=reading_order,
        )
        return self._result(
            output="Assembled the research landscape.",
            delta=StateDelta(set_landscape=landscape),
            reasoning=[
                f"Selected {len(key_papers)} key papers (top relevance).",
                "Reading order: key papers first, then foundational→recent within the field.",
            ],
        )

    def _landscape_summary(self, state: ResearchState) -> str:
        n = len(state.papers)
        cluster_desc = "; ".join(f"{c.label} ({len(c.paper_ids)})" for c in state.clusters)
        if self._llm.available:
            titles = "\n".join(f"- {p.title}" for p in state.ranked_papers()[:15])
            prompt = (
                f"Research goal: {state.goal}\n\nTop papers:\n{titles}\n\n"
                f"Themes: {cluster_desc}\n\n"
                "Write a concise (120-180 word) research landscape: historical development, key "
                "methods, current challenges, and open opportunities. Plain prose, no lists."
            )
            out = self._llm.complete(prompt, system="You are a senior researcher writing a survey.")
            if out:
                return out
        return (
            f"Landscape for '{state.goal}': {n} papers organized into {len(state.clusters)} "
            f"themes — {cluster_desc}. Enable an LLM (RESEARCHOS_LLM_PROVIDER=openai) for a "
            f"narrative synthesis of development, methods, challenges, and opportunities."
        )


# ----------------------------------------------------------------- helpers
def _kmeans(x: np.ndarray, k: int, iters: int = 25, seed: int = 0) -> np.ndarray:
    """Tiny, deterministic k-means. Returns integer cluster labels."""
    n = x.shape[0]
    if k >= n:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    centroids = x[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for step in range(iters):
        dists = ((x[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        new_labels = dists.argmin(axis=1)
        if step > 0 and np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for c in range(k):
            members = x[labels == c]
            if len(members) > 0:
                centroids[c] = members.mean(axis=0)
    return labels


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _cluster_keywords(papers: list[Paper], top: int = 3) -> list[str]:
    counts: dict[str, int] = {}
    for p in papers:
        for tok in set(_tokens(f"{p.title} {p.abstract}")):
            counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [tok for tok, _ in ranked[:top]]


def _heuristic_card(paper: Paper) -> ResearchCard:
    sentences = re.split(r"(?<=[.!?])\s+", paper.abstract.strip())
    problem = sentences[0] if sentences and sentences[0] else "unknown"
    key_idea = " ".join(sentences[1:3]) if len(sentences) > 1 else paper.abstract[:300]
    return ResearchCard(
        paper_id=paper.id,
        problem=problem,
        motivation="unknown (heuristic card — enable an LLM for motivation analysis)",
        key_idea=key_idea or paper.abstract[:300],
        method="See full paper. Enable PDF ingestion + LLM for method extraction.",
        results="unknown",
        limitations="unknown",
        future_work="unknown",
        repro_difficulty="unknown",
        opportunities="unknown",
        generated_by="heuristic",
    )


def _extract_json(raw: str) -> str:
    """Best-effort: pull the first {...} block out of an LLM response."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return raw
