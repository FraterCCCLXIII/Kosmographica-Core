from __future__ import annotations

import json
from typing import Any


def as_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def format_error(payload: dict[str, Any]) -> str:
    error = payload.get("error", {})
    if not isinstance(error, dict):
        return "Error: unknown failure"
    details = error.get("details")
    suffix = f"\n\nDetails:\n{as_json(details)}" if details else ""
    return f"Error [{error.get('code', 'unknown')}]: {error.get('message', 'unknown failure')}{suffix}"


def format_doctor(result: dict[str, Any]) -> str:
    lines = ["# Kosmographica Doctor", ""]
    lines.append(f"- API URL: {result.get('api_url')}")
    lines.append(f"- API reachable: {_yes(result.get('api_reachable'))}")
    lines.append(f"- Workspace: {result.get('workspace_id') or 'not configured'}")
    lines.append(f"- Project: {result.get('project_id') or 'not configured'}")
    lines.append(f"- Project valid: {_yes(result.get('project_valid'))}")
    lines.append(f"- Documents: {result.get('document_count', 0)}")
    lines.append(f"- RAG likely ready: {_yes(result.get('rag_ready'))}")
    lines.append("")
    lines.append("## Checks")
    for check in result.get("checks", []):
        if isinstance(check, dict):
            lines.append(f"- {_yes(check.get('ok'))} {check.get('name')}: {check.get('message')}")
    return "\n".join(lines)


def format_rag(response: dict[str, Any]) -> str:
    lines = ["# Answer", "", str(response.get("answer", "")), ""]
    confidence = response.get("confidence", "unknown")
    if response.get("insufficient_evidence"):
        confidence = f"{confidence} (insufficient evidence)"
    lines.extend(["## Confidence", str(confidence), ""])
    rationale = response.get("confidence_rationale")
    if rationale:
        lines.extend(["## Rationale", str(rationale), ""])
    citations = response.get("citations") or []
    lines.append("## Citations")
    if citations:
        for citation in citations:
            lines.append(f"- [{citation.get('chunk_id')}] {citation.get('citation')}")
    else:
        lines.append("- No validated citations returned.")
    return "\n".join(lines)


def format_chunks(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No chunks matched."
    lines = ["# Chunk Search Results", ""]
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id") or chunk.get("id")
        score = chunk.get("similarity_score", chunk.get("score", ""))
        citation = chunk.get("citation", "")
        text = chunk.get("text", "")
        lines.extend([f"## {citation or chunk_id}", f"Score: {score}", "", str(text), ""])
    return "\n".join(lines)


def format_graph(result: dict[str, Any]) -> str:
    nodes = result.get("nodes") or []
    edges = result.get("edges") or []
    lines = [
        "# Graph Search",
        "",
        f"Query: {result.get('query', '')}",
        f"Nodes: {len(nodes)}",
        f"Edges: {len(edges)}",
        "",
        "## Nodes",
    ]
    for node in nodes[:25]:
        lines.append(f"- {node.get('label')} ({node.get('node_type')}) [{node.get('id')}]")
    lines.append("")
    lines.append("## Edges")
    for edge in edges[:25]:
        lines.append(f"- {edge.get('edge_type')}: {edge.get('source_node_id')} -> {edge.get('target_node_id')}")
    return "\n".join(lines)


def format_list(title: str, data: dict[str, Any], label_key: str = "title") -> str:
    items = data.get("items", [])
    total = data.get("total", len(items))
    lines = [f"# {title}", "", f"Returned {len(items)} of {total}.", ""]
    for item in items:
        label = item.get(label_key) or item.get("canonical_name") or item.get("label") or item.get("id")
        lines.append(f"- {label} [{item.get('id')}]")
    return "\n".join(lines)


def format_detail(title: str, data: dict[str, Any]) -> str:
    return f"# {title}\n\n```json\n{as_json(data)}\n```"


def _yes(value: object) -> str:
    return "yes" if bool(value) else "no"
