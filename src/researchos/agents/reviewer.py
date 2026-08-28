"""Reviewer — assesses a single paper's research card (Phase 3).

Produces strengths / weaknesses / novelty / feasibility / score, the same shape a real
reviewer gives. Heuristic mode is fully offline and deterministic (feature-based);
with an LLM configured the card + abstract go to the model and come back as a review,
falling back to heuristics on any failure.

Novelty is measured against a *context*: the other papers of the same project (or the
frozen benchmark corpus), so "novel" means "shares little vocabulary with what we
already know" — traceable, not vibes.
"""

from __future__ import annotations

import json
import re

from researchos.core.interfaces import LLM
from researchos.core.models import Paper, PaperReview, ResearchCard
from researchos.memory.graph import tokenize

_CARD_FIELDS = (
    "problem",
    "motivation",
    "key_idea",
    "method",
    "results",
    "limitations",
    "future_work",
    "opportunities",
)

_FEASIBILITY = {"low": 0.8, "medium": 0.6, "high": 0.3, "unknown": 0.5}

_EVIDENCE_RE = re.compile(r"\d+(\.\d+)?\s*%|\b(accuracy|outperform|improve|gain|speedup)\b")


def _is_unknown(value: str) -> bool:
    return not value or value.lower().startswith("unknown")


class Reviewer:
    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def review(
        self,
        paper: Paper,
        card: ResearchCard,
        context: list[Paper] | None = None,
    ) -> PaperReview:
        """Review one paper against its card (and optionally the surrounding corpus)."""
        if self._llm.available:
            review = self._llm_review(paper, card)
            if review is not None:
                return review
        return self._heuristic_review(paper, card, context or [])

    # ------------------------------------------------------------ heuristics
    def _heuristic_review(
        self, paper: Paper, card: ResearchCard, context: list[Paper]
    ) -> PaperReview:
        filled = [f for f in _CARD_FIELDS if not _is_unknown(str(getattr(card, f, "")))]
        fill_ratio = len(filled) / len(_CARD_FIELDS)

        sentences = [s for s in re.split(r"(?<=[.!?])\s+", paper.abstract.strip()) if s]
        depth = min(1.0, len(sentences) / 4)
        evidence = bool(_EVIDENCE_RE.search(paper.abstract))

        score = min(
            10.0,
            fill_ratio * 3.0  # card completeness
            + depth * 3.0  # abstract depth
            + (2.0 if evidence else 0.0)  # quantitative claims
            + (2.0 if not _is_unknown(card.method) else 0.0),  # method defined
        )
        score = round(score, 1)

        novelty = self._novelty(paper, context)
        feasibility = _FEASIBILITY.get(card.repro_difficulty, 0.5)
        if _is_unknown(card.method):
            feasibility = round(feasibility * 0.8, 2)

        strengths = [
            f"Clear {f.replace('_', ' ')} reported" for f in ("problem", "key_idea") if f in filled
        ]
        if not _is_unknown(card.method):
            strengths.append("Concrete method described")
        if not _is_unknown(card.results):
            strengths.append("Empirical results provided")
        if evidence:
            strengths.append("Contains quantitative evidence")
        if not strengths:
            strengths = ["Card is extractive-only; an LLM review would deepen it"]

        missing = [f for f in _CARD_FIELDS if f not in filled]
        weaknesses = [f"{f.replace('_', ' ')} not reported" for f in missing] or [
            "Card is shallow — no qualitative fields filled"
        ]

        summary = next(
            (s for s in (card.key_idea, card.problem) if not _is_unknown(s)), ""
        ).strip()[:200]

        return PaperReview(
            paper_id=paper.id,
            summary=summary,
            strengths=strengths[:4],
            weaknesses=weaknesses[:4],
            novelty=round(novelty, 2),
            feasibility=round(feasibility, 2),
            score=score,
        )

    @staticmethod
    def _novelty(paper: Paper, context: list[Paper]) -> float:
        """1 - max query-token overlap with the context corpus (lexical, deterministic)."""
        pk = set(tokenize(f"{paper.title} {paper.abstract}"))
        if not pk or not context:
            return 0.5
        max_overlap = 0.0
        for other in context:
            if other is paper:
                continue
            if other.id and other.id == paper.id:
                continue
            ok = set(tokenize(f"{other.title} {other.abstract}"))
            if ok:
                max_overlap = max(max_overlap, len(pk & ok) / len(pk))
        return 1.0 - max_overlap

    # ------------------------------------------------------------- LLM mode
    def _llm_review(self, paper: Paper, card: ResearchCard) -> PaperReview | None:
        prompt = (
            f"Title: {paper.title}\nAbstract: {paper.abstract}\n\n"
            f"Research card (JSON): {card.model_dump_json()}\n\n"
            "Review this paper. Return a JSON object with keys: summary, strengths "
            "(array of strings), weaknesses (array), novelty (0-1), feasibility (0-1), "
            "score (0-10). Be critical and specific."
        )
        try:
            raw = self._llm.complete(
                prompt,
                system="You are a rigorous, adversarial peer reviewer. Judge only what "
                "is reported; flag unknowns explicitly.",
            )
            data = json.loads(_extract_json(raw))
            return PaperReview(
                paper_id=paper.id,
                summary=str(data.get("summary", "")),
                strengths=[str(s) for s in data.get("strengths", [])],
                weaknesses=[str(w) for w in data.get("weaknesses", [])],
                novelty=float(data.get("novelty", 0.5)),
                feasibility=float(data.get("feasibility", 0.5)),
                score=float(data.get("score", 5.0)),
                reviewed_by=f"llm:{self._llm.name}",
            )
        except Exception:
            return None


def _extract_json(raw: str) -> str:
    """Best-effort: pull the first {...} block out of an LLM response."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw
