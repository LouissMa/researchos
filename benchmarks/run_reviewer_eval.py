"""Frozen offline Reviewer benchmark (Roadmap Phase 3): heuristic review sanity.

Reviews the frozen papers in ``benchmarks/reviewer_scenarios.json`` with the deterministic
heuristic Reviewer and asserts that scores (a) respect the declared tier bands and (b) rank
strong > mid > weak. Fully offline; runs in CI.

Usage:
    uv run python -m benchmarks.run_reviewer_eval
"""

from __future__ import annotations

import json
from pathlib import Path

from researchos.agents.knowledge import heuristic_card
from researchos.agents.reviewer import Reviewer
from researchos.core.interfaces import LLM
from researchos.core.models import Paper

_SCENARIOS = Path(__file__).resolve().parent / "reviewer_scenarios.json"


class _NullLLM(LLM):
    """Offline LLM stub — keeps the Reviewer in deterministic heuristic mode."""

    name = "null"
    available = False

    def complete(self, prompt: str, *, system: str | None = None) -> str:  # pragma: no cover
        raise RuntimeError("null provider")


def _to_paper(data: dict) -> Paper:
    return Paper(**data).ensure_id()


def run_reviewer_eval() -> bool:
    payload = json.loads(_SCENARIOS.read_text(encoding="utf-8"))
    scenarios = payload["scenarios"]
    tiers = payload["tiers"]

    papers = [_to_paper(sc["paper"]) for sc in scenarios]
    context = list(papers)
    reviewer = Reviewer(_NullLLM())

    results: dict[str, float] = {}
    print(f"{'scenario':<14} {'tier':<8} {'score':<8} {'novelty':<9} {'feas':<6}")
    for sc, paper in zip(scenarios, papers, strict=True):
        review = reviewer.review(paper, heuristic_card(paper), context)
        results[sc["id"]] = review.score
        print(
            f"{sc['id']:<14} {sc['gold_tier']:<8} {review.score:<8.2f} "
            f"{review.novelty:<9.2f} {review.feasibility:<6.2f}"
        )

    ok = True
    # Strict tier ordering (strong > mid > weak).
    ids = [sc["id"] for sc in scenarios]
    tiers_of = {sc["id"]: sc["gold_tier"] for sc in scenarios}
    order = {"strong": 2, "mid": 1, "weak": 0}
    sorted_by_score = sorted(ids, key=lambda i: results[i])
    expected_order = sorted(ids, key=lambda i: order[tiers_of[i]])
    if sorted_by_score != expected_order:
        print("\nFAIL: reviewer score ordering does not match gold tiers")
        ok = False

    # Per-tier bands.
    for sc in scenarios:
        band = tiers[sc["gold_tier"]]
        score = results[sc["id"]]
        in_band = band["min_score"] <= score <= band["max_score"]
        status = "PASS" if in_band else "FAIL"
        print(
            f"  {sc['id']}: score {score:.2f} in band "
            f"[{band['min_score']}, {band['max_score']}] → {status}"
        )
        if not in_band:
            ok = False
    return ok


def main() -> int:
    ok = run_reviewer_eval()
    print("\n" + ("REVIEWER BENCHMARK PASS" if ok else "REVIEWER BENCHMARK FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
