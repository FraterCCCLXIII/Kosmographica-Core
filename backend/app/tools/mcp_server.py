from __future__ import annotations

import json
import sys
from typing import Any, Callable

from app.tools.client import DEFAULT_EDGE_TYPES, KosmoApiClient
from app.tools.config import load_config
from app.tools.errors import KosmoToolError, error_payload

JsonDict = dict[str, Any]


def main() -> int:
    server = MinimalMcpServer()
    server.serve()
    return 0


class MinimalMcpServer:
    def __init__(self) -> None:
        self.config = load_config()
        self.client = KosmoApiClient(self.config)
        self.tools: dict[str, Callable[[JsonDict], JsonDict | list[JsonDict] | bytes]] = {
            "ask_corpus": self.ask_corpus,
            "compare_projects": self.compare_projects,
            "search_chunks": self.search_chunks,
            "search_graph": self.search_graph,
            "get_document": self.get_document,
            "get_entity": self.get_entity,
            "list_clusters": self.list_clusters,
            "get_cluster": self.get_cluster,
            "export_project_summary": self.export_project_summary,
        }

    def serve(self) -> None:
        while True:
            message = read_message(sys.stdin.buffer)
            if message is None:
                break
            response = self.handle(message)
            if response is not None:
                write_message(sys.stdout.buffer, response)

    def handle(self, message: JsonDict) -> JsonDict | None:
        method = message.get("method")
        request_id = message.get("id")
        if method == "notifications/initialized":
            return None
        try:
            if method == "initialize":
                return result(request_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "kosmographica", "version": "0.1.0"},
                })
            if method == "tools/list":
                return result(request_id, {"tools": tool_definitions()})
            if method == "tools/call":
                params = message.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if name not in self.tools:
                    raise ValueError(f"Unknown tool: {name}")
                payload = self.tools[name](arguments)
                return result(request_id, mcp_content(payload))
            return error(request_id, -32601, f"Unsupported MCP method: {method}")
        except Exception as exc:
            return result(request_id, mcp_error_content(exc))

    def ask_corpus(self, args: JsonDict) -> JsonDict:
        project_id = self.config.require_project(args.get("project_id"))
        question = require_str(args, "question")
        return self.client.ask(question, project_id, mode=str(args.get("mode", "single")), k=int(args.get("k", 8)))

    def compare_projects(self, args: JsonDict) -> JsonDict:
        question = require_str(args, "question")
        project_ids = args.get("project_ids")
        if not isinstance(project_ids, list) or not project_ids:
            raise ValueError("project_ids must be a non-empty list.")
        return self.client.comparative_ask(question, [str(item) for item in project_ids], k=int(args.get("k", 8)))

    def search_chunks(self, args: JsonDict) -> list[JsonDict]:
        project_id = self.config.require_project(args.get("project_id"))
        return self.client.search_chunks(require_str(args, "query"), project_id, limit=int(args.get("limit", 8)))

    def search_graph(self, args: JsonDict) -> JsonDict:
        project_id = self.config.require_project(args.get("project_id"))
        edge_types = args.get("edge_types")
        if edge_types is None:
            parsed_edge_types = DEFAULT_EDGE_TYPES
        elif isinstance(edge_types, list):
            parsed_edge_types = [str(item) for item in edge_types]
        else:
            parsed_edge_types = [item.strip() for item in str(edge_types).split(",") if item.strip()]
        return self.client.search_graph(
            require_str(args, "query"),
            project_id,
            depth=int(args.get("depth", 1)),
            node_limit=int(args.get("node_limit", 250)),
            edge_limit=int(args.get("edge_limit", 500)),
            edge_types=parsed_edge_types,
            document_id=str(args["document_id"]) if args.get("document_id") else None,
        )

    def get_document(self, args: JsonDict) -> JsonDict:
        return self.client.get_document(require_str(args, "document_id"))

    def get_entity(self, args: JsonDict) -> JsonDict:
        return self.client.entity_detail(require_str(args, "entity_id"))

    def list_clusters(self, args: JsonDict) -> JsonDict:
        project_id = self.config.require_project(args.get("project_id"))
        return self.client.list_clusters(project_id, limit=int(args.get("limit", 20)))

    def get_cluster(self, args: JsonDict) -> JsonDict:
        return self.client.cluster_detail(require_str(args, "cluster_id"))

    def export_project_summary(self, args: JsonDict) -> JsonDict:
        project_id = self.config.require_project(args.get("project_id"))
        format_ = str(args.get("format", "markdown"))
        content = self.client.export_project(project_id, format_=format_)
        text = content.decode("utf-8", errors="replace")
        return {"project_id": project_id, "format": format_, "content": text}


def tool_definitions() -> list[JsonDict]:
    return [
        tool("ask_corpus", "Ask a cited question against one project corpus.", {"question": "string", "project_id": "string", "mode": "string", "k": "number"}, ["question"]),
        tool("compare_projects", "Ask a cited comparative question across projects.", {"question": "string", "project_ids": "array", "k": "number"}, ["question", "project_ids"]),
        tool("search_chunks", "Search chunks semantically.", {"query": "string", "project_id": "string", "limit": "number"}, ["query"]),
        tool("search_graph", "Search a bounded graph neighborhood. co_occurs_with is excluded by default.", {"query": "string", "project_id": "string", "depth": "number", "edge_types": "array", "node_limit": "number", "edge_limit": "number", "document_id": "string"}, ["query"]),
        tool("get_document", "Fetch a document by id.", {"document_id": "string"}, ["document_id"]),
        tool("get_entity", "Fetch entity detail by id.", {"entity_id": "string"}, ["entity_id"]),
        tool("list_clusters", "List project clusters when clustering is available.", {"project_id": "string", "limit": "number"}, []),
        tool("get_cluster", "Fetch cluster detail by id.", {"cluster_id": "string"}, ["cluster_id"]),
        tool("export_project_summary", "Export project-level research artifact content.", {"project_id": "string", "format": "string"}, []),
    ]


def tool(name: str, description: str, properties: dict[str, str], required: list[str]) -> JsonDict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {
                key: schema_for(value, key)
                for key, value in properties.items()
            },
            "required": required,
        },
    }


def schema_for(value_type: str, key: str) -> JsonDict:
    schema: JsonDict = {"type": value_type, "description": key.replace("_", " ")}
    if value_type == "array":
        schema["items"] = {"type": "string"}
    return schema


def mcp_content(payload: Any) -> JsonDict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
        "structuredContent": payload if isinstance(payload, dict) else {"items": payload},
    }


def mcp_error_content(exc: Exception) -> JsonDict:
    payload = error_payload(exc)
    return {"isError": True, "content": [{"type": "text", "text": json.dumps(payload, indent=2)}], "structuredContent": payload}


def result(request_id: object, payload: JsonDict) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def error(request_id: object, code: int, message: str) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def require_str(args: JsonDict, key: str) -> str:
    value = args.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"{key} is required.")
    return str(value)


def read_message(stream: Any) -> JsonDict | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        decoded = line.decode("utf-8").strip()
        if not decoded:
            break
        name, _, value = decoded.partition(":")
        headers[name.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream: Any, message: JsonDict) -> None:
    body = json.dumps(message).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8"))
    stream.write(body)
    stream.flush()


if __name__ == "__main__":
    raise SystemExit(main())
