"""Reviewer capability: quality ordering and score bands (Phase 3, offline)."""

from researchos.agents.knowledge import heuristic_card
from researchos.agents.reviewer import Reviewer
from researchos.core.models import Paper
from researchos.llm.client import get_llm

_STRONG = Paper(
    source="arxiv",
    source_id="r1",
    title="Robust Retrieval-Augmented Generation with Adaptive Query Rewriting",
    abstract=(
        "Retrieval-augmented generation systems struggle when the user query does not match "
        "the document vocabulary. We propose AdaptiveQueryRewrite, a lightweight module that "
        "rewrites the query before retrieval using index statistics. Experiments on four "
        "benchmarks show a 12.4% average accuracy improvement over the strongest baseline, "
        "with a 1.8x speedup in latency. A limitation is that the rewriter is trained on "
        "domain-specific data."
    ),
)

_MID = Paper(
    source="arxiv",
    source_id="r2",
    title="On the Effect of Prompt Ordering in Language Model Agents",
    abstract=(
        "We study how the ordering of instructions and few-shot examples affects language "
        "model agent performance. Our framework covers both zero-shot and few-shot settings "
        "across several tasks."
    ),
)

_WEAK = Paper(
    source="arxiv",
    source_id="r3",
    title="A Note on Agent Memory",
    abstract="We briefly discuss memory in agents.",
)

# Papers need stable ids before they can be used as dict keys / compared.
_STRONG.ensure_id()
_MID.ensure_id()
_WEAK.ensure_id()


def _reviewer(settings):
    return Reviewer(get_llm(settings))


def test_reviewer_orders_quality(settings):
    context = [_STRONG, _MID, _WEAK]
    reviewer = _reviewer(settings)
    scores = {p.id: reviewer.review(p, heuristic_card(p), context).score for p in context}
    assert scores[_STRONG.id] > scores[_MID.id] > scores[_WEAK.id]
    assert scores[_STRONG.id] >= 5.0
    assert scores[_WEAK.id] <= 4.0


def test_reviewer_shape_and_determinism(settings):
    reviewer = _reviewer(settings)
    a = reviewer.review(_STRONG, heuristic_card(_STRONG), [_STRONG, _MID, _WEAK])
    b = reviewer.review(_STRONG, heuristic_card(_STRONG), [_STRONG, _MID, _WEAK])
    assert a.model_dump() == b.model_dump()
    assert a.strengths and a.weaknesses
    assert 0.0 <= a.score <= 10.0
    assert 0.0 <= a.novelty <= 1.0
    assert a.reviewed_by == "heuristic"


def test_novelty_against_context(settings):
    # A paper sharing vocabulary with the context is less "novel" than an off-topic one.
    reviewer = _reviewer(settings)
    similar = Paper(
        source="arxiv",
        source_id="r4",
        title="More on Retrieval-Augmented Generation with Query Rewriting",
        abstract=(
            "We extend retrieval-augmented generation by rewriting user queries before "
            "retrieval using document statistics, improving accuracy on benchmarks."
        ),
    )
    ctx = [_STRONG, _MID, _WEAK]
    novel = reviewer.review(_WEAK, heuristic_card(_WEAK), ctx).novelty
    familiar = reviewer.review(similar, heuristic_card(similar), ctx).novelty
    assert novel > familiar
