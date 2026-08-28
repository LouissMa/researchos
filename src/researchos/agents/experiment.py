"""Experiment Agent — reproduction planning (Phase 4, assisted-first).

Turns a paper's research card (and optional code links) into an :class:`ExperimentPlan`:
a narrative of reproduction steps plus the exact sandboxed commands to run and the
paper's claimed baseline for later comparison. Runs are always *assisted* — the human
approves and can edit every command before it executes (see
:class:`researchos.tools.python_exec.PythonExecTool`).

Heuristic mode derives steps from the card fields and a generic clone→install→run
template from the paper's code URLs. LLM mode drafts a richer plan from the same
evidence; both are grounded in the card (never fabricated commands for unknown repos).
"""

from __future__ import annotations

import json

from researchos.core.interfaces import LLM
from researchos.core.models import ExperimentPlan, Paper, ResearchCard, stable_id
from researchos.memory.graph import tokenize


def _git_dir(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "") or "repo"


class ExperimentAgent:
    role = "experiment"

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def plan(self, paper: Paper, card: ResearchCard | None = None) -> ExperimentPlan:
        if self._llm.available:
            plan = self._llm_plan(paper, card)
            if plan is not None:
                return plan
        return self._heuristic_plan(paper, card)

    # ------------------------------------------------------------ heuristics
    def _heuristic_plan(self, paper: Paper, card: ResearchCard | None) -> ExperimentPlan:
        steps = [
            f"Read the paper ({paper.title}) and identify the exact method to reproduce.",
        ]
        if card and card.method and "unknown" not in card.method.lower():
            steps.append(f"Recreate the method: {card.method[:160]}")
        if card and card.repro_difficulty not in ("", "unknown"):
            steps.append(
                f"Expect {card.repro_difficulty} reproduction difficulty — budget time for "
                "environment and dependency issues."
            )
        if card and card.results and "unknown" not in card.results.lower():
            steps.append(f"Verify the reported results: {card.results[:160]}")
        steps.append("Record every command and output; compare against the baseline claim.")

        commands: list[str] = []
        for url in paper.code_urls[:1]:  # template per primary repo; human edits freely
            name = _git_dir(url)
            commands.append(
                f"git clone --depth 1 {url} {name} && cd {name} && "
                f"pip install -e . && python -m pytest -q"
            )
        if not commands:
            commands.append("python -c \"print('reproduction commands go here')\"")

        # Baseline: the paper's claimed result — from the card when an LLM enriched it,
        # otherwise the abstract's final sentence (usually the headline claim).
        baseline = card.results if (card and "unknown" not in card.results.lower()) else ""
        if not baseline:
            sentences = [s for s in paper.abstract.split(". ") if s.strip()]
            if sentences:
                baseline = sentences[-1].strip()
        return ExperimentPlan(
            id=stable_id("exp", paper.id),
            paper_id=paper.id,
            title=f"Reproduce: {paper.title}",
            steps=steps,
            commands=commands,
            baseline=baseline[:300],
            generated_by="heuristic",
        )

    # ------------------------------------------------------------- LLM mode
    def _llm_plan(self, paper: Paper, card: ResearchCard | None) -> ExperimentPlan | None:
        card_json = card.model_dump_json() if card else "{}"
        prompt = (
            f"Paper: {paper.title}\nAbstract: {paper.abstract}\n"
            f"Code repos: {', '.join(paper.code_urls) or 'none linked'}\n"
            f"Research card: {card_json}\n\n"
            "Design an assisted reproduction plan. Return JSON with keys: title, steps "
            "(array of strings), commands (array of shell commands to run in a sandbox, "
            "only if a code repo is linked), baseline (the paper's claimed result)."
        )
        try:
            raw = self._llm.complete(
                prompt,
                system="You are a meticulous research engineer planning paper reproduction. "
                "Never invent repositories or commands; if no code is linked, give steps only.",
            )
            data = json.loads(_extract_json(raw))
            return ExperimentPlan(
                id=stable_id("exp", paper.id),
                paper_id=paper.id,
                title=str(data.get("title", f"Reproduce: {paper.title}")),
                steps=[str(s) for s in data.get("steps", [])],
                commands=[str(c) for c in data.get("commands", [])],
                baseline=str(data.get("baseline", "")),
                generated_by=f"llm:{self._llm.name}",
            )
        except Exception:
            return None


def baseline_match(baseline: str, output: str) -> bool | None:
    """Lexical check: does the output touch the paper's claimed baseline at all?"""
    btoks = set(tokenize(baseline))
    if not btoks:
        return None
    out_toks = set(tokenize(output))
    return bool(btoks & out_toks)


def _extract_json(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return raw
