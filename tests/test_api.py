"""API surface: dashboard, OpenAPI paths, and read endpoints (offline)."""

from starlette.testclient import TestClient

from researchos.api.app import create_app


def _client(orch) -> TestClient:
    # `orch` fixture has initialized the DB. We don't enter the lifespan (no run
    # endpoints exercised here), so no second orchestrator/Qdrant is created.
    return TestClient(create_app())


def test_dashboard_served(orch):
    r = _client(orch).get("/")
    assert r.status_code == 200
    assert "ResearchOS" in r.text
    assert "Reasoning trace" in r.text


def test_openapi_exposes_endpoints(orch):
    spec = _client(orch).get("/openapi.json").json()
    paths = spec["paths"]
    for p in [
        "/health",
        "/projects/{project_id}/runs",
        "/runs",
        "/runs/{run_id}/events",
        "/projects/{project_id}/papers",
        "/projects/{project_id}/memory",
        "/projects/{project_id}/graph",
    ]:
        assert p in paths


def test_health_and_empty_memory(orch):
    c = _client(orch)
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/projects/nonexistent/memory").json() == []


def test_graph_endpoint_after_run(orch):
    orch.start_run("apitest", "knowledge graphs for llm agents", limit=6, top_cards=2)
    r = _client(orch).get("/projects/apitest/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["nodes"] >= 6
    assert body["edges"] > 0
    assert "paper" in body["by_type"]
    for edge in body["sample_edges"]:
        assert edge["provenance"]  # every exposed edge is grounded
        assert 0.0 <= edge["confidence"] <= 1.0
