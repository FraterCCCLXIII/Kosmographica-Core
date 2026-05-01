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

            project = _post_json(
                client,
                f"/workspaces/{workspace['id']}/projects",
                {
                    "name": f"Smoke Project {int(time.time())}",
                    "description": "Created by smoke_test.py",
                    "domain": "smoke-test",
                    "embedding_config": {"provider": "local", "model": "local-hash-embedding-1536"},
                    "extraction_config": {"chunking": {"strategy": "sentence", "chunk_size": 120, "chunk_overlap": 20}},
                },
            )["data"]
            results.append(("create project", True, project["id"]))

            upload = _upload_test_file(client, project["id"])["data"]
            document_id = upload["document_id"]
            results.append(("upload txt document", True, document_id))

            status = _poll_ready(client, document_id)
            results.append(("poll document ready", status == "ready", status))

            search_results = _post_json(
                client,
                "/search/vector",
                {"query": "gnostic demiurge cosmology", "project_id": project["id"], "k": 3, "filters": {}},
            )
            results.append(("vector search", bool(search_results), f"{len(search_results)} result(s)"))
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


def _upload_test_file(client: httpx.Client, project_id: str) -> dict[str, Any]:
    text = (
        "The gnostic text describes a demiurge and a layered cosmology. "
        "Sophia appears as a figure connected to wisdom, emanation, and restoration. "
        "This smoke document gives vector search enough evidence to retrieve a relevant chunk."
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / "smoke.txt"
        file_path.write_text(text, encoding="utf-8")
        with file_path.open("rb") as file_obj:
            response = client.post(
                "/documents/upload",
                data={"project_id": project_id, "title": "Smoke Test Document"},
                files={"file": ("smoke.txt", file_obj, "text/plain")},
            )
    response.raise_for_status()
    return response.json()


def _poll_ready(client: httpx.Client, document_id: str) -> str:
    last_status = "unknown"
    for _ in range(30):
        response = client.get(f"/documents/{document_id}/status")
        response.raise_for_status()
        last_status = response.json()["data"]["document_status"]
        if last_status in {"ready", "failed"}:
            return last_status
        time.sleep(1)
    return last_status


if __name__ == "__main__":
    sys.exit(main())
