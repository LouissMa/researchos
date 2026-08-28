"""Idea Agent 閳?gap analysis over the knowledge graph 閳?research proposals (Phase 3).

Owns the transition from "what we found" to "what's worth doing next". Every proposal is
**grounded** in the landscape: it cites the cluster ids / paper ids that support the gap
claim, so ideas are traceable rather than free-floating hunches.

Heuristic gap detectors (offline, deterministic):

- **cross-cluster bridge** 閳?pairs of themes with keyword overlap but no shared papers:
  combining them is a concrete integration hypothesis.
- **under-explored theme** 閳?clusters far below the median size: the search under-sampled
  a likely-relevant area.
- **recurring interest** 閳?themes matching the project's reflected interest profile:
  deepen what the user consistently reads.
- **isolated contribution** 閳?papers that share almost no vocabulary with the rest of the
  landscape: verify or connect them.

With an LLM configured, the same evidence is sent as a prompt and proposals come back
LLM-authored; otherwise (or on failure) the heuristics above run.
"""

from __future__ import annotations

import json

from researchos.agents.base import BaseAgent
from researchos.core.interfaces import LLM
from researchos.core.models import ResearchIdea, stable_id
from researchos.core.state import AgentResult, ResearchState, StateDelta, Task, TaskKind
from researchos.memory.graph import tokenize
from researchos.memory.manager import MemoryManager

_MAX_IDEAS = 4


def _keywords(cluster) -> set[str]:
    return set(tokenize(" ".join(cluster.keywords)))


def _paper_keywords(paper) -> set[str]:
    return set(tokenize(f"{paper.title} {paper.abstract}"))


