"""Frozen offline evaluation scenarios for ResearchOS (Roadmap Phase 2).

Run with ``uv run python -m benchmarks.run_eval`` from the repository root — no network,
no API keys. CI executes this as a dedicated job; the script exits non-zero when a
scenario's hybrid recall@k falls below its declared threshold in ``scenarios.json``.
"""
