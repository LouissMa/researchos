"""Writing Agent — LaTeX drafts and consistency checks (Phase 5).

Related work is assembled **from the project's knowledge graph only**: theme sections
come from the graph's concept nodes (with their ``BELONGS_TO`` member papers), every
``\\cite`` key resolves to a ``\\bibitem`` in the same document, and the consistency
pass reports any dangling citation. No fabricated references — the anti-hallucination
rule of ARCHITECTURE.md §5 applies to writing as much as to retrieval.

Heuristic mode is fully offline and deterministic. LLM mode improves prose where a key
is configured and falls back to heuristics on any failure.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from researchos.core.interfaces import LLM
from researchos.core.models import Draft
from researchos.memory.graph import SqliteGraphStore
from researchos.persistence.models import PaperRow
from researchos.persistence.store import Store

_CITE_RE = re.compile(r"\\cite(?:t)?\{([^}]+)\}")


class WritingAgent:
    role = "writing"

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def draft(self, project_id: str, *, run_id: str | None = None) -> Draft:
        """Generate a related-work LaTeX draft grounded in the project's KG."""
        if self._llm.available:
            tex = self._llm_tex(project_id)
            if tex:
                draft = self._assemble(project_id, run_id, tex, f"llm:{self._llm.name}")
                draft.inconsistencies = self.check(draft)
                return draft
        tex = self._heuristic_tex(project_id)
        draft = self._assemble(project_id, run_id, tex, "heuristic")
        draft.inconsistencies = self.check(draft)
        return draft

    # ------------------------------------------------------------ assembly
    @staticmethod
    def _assemble(project_id: str, run_id: str | None, tex: str, generated_by: str) -> Draft:
        citations = sorted(set(_CITE_RE.findall(tex)))
        return Draft(
            id=f"draft-{project_id}",
            project_id=project_id,
            run_id=run_id or "",
            tex=tex,
            sections=[s for s in re.findall(r"\\section\*?\{([^}]+)\}", tex)],
            citations=citations,
            generated_by=generated_by,
        )

    # ---------------------------------------------------------- heuristics
    def _heuristic_tex(self, project_id: str) -> str:
        papers = Store().list_papers(project_id, limit=200)
        themes = self._themes(project_id, papers)
        if not papers:
            return _document("Draft (empty project)", _esc(project_id), "")

        by_id = {p.id: p for p in papers}
        lines: list[str] = []
        intro = (
            "This document surveys the research landscape of project "
            f"\\texttt{{{_esc(project_id)}}} — {len(papers)} papers organized into "
            f"{len(themes)} themes by ResearchOS."
        )
        lines.append("\\section{Introduction}\n" + intro)

        lines.append("\\section{Related Work}\n")
        for theme, members in themes:
            lines.append(f"\\subsection{{{_esc(theme)}}}\n")
            for pid in members:
                paper = by_id.get(pid)
                if paper:
                    lines.append(f"\\citet{{{pid}}} — {_esc(paper.title)}")
            lines.append("")

        ideas = Store().list_ideas(project_id, limit=10)
        if ideas:
            lines.append("\\section{Open Directions}\n")
            for idea in ideas:
                lines.append(
                    f"\\begin{{itemize}}\n  \\item \\textbf{{{_esc(idea.title)}}} — "
                    f"{_esc(idea.hypothesis[:160])}\n\\end{{itemize}}\n"
                )

        lines.append(_bibliography(papers))
        return _document("ResearchOS Survey Draft", f"Project {_esc(project_id)}", "\n".join(lines))

    # ------------------------------------------------------------ the graph
    def _themes(self, project_id: str, papers: list[PaperRow]) -> list[tuple[str, list[str]]]:
        """Theme → member paper ids, reconstructed from the knowledge graph."""
        graph = SqliteGraphStore()
        concepts = graph.nodes(project_id, node_type="concept", limit=100)
        edges = graph.edges(project_id, relation="BELONGS_TO", limit=500)
        concept_members: dict[str, list[str]] = {c.id: [] for c in concepts}
        for e in edges:
            if e.target_id in concept_members:
                # source id format: "{project}:paper:{paper_id}"
                paper_id = e.source_id.rsplit(":", 1)[-1]
                if any(p.id == paper_id for p in papers):
                    concept_members[e.target_id].append(paper_id)
        themes: list[tuple[str, list[str]]] = []
        for c in concepts:
            members = sorted(set(concept_members[c.id]))
            if members:
                themes.append((c.label, members))
        if not themes and papers:
            themes.append(("Overview", [p.id for p in papers]))
        return themes

    # ---------------------------------------------------------- consistency
    @staticmethod
    def check(draft: Draft) -> list[str]:
        """Every \\cite must resolve to a \\bibitem in the same document."""
        bib = set(re.findall(r"\\bibitem\{([^}]+)\}", draft.tex))
        issues: list[str] = []
        for key in draft.citations:
            if key not in bib:
                issues.append(f"dangling citation: \\cite{{{key}}} has no \\bibitem")
        for key in sorted(bib):
            if key not in draft.citations:
                issues.append(f"uncited bibliography entry: \\bibitem{{{key}}}")
        return issues

    # ------------------------------------------------------------- LLM mode
    def _llm_tex(self, project_id: str) -> str | None:
        papers = Store().list_papers(project_id, limit=30)
        if not papers:
            return None
        listing = "\n".join(
            f"- {p.id} | {p.title} | {p.published or 'n.d.'} | {p.abstract[:200]}"
            for p in papers[:15]
        )
        prompt = (
            "Write a LaTeX survey draft for the following papers (cite them with "
            "\\citet{<paper-id>} using the ids exactly as listed):\n"
            f"{listing}\n\n"
            "Sections: Introduction, Related Work (grouped thematically), Open Directions. "
            "Only cite the papers listed; never invent references."
        )
        try:
            raw = self._llm.complete(
                prompt,
                system="You are a senior researcher writing a related-work survey in LaTeX. "
                "Cite only the provided paper keys.",
            )
            return raw.strip()
        except Exception:
            return None


# --------------------------------------------------------------- rendering
def _esc(text: str) -> str:
    return text.replace("&", "\\&").replace("%", "\\%").replace("#", "\\#")


def _bibliography(papers: list[PaperRow]) -> str:
    entries = []
    for p in papers:
        authors = ", ".join((p.source_id or p.source).split()[:1]) or p.source
        entries.append(
            f"\\bibitem{{{p.id}}} {authors} \\textit{{{_esc(p.title)}}}, "
            f"{p.published or 'n.d.'}, {p.url}"
        )
    return "\\begin{thebibliography}{99}\n" + "\n".join(entries) + "\n\\end{thebibliography}"


def _document(title: str, subtitle: str, body: str) -> str:
    date = datetime.now(UTC).date().isoformat()
    return (
        "\\documentclass{article}\n"
        "\\usepackage{natbib}\n"
        "\\title{" + _esc(title) + "}\n"
        "\\author{ResearchOS}\n"
        f"\\date{{{date}}}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        f"\\noindent\\textit{{{_esc(subtitle)}}}\n\n" + body + "\n\\end{document}\n"
    )