class IdeaAgent(BaseAgent):
    role = "idea"

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def run(self, state: ResearchState, task: Task) -> AgentResult:
        if task.kind != TaskKind.IDEA:
            return self._result(ok=False, error=f"Idea agent cannot handle {task.kind}")
        return self._propose(state)

    # ------------------------------------------------------------ generation
    def _propose(self, state: ResearchState) -> AgentResult:
        if self._llm.available:
            ideas = self._llm_ideas(state)
            if ideas:
                return self._result(
                    output=f"Proposed {len(ideas)} research ideas (llm:{self._llm.name}).",
                    delta=StateDelta(add_ideas=ideas),
                    reasoning=[
                        "Gap analysis over the landscape clusters (LLM-authored proposals)."
                    ],
                )
        ideas = self._heuristic_ideas(state)
        return self._result(
            output=f"Proposed {len(ideas)} research ideas (heuristic).",
            delta=StateDelta(add_ideas=ideas),
            reasoning=[f"Heuristic gap analysis 閳?{len(ideas)} grounded proposals."]
            + [f"- {i.title}" for i in ideas],
        )

    # ------------------------------------------------------------ heuristics
    def _heuristic_ideas(self, state: ResearchState) -> list[ResearchIdea]:
        ideas: list[ResearchIdea] = []
        clusters = state.clusters
        papers = list(state.papers.values())

        # 1) Cross-cluster bridges.
        for i, a in enumerate(clusters):
            for b in clusters[i + 1 :]:
                shared = _keywords(a) & _keywords(b)
                if not shared or set(a.paper_ids) & set(b.paper_ids):
                    continue
                overlap = len(shared)
                ideas.append(
                    ResearchIdea(
                        id=stable_id("bridge", state.project_id, a.id, b.id),
                        title=f"Bridge '{a.label}' and '{b.label}'",
                        hypothesis=(
                            f"Combining techniques from '{a.label}' with the framework of "
                            f"'{b.label}' addresses a gap neither theme covers alone."
                        ),
                        rationale=(
                            f"The two themes share {overlap} keyword(s) "
                            f"({', '.join(sorted(shared)[:4])}) yet no paper connects them."
                        ),
                        gap=(
                            f"No paper bridges cluster '{a.label}' ({len(a.paper_ids)} papers) "
                            f"and cluster '{b.label}' ({len(b.paper_ids)} papers)."
                        ),
                        grounding=[a.id, b.id],
                        novelty=0.75,
                        feasibility=0.6,
                    )
                )

        # 2) Under-explored themes (well below the median cluster size).
        sizes = [len(c.paper_ids) for c in clusters]
        median = sorted(sizes)[len(sizes) // 2] if sizes else 0
        for c in clusters:
            if median > 1 and len(c.paper_ids) <= max(1, median // 2):
                ideas.append(
                    ResearchIdea(
                        id=stable_id("sparse", state.project_id, c.id),
                        title=f"Deepen the under-explored theme '{c.label}'",
                        hypothesis=(
                            f"'{c.label}' is likely under-sampled; a targeted search and "
                            f"re-read may surface missing seminal or recent work."
                        ),
                        rationale=(
                            f"Cluster '{c.label}' holds only {len(c.paper_ids)} paper(s) "
                            f"against a landscape median of {median}."
                        ),
                        gap=(
                            f"Under-represented theme: '{c.label}' "
                            f"(keywords: {', '.join(c.keywords) or 'n/a'})."
                        ),
                        grounding=[c.id],
                        novelty=0.5,
                        feasibility=0.7,
                    )
                )

        # 3) Recurring interest alignment.
        interests = self._interest_tokens(state.project_id)
        if interests:
            for c in clusters:
                match = _keywords(c) & interests
                if match:
                    ideas.append(
                        ResearchIdea(
                            id=stable_id("interest", state.project_id, c.id),
                            title=f"Extend the recurring interest '{c.label}'",
                            hypothesis=(
                                f"Deepening '{c.label}' aligns with the project's recurring "
                                f"interests ({', '.join(sorted(match))})."
                            ),
                            rationale=(
                                "The reflected interest profile consistently favors this area."
                            ),
                            gap=(
                                "Recurring interest "
                                f"'{', '.join(sorted(match))}' is not yet consolidated."
                            ),
                            grounding=[c.id],
                            novelty=0.45,
                            feasibility=0.8,
                        )
                    )

        # 4) Isolated contributions (share almost no vocabulary with the landscape).
        for p in papers:
            others = [q for q in papers if q.id != p.id]
            if not others:
                continue
            pk = _paper_keywords(p)
            max_overlap = max((len(pk & _paper_keywords(q)) for q in others), default=0)
            if max_overlap <= 1:
                ideas.append(
                    ResearchIdea(
                        id=stable_id("isolated", state.project_id, p.id),
                        title=f"Verify the isolated contribution: '{p.title[:60]}'",
                        hypothesis=(
                            "A paper disconnected from the rest of the landscape may be a "
                            "novel direction worth replicating or a tangential outlier."
                        ),
                        rationale=(
                            f"'{p.title[:60]}' shares at most {max_overlap} keyword(s) with "
                            f"every other paper in the landscape."
                        ),
                        gap="The landscape contains an isolated, unconnected contribution.",
                        grounding=[p.id],
                        novelty=0.4,
                        feasibility=0.7,
                    )
                )

        # Deterministic ordering, bounded output.
        ideas.sort(key=lambda i: (-i.novelty, i.title))
        return ideas[:_MAX_IDEAS]

    def _interest_tokens(self, project_id: str) -> set[str]:
        for item in MemoryManager().list_items(project_id, ref_type="interest", limit=5):
            if item.ref_id == "profile":
                return set(tokenize(item.content))
        return set()

    # ------------------------------------------------------------- LLM mode
    def _llm_ideas(self, state: ResearchState) -> list[ResearchIdea] | None:
        cluster_desc = "; ".join(
            f"{c.label} [{len(c.paper_ids)} papers: {', '.join(c.keywords)}]"
            for c in state.clusters
        )
        titles = "\n".join(f"- {p.title}" for p in state.ranked_papers()[:15])
        prompt = (
            f"Research goal: {state.goal}\n\nLandscape themes:\n{cluster_desc}\n\n"
            f"Top papers:\n{titles}\n\n"
            "Propose up to 3 concrete, novel research directions grounded in this landscape. "
            "Return a JSON array with objects: {title, hypothesis, rationale, gap, "
            "grounding (cluster labels or paper titles), novelty (0-1), feasibility (0-1)}."
        )
        try:
            raw = self._llm.complete(
                prompt,
                system="You are a research strategist. Only propose ideas supported by the "
                "provided landscape; never fabricate papers.",
            )
            data = json.loads(_extract_json(raw))
            ideas: list[ResearchIdea] = []
            for i, d in enumerate(data[:3]):
                grounding = [str(g) for g in d.get("grounding", [])]
                ideas.append(
                    ResearchIdea(
                        id=stable_id("llm", state.project_id, state.run_id, str(i)),
                        title=str(d.get("title", "Untitled idea")),
                        hypothesis=str(d.get("hypothesis", "")),
                        rationale=str(d.get("rationale", "")),
                        gap=str(d.get("gap", "")),
                        grounding=grounding,
                        novelty=float(d.get("novelty", 0.5)),
                        feasibility=float(d.get("feasibility", 0.5)),
                        generated_by=f"llm:{self._llm.name}",
                    )
                )
            return ideas
        except Exception:
            return None


def _extract_json(raw: str) -> str:
    """Best-effort: pull the first [...] or {...} block out of an LLM response."""
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end <= start:
        start = raw.find("{")
        end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw
