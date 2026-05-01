from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

API_BASE_URL = "http://127.0.0.1:8000/api/v1"


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    try:
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            workspace = _post_json(
                client,
                "/workspaces",
                {"name": f"Smoke Workspace {int(time.time())}", "description": "Created by smoke_test.py"},
            )["data"]
            results.append(("create workspace", True, workspace["id"]))

            project_a = _post_json(
                client,
                f"/workspaces/{workspace['id']}/projects",
                {
                    "name": f"Smoke Project A {int(time.time())}",
                    "description": "Created by smoke_test.py",
                    "domain": "smoke-test",
                    "embedding_config": {"provider": "local", "model": "local-hash-embedding-1536"},
                    "extraction_config": {"chunking": {"strategy": "sentence", "chunk_size": 120, "chunk_overlap": 20}},
                },
            )["data"]
            results.append(("create project A", True, project_a["id"]))

            project_b = _post_json(
                client,
                f"/workspaces/{workspace['id']}/projects",
                {
                    "name": f"Smoke Project B {int(time.time())}",
                    "description": "Created by smoke_test.py",
                    "domain": "smoke-test",
                    "embedding_config": {"provider": "local", "model": "local-hash-embedding-1536"},
                    "extraction_config": {"chunking": {"strategy": "sentence", "chunk_size": 120, "chunk_overlap": 20}},
                },
            )["data"]
            results.append(("create project B", True, project_b["id"]))

            upload_a = _upload_test_file(client, project_a["id"], "smoke-a.txt", _project_a_text())["data"]
            document_a_id = upload_a["document_id"]
            results.append(("upload project A txt document", True, document_a_id))

            upload_b = _upload_test_file(client, project_b["id"], "smoke-b.txt", _project_b_text())["data"]
            document_b_id = upload_b["document_id"]
            results.append(("upload project B txt document", True, document_b_id))

            status_a = _poll_ready(client, document_a_id)
            results.append(("poll project A graph ready", status_a in {"ready", "graph_ready"}, status_a))
            status_b = _poll_ready(client, document_b_id)
            results.append(("poll project B graph ready", status_b in {"ready", "graph_ready"}, status_b))

            nodes = _get_json(client, f"/graph/nodes?project_id={project_a['id']}")["data"]["items"]
            edges = _get_json(client, f"/graph/edges?project_id={project_a['id']}")["data"]["items"]
            node_types = {node["node_type"] for node in nodes}
            edge_types = {edge["edge_type"] for edge in edges}
            results.append(("graph nodes", {"chunk", "entity", "claim"}.issubset(node_types), f"{len(nodes)} node(s), types={sorted(node_types)}"))
            results.append(("graph edges", {"contains", "mentions", "supports_claim"}.issubset(edge_types), f"{len(edges)} edge(s), types={sorted(edge_types)}"))

            search_results = _post_json(
                client,
                "/search/vector",
                {"query": "gnostic demiurge cosmology", "project_id": project_a["id"], "k": 3, "filters": {}},
            )
            results.append(("vector search", bool(search_results), f"{len(search_results)} result(s)"))

            project_b_chunk_ids = {
                result["chunk_id"]
                for result in _post_json(
                    client,
                    "/search/vector",
                    {"query": "gnostic demiurge cosmology", "project_id": project_b["id"], "k": 10, "filters": {}},
                )
            }
            leaked_chunk_ids = {result["chunk_id"] for result in search_results}.intersection(project_b_chunk_ids)
            results.append(("project isolation", not leaked_chunk_ids, f"{len(leaked_chunk_ids)} leaked chunk(s)"))

            rag_response = _post_json(
                client,
                "/search/query",
                {"question": "What does the text say about Sophia and the demiurge?", "project_id": project_a["id"], "mode": "single", "k": 3},
            )
            results.append(("local RAG answer", rag_response["confidence"] == "low" and bool(rag_response["citations"]), rag_response["confidence"]))

            note = _post_json(
                client,
                "/research-notes",
                {
                    "project_id": project_a["id"],
                    "title": "Smoke research map",
                    "body": "Created by smoke_test.py",
                    "graph_node_ids": [node["id"] for node in nodes[:2]],
                    "metadata": {"source": "smoke_test"},
                },
            )["data"]
            results.append(("research note", bool(note["id"]), note["id"]))

            suggestions = _get_json(client, f"/workspaces/{workspace['id']}/cross-project/suggestions")
            results.append(("cross-project suggestions", bool(suggestions), f"{len(suggestions)} suggestion(s)"))
            if suggestions:
                confirmed = _post_json(
                    client,
                    f"/workspaces/{workspace['id']}/cross-project/links/confirm",
                    {"suggestion": suggestions[0], "rationale": "Smoke test identical entity evidence."},
                )
                results.append(("confirm cross-project link", confirmed["link_type"] == "same_entity_candidate", confirmed["id"]))
                canonical = _post_json(
                    client,
                    f"/workspaces/{workspace['id']}/cross-project/canonical/promote",
                    {"entity_id": suggestions[0]["source_entity"]["id"]},
                )
                results.append(("promote canonical entity", bool(canonical["id"]), canonical["id"]))

            export_json = _get_json(client, f"/export/{project_a['id']}/json")
            results.append(("export json", bool(export_json["nodes"]) and bool(export_json["edges"]) and bool(export_json["claims"]), "populated"))
            markdown = client.get(f"/export/{project_a['id']}/markdown")
            markdown.raise_for_status()
            results.append(("export markdown", "## Claims" in markdown.text and "Smoke Project A" in markdown.text, f"{len(markdown.text)} chars"))
    except Exception as exc:
        results.append(("smoke test exception", False, str(exc)))

    for name, ok, detail in results:
        label = "PASS" if ok else "FAIL"
        print(f"{label}: {name} - {detail}")

    return 0 if results and all(ok for _, ok, _ in results) else 1


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> Any:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def _get_json(client: httpx.Client, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _upload_test_file(client: httpx.Client, project_id: str, filename: str, text: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / filename
        file_path.write_text(text, encoding="utf-8")
        with file_path.open("rb") as file_obj:
            response = client.post(
                "/documents/upload",
                data={"project_id": project_id, "title": Path(filename).stem},
                files={"file": (filename, file_obj, "text/plain")},
            )
    response.raise_for_status()
    return response.json()


def _poll_ready(client: httpx.Client, document_id: str) -> str:
    last_status = "unknown"
    for _ in range(30):
        response = client.get(f"/documents/{document_id}/status")
        response.raise_for_status()
        last_status = response.json()["data"]["document_status"]
        if last_status in {"ready", "graph_ready", "failed"}:
            return last_status
        time.sleep(1)
    return last_status


def _project_a_text() -> str:
    return (
        "The gnostic text describes a demiurge and a layered cosmology. "
        "Sophia appears as a figure connected to wisdom, emanation, and restoration. "
        "This smoke document gives vector search enough evidence to retrieve a relevant chunk."
    )


def _project_b_text() -> str:
    return (
        "A second gnostic source also names Sophia and the demiurge in a cosmology of knowledge. "
        "The wording intentionally repeats entity names for cross-project link suggestions."
    )


if __name__ == "__main__":
    sys.exit(main())
