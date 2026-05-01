from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.tools.config import ToolConfig
from app.tools.errors import ApiError, BackendUnavailable, ClusteringNotAvailable, ConfigError

DEFAULT_EDGE_TYPES = ["mentions", "contains", "supports_claim"]


class KosmoApiClient:
    def __init__(self, config: ToolConfig) -> None:
        self.config = config

    def close(self) -> None:
        return None

    def doctor(self, project_id: str | None = None, workspace_id: str | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "api_url": self.config.api_url,
            "api_reachable": False,
            "workspace_id": workspace_id or self.config.workspace_id,
            "project_id": project_id or self.config.project_id,
            "project_valid": False,
            "document_count": 0,
            "rag_ready": False,
            "checks": [],
        }
        checks: list[dict[str, object]] = []
        result["checks"] = checks
        try:
            workspaces = self.list_workspaces()
            result["api_reachable"] = True
            checks.append({"name": "api", "ok": True, "message": f"Reached {self.config.api_url}"})
            if workspace_id or self.config.workspace_id:
                projects = self.list_projects(self.config.require_workspace(workspace_id))
                checks.append({"name": "workspace", "ok": True, "message": f"Workspace has {len(projects)} project(s)."})
            else:
                checks.append({"name": "workspace", "ok": True, "message": f"API returned {len(workspaces)} workspace(s)."})
            resolved_project = self.config.require_project(project_id)
            documents = self.list_documents(resolved_project, limit=1)
            result["project_valid"] = True
            result["document_count"] = documents.get("total", len(documents.get("items", [])))
            result["rag_ready"] = int(result["document_count"]) > 0
            checks.append({"name": "project", "ok": True, "message": f"Project has {result['document_count']} document(s)."})
        except ConfigError as exc:
            checks.append({"name": "config", "ok": False, "message": exc.message})
        except BackendUnavailable as exc:
            checks.append({"name": "api", "ok": False, "message": exc.message})
        except ApiError as exc:
            checks.append({"name": "api", "ok": False, "message": exc.message, "status_code": exc.status_code})
        return result

    def list_workspaces(self) -> list[dict[str, Any]]:
        return _items(self._request("GET", "/workspaces"))

    def list_projects(self, workspace_id: str) -> list[dict[str, Any]]:
        return _items(self._request("GET", f"/workspaces/{workspace_id}/projects"))

    def list_documents(self, project_id: str, *, limit: int = 20, offset: int = 0, status: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return _data(self._request("GET", f"/projects/{project_id}/documents", params=params))

    def get_document(self, document_id: str) -> dict[str, Any]:
        return _data(self._request("GET", f"/documents/{document_id}"))

    def get_document_chunks(self, document_id: str, *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return _data(self._request("GET", f"/documents/{document_id}/chunks", params={"limit": limit, "offset": offset}))

    def ask(self, question: str, project_id: str, *, mode: str = "single", k: int = 8, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/search/query",
            json_body={"question": question, "project_id": project_id, "mode": mode, "k": k, "filters": filters or {}},
        )
        response["insufficient_evidence"] = response.get("confidence") == "insufficient_evidence"
        return response

    def comparative_ask(self, question: str, project_ids: list[str], *, k: int = 8) -> dict[str, Any]:
        response = self._request("POST", "/search/comparative", json_body={"question": question, "project_ids": project_ids, "k": k})
        response["insufficient_evidence"] = response.get("confidence") == "insufficient_evidence"
        return response

    def search_chunks(self, query: str, project_id: str, *, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._request("POST", "/search/vector", json_body={"query": query, "project_id": project_id, "k": limit, "filters": filters or {}})

    def search_graph(
        self,
        query: str,
        project_id: str,
        *,
        depth: int = 1,
        seed_limit: int = 20,
        node_limit: int = 250,
        edge_limit: int = 500,
        edge_types: list[str] | None = None,
        min_weight: float | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": query,
            "depth": depth,
            "seed_limit": seed_limit,
            "node_limit": node_limit,
            "edge_limit": edge_limit,
            "edge_type": ",".join(edge_types or DEFAULT_EDGE_TYPES),
        }
        if min_weight is not None:
            params["min_weight"] = min_weight
        if document_id:
            params["document_id"] = document_id
        return _data(self._request("GET", f"/projects/{project_id}/graph/search", params=params))

    def list_entities(self, project_id: str, *, query: str | None = None, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        return _data(self._request("GET", f"/projects/{project_id}/entities", params=params))

    def entity_detail(self, entity_id: str) -> dict[str, Any]:
        return _data(self._request("GET", f"/entities/{entity_id}/detail"))

    def list_clusters(self, project_id: str, *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        try:
            return _data(self._request("GET", f"/projects/{project_id}/clusters", params={"limit": limit, "offset": offset}))
        except ApiError as exc:
            if exc.status_code in {404, 405, 501}:
                raise ClusteringNotAvailable("Clustering API is not available for this project or backend.") from exc
            raise

    def cluster_detail(self, cluster_id: str) -> dict[str, Any]:
        try:
            return _data(self._request("GET", f"/clusters/{cluster_id}"))
        except ApiError as exc:
            if exc.status_code in {404, 405, 501}:
                raise ClusteringNotAvailable(f"Cluster is not available: {cluster_id}") from exc
            raise

    def export_project(self, project_id: str, *, format_: str = "markdown", out: Path | None = None) -> bytes:
        content = self._request_bytes("GET", f"/export/{project_id}/{format_}")
        if out:
            out.write_bytes(content)
        return content

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        with httpx.Client(base_url=self.config.api_url, timeout=self.config.timeout_seconds, headers=self._headers()) as client:
            try:
                response = client.request(method, path, params=params, json=json_body)
            except httpx.RequestError as exc:
                raise BackendUnavailable(f"Could not reach Kosmographica API at {self.config.api_url}.") from exc
        if response.status_code >= 400:
            raise _api_error(response)
        return response.json()

    def _request_bytes(self, method: str, path: str) -> bytes:
        with httpx.Client(base_url=self.config.api_url, timeout=self.config.timeout_seconds, headers=self._headers()) as client:
            try:
                response = client.request(method, path)
            except httpx.RequestError as exc:
                raise BackendUnavailable(f"Could not reach Kosmographica API at {self.config.api_url}.") from exc
        if response.status_code >= 400:
            raise _api_error(response)
        return response.content

    def _headers(self) -> dict[str, str]:
        if not self.config.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.config.auth_token}"}


def _data(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def _items(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = _data(response)
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def _api_error(response: httpx.Response) -> ApiError:
    details: object
    try:
        details = response.json()
    except json.JSONDecodeError:
        details = response.text
    message = response.reason_phrase
    if isinstance(details, dict) and "detail" in details:
        message = str(details["detail"])
    return ApiError(response.status_code, message, details=details)
