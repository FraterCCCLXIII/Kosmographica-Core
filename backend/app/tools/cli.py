from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from app.tools import admin
from app.tools.client import DEFAULT_EDGE_TYPES, KosmoApiClient
from app.tools.config import load_config, serialize_config, set_config_value
from app.tools.errors import KosmoToolError, error_payload
from app.tools.formatters import (
    as_json,
    format_chunks,
    format_detail,
    format_doctor,
    format_error,
    format_graph,
    format_list,
    format_rag,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = run(args)
    except KosmoToolError as exc:
        print(format_error(error_payload(exc)), file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kosmo", description="Kosmographica CLI")
    add_json_arg(parser)
    subcommands = parser.add_subparsers(dest="command", required=True)

    config = subcommands.add_parser("config", help="Manage .kosmo defaults")
    add_json_arg(config)
    config_sub = config.add_subparsers(dest="config_command", required=True)
    _config_setter(config_sub, "set-api-url", "api_url", "API URL")
    _config_setter(config_sub, "set-workspace", "workspace_id", "Workspace UUID")
    _config_setter(config_sub, "set-project", "project_id", "Project UUID")
    config_show = config_sub.add_parser("show", help="Show resolved configuration")
    add_json_arg(config_show)
    config_show.set_defaults(config_key=None)

    doctor = subcommands.add_parser("doctor", help="Check API and project readiness")
    add_json_arg(doctor)
    add_project_arg(doctor)
    doctor.add_argument("--workspace")

    ask = subcommands.add_parser("ask", help="Ask a cited question")
    add_json_arg(ask)
    add_project_arg(ask)
    ask.add_argument("question")
    ask.add_argument("--mode", default="single")
    ask.add_argument("-k", type=int, default=8)

    search = subcommands.add_parser("search", help="Search corpus data")
    add_json_arg(search)
    search_sub = search.add_subparsers(dest="search_command", required=True)
    chunks = search_sub.add_parser("chunks", help="Search chunks")
    add_json_arg(chunks)
    add_project_arg(chunks)
    chunks.add_argument("query")
    chunks.add_argument("--limit", type=int, default=8)

    graph = subcommands.add_parser("graph", help="Graph commands")
    add_json_arg(graph)
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    graph_search = graph_sub.add_parser("search", help="Search a bounded graph neighborhood")
    add_json_arg(graph_search)
    add_project_arg(graph_search)
    graph_search.add_argument("query")
    graph_search.add_argument("--depth", type=int, default=1)
    graph_search.add_argument("--edge-types", default=",".join(DEFAULT_EDGE_TYPES))
    graph_search.add_argument("--node-limit", type=int, default=250)
    graph_search.add_argument("--edge-limit", type=int, default=500)

    documents = subcommands.add_parser("documents", help="Document commands")
    add_json_arg(documents)
    documents_sub = documents.add_subparsers(dest="documents_command", required=True)
    documents_list = documents_sub.add_parser("list", help="List documents")
    add_json_arg(documents_list)
    add_project_arg(documents_list)
    documents_list.add_argument("--limit", type=int, default=20)
    documents_list.add_argument("--offset", type=int, default=0)
    documents_get = documents_sub.add_parser("get", help="Get a document")
    add_json_arg(documents_get)
    documents_get.add_argument("document_id")

    entities = subcommands.add_parser("entities", help="Entity commands")
    add_json_arg(entities)
    entities_sub = entities.add_subparsers(dest="entities_command", required=True)
    entities_search = entities_sub.add_parser("search", help="Search entities")
    add_json_arg(entities_search)
    add_project_arg(entities_search)
    entities_search.add_argument("--query", default=None)
    entities_search.add_argument("--limit", type=int, default=20)
    entity_get = entities_sub.add_parser("get", help="Get entity detail")
    add_json_arg(entity_get)
    entity_get.add_argument("entity_id")

    clusters = subcommands.add_parser("clusters", help="Cluster commands")
    add_json_arg(clusters)
    clusters_sub = clusters.add_subparsers(dest="clusters_command", required=True)
    clusters_list = clusters_sub.add_parser("list", help="List clusters")
    add_json_arg(clusters_list)
    add_project_arg(clusters_list)
    clusters_list.add_argument("--limit", type=int, default=20)
    cluster_get = clusters_sub.add_parser("get", help="Get cluster detail")
    add_json_arg(cluster_get)
    cluster_get.add_argument("cluster_id")

    export = subcommands.add_parser("export", help="Export commands")
    add_json_arg(export)
    export_sub = export.add_subparsers(dest="export_command", required=True)
    export_project = export_sub.add_parser("project", help="Export a project")
    add_json_arg(export_project)
    add_project_arg(export_project)
    export_project.add_argument("--format", choices=["json", "graphml", "csv", "markdown"], default="markdown")
    export_project.add_argument("--out", type=Path, required=True)

    admin_parser = subcommands.add_parser("admin", help="Read-only admin diagnostics")
    add_json_arg(admin_parser)
    admin_sub = admin_parser.add_subparsers(dest="admin_command", required=True)
    add_json_arg(admin_sub.add_parser("db-check"))
    add_json_arg(admin_sub.add_parser("index-check"))
    add_json_arg(admin_sub.add_parser("processing-health"))
    return parser


def run(args: argparse.Namespace) -> str | None:
    config = load_config()
    if args.command == "config":
        return run_config(args, config)
    client = KosmoApiClient(config)
    if args.command == "doctor":
        result = client.doctor(project_id=args.project, workspace_id=args.workspace)
        return render(args, result, format_doctor)
    if args.command == "ask":
        result = client.ask(args.question, config.require_project(args.project), mode=args.mode, k=args.k)
        return render(args, result, format_rag)
    if args.command == "search" and args.search_command == "chunks":
        result = client.search_chunks(args.query, config.require_project(args.project), limit=args.limit)
        return render(args, result, format_chunks)
    if args.command == "graph" and args.graph_command == "search":
        result = client.search_graph(
            args.query,
            config.require_project(args.project),
            depth=args.depth,
            node_limit=args.node_limit,
            edge_limit=args.edge_limit,
            edge_types=_csv(args.edge_types),
        )
        return render(args, result, format_graph)
    if args.command == "documents" and args.documents_command == "list":
        result = client.list_documents(config.require_project(args.project), limit=args.limit, offset=args.offset)
        return render(args, result, lambda data: format_list("Documents", data, "title"))
    if args.command == "documents" and args.documents_command == "get":
        result = client.get_document(args.document_id)
        return render(args, result, lambda data: format_detail("Document", data))
    if args.command == "entities" and args.entities_command == "search":
        result = client.list_entities(config.require_project(args.project), query=args.query, limit=args.limit)
        return render(args, result, lambda data: format_list("Entities", data, "canonical_name"))
    if args.command == "entities" and args.entities_command == "get":
        result = client.entity_detail(args.entity_id)
        return render(args, result, lambda data: format_detail("Entity", data))
    if args.command == "clusters" and args.clusters_command == "list":
        result = client.list_clusters(config.require_project(args.project), limit=args.limit)
        return render(args, result, lambda data: format_list("Clusters", data, "label"))
    if args.command == "clusters" and args.clusters_command == "get":
        result = client.cluster_detail(args.cluster_id)
        return render(args, result, lambda data: format_detail("Cluster", data))
    if args.command == "export" and args.export_command == "project":
        client.export_project(config.require_project(args.project), format_=args.format, out=args.out)
        return f"Wrote {args.out}"
    if args.command == "admin":
        return run_admin(args, config)
    raise AssertionError(f"Unhandled command: {args.command}")


def run_config(args: argparse.Namespace, config: Any) -> str:
    if args.config_command == "show":
        return as_json(serialize_config(config))
    path = set_config_value(args.config_key, args.value)
    return f"Updated {args.config_key} in {path}"


def run_admin(args: argparse.Namespace, config: Any) -> str:
    if args.admin_command == "db-check":
        return as_json(admin.db_check(config))
    if args.admin_command == "index-check":
        return as_json(admin.index_check(config))
    if args.admin_command == "processing-health":
        return as_json(admin.processing_health(config))
    raise AssertionError(f"Unhandled admin command: {args.admin_command}")


def render(args: argparse.Namespace, data: Any, formatter: Any) -> str:
    if getattr(args, "json", False):
        return as_json(data)
    return formatter(data)


def add_project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", help="Project UUID. Defaults to .kosmo project_id.")


def add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print JSON output")


def _config_setter(subcommands: argparse._SubParsersAction[argparse.ArgumentParser], name: str, key: str, help_text: str) -> None:
    parser = subcommands.add_parser(name, help=f"Set {help_text}")
    add_json_arg(parser)
    parser.add_argument("value")
    parser.set_defaults(config_key=key)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
