"""Minimal end-to-end example: run a literature-discovery workflow programmatically.

    python examples/literature_discovery.py "long-term memory for LLM agents"

Runs fully offline (real arXiv search + local embeddings + embedded Qdrant). Set an
OpenAI-compatible LLM via .env to unlock LLM-written cards and a narrative landscape.
"""

from __future__ import annotations

import sys

from researchos.config import get_settings
from researchos.observability.events import Event
from researchos.orchestration.orchestrator import SequentialOrchestrator


def main() -> None:
    goal = sys.argv[1] if len(sys.argv) > 1 else "long-term memory mechanisms for LLM agents"

    def on_event(ev: Event) -> None:
        text = ev.payload.get("text") or ev.payload.get("output") or ""
        print(f"  [{ev.actor}] {ev.type.value} {text}".rstrip())

    orch = SequentialOrchestrator(get_settings())
    state = orch.start_run("example", goal, limit=15, top_cards=4, on_event=on_event)

    print("\n=== LANDSCAPE ===")
    if state.landscape:
        print(state.landscape.summary, "\n")
        print("Key papers (reading order):")
        for i, pid in enumerate(state.landscape.reading_order[:10], 1):
            paper = state.papers.get(pid)
            if paper:
                print(f"  {i}. {paper.title} ({paper.year or 'n.d.'})")
    print(f"\nRun {state.run_id}: {len(state.papers)} papers, {len(state.clusters)} themes.")


if __name__ == "__main__":
    main()
