"""Cross-source deduplication and metadata merging."""

from datetime import date

from researchos.core.models import Paper
from researchos.ingestion.dedup import dedup_papers


def test_dedup_by_doi_merges_richer_metadata():
    a = Paper(
        source="semantic_scholar",
        source_id="s1",
        title="A Great Paper",
        abstract="short",
        doi="10.1/xyz",
        authors=["X"],
    )
    b = Paper(
        source="openalex",
        source_id="W9",
        title="A Great Paper (v2 title)",
        abstract="a much longer and richer abstract",
        doi="10.1/XYZ",
        authors=["X", "Y"],
        citation_count=42,
        published=date(2024, 1, 1),
    )
    out = dedup_papers([a, b])
    assert len(out) == 1
    merged = out[0]
    assert merged.abstract == "a much longer and richer abstract"  # longer kept
    assert merged.authors == ["X", "Y"]  # richer author list kept
    assert merged.citation_count == 42
    assert merged.published == date(2024, 1, 1)


def test_dedup_by_arxiv_id_ignores_version():
    a = Paper(source="arxiv", source_id="2401.00001v1", title="Memory for Agents")
    b = Paper(source="arxiv", source_id="2401.00001v2", title="Memory for Agents (updated)")
    assert len(dedup_papers([a, b])) == 1


def test_dedup_by_normalized_title_across_sources():
    a = Paper(source="arxiv", source_id="2401.1", title="Long-Term Memory: A Study!")
    b = Paper(source="openalex", source_id="W1", title="long term memory a study")
    assert len(dedup_papers([a, b])) == 1


def test_distinct_papers_are_kept():
    a = Paper(source="arxiv", source_id="1", title="Paper One")
    b = Paper(source="arxiv", source_id="2", title="Paper Two")
    assert len(dedup_papers([a, b])) == 2
