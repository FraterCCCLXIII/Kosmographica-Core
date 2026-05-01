from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tools.client import KosmoApiClient
from app.tools.cli import main as cli_main
from app.tools.config import ToolConfig, load_config, set_config_value
from app.tools.errors import ApiError, BackendUnavailable, ClusteringNotAvailable
from app.tools.mcp_server import MinimalMcpServer


def test_config_file_defaults_are_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_config_value("project_id", "project-1", cwd=tmp_path)
    monkeypatch.delenv("KOSMO_PROJECT_ID", raising=False)

    config = load_config(tmp_path, env={})

    assert config.project_id == "project-1"
    assert config.api_url == "http://127.0.0.1:8000/api/v1"


def test_env_overrides_config_file(tmp_path: Path) -> None:
    set_config_value("project_id", "project-from-file", cwd=tmp_path)

    config = load_config(tmp_path, env={"KOSMO_PROJECT_ID": "project-from-env"})

    assert config.project_id == "project-from-env"


def test_search_graph_excludes_co_occurs_with_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_request(self, method, path, *, params=None, json_body=None):  # type: ignore[no-untyped-def]
        captured["params"] = params
        return {"data": {"nodes": [], "edges": [], "seed_node_ids": [], "query": params["query"]}}

    monkeypatch.setattr(KosmoApiClient, "_request", fake_request)
    client = KosmoApiClient(ToolConfig())

    client.search_graph("Mithras", "project-1")

    assert captured["params"]["edge_type"] == "mentions,contains,supports_claim"  # type: ignore[index]
    assert "co_occurs_with" not in str(captured["params"]["edge_type"])  # type: ignore[index]


def test_ask_corpus_marks_insufficient_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(self, method, path, *, params=None, json_body=None):  # type: ignore[no-untyped-def]
        return {
            "answer": "No evidence.",
            "confidence": "insufficient_evidence",
            "citations": [],
            "retrieved_chunks": [],
            "graph_paths": [],
        }

    monkeypatch.setattr(KosmoApiClient, "_request", fake_request)
    client = KosmoApiClient(ToolConfig())

    response = client.ask("Unsupported?", "project-1")

    assert response["insufficient_evidence"] is True


def test_cluster_404_raises_domain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(self, method, path, *, params=None, json_body=None):  # type: ignore[no-untyped-def]
        raise ApiError(404, "Not found", details={"detail": "Not found"})

    monkeypatch.setattr(KosmoApiClient, "_request", fake_request)
    client = KosmoApiClient(ToolConfig())

    with pytest.raises(ClusteringNotAvailable):
        client.list_clusters("project-1")


def test_mcp_unreachable_backend_returns_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_ask(self, question, project_id, *, mode="single", k=8, filters=None):  # type: ignore[no-untyped-def]
        raise BackendUnavailable("Backend down.")

    monkeypatch.setattr(KosmoApiClient, "ask", fake_ask)
    monkeypatch.setattr("app.tools.mcp_server.load_config", lambda: ToolConfig(project_id="project-1"))
    server = MinimalMcpServer()

    response = server.handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "ask_corpus", "arguments": {"question": "What?"}},
    })

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "backend_unavailable"


def test_mcp_tool_list_schema_is_json_serializable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.mcp_server.load_config", lambda: ToolConfig())
    server = MinimalMcpServer()

    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response is not None
    json.dumps(response)


def test_cli_json_flag_works_after_leaf_command(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("app.tools.cli.load_config", lambda: ToolConfig(project_id="project-1"))
    monkeypatch.setattr(KosmoApiClient, "list_documents", lambda self, project_id, limit=20, offset=0, status=None: {"items": [], "total": 0, "limit": limit, "offset": offset})

    exit_code = cli_main(["documents", "list", "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["total"] == 0
