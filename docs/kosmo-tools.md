# Kosmographica CLI And MCP Tools

Kosmographica includes two integration surfaces for local research workflows:

- `kosmo`: a human CLI for asking questions, searching evidence, inspecting graph data, and exporting artifacts.
- `kosmo-mcp`: a Cursor-compatible MCP server that exposes the same API-first operations as structured tools.

Both tools call the existing FastAPI backend by default. They do not bypass project isolation, RAG citation validation, graph bounds, or export behavior.

## Configuration

Create a `.kosmo` config file in the repo root or your home directory:

```bash
kosmo config set-api-url http://127.0.0.1:8000/api/v1
kosmo config set-workspace 78dd7745-82da-4f16-ade5-51355649f6e1
kosmo config set-project 7cae8ddf-0ee9-4617-8659-ef38b8e73f2e
kosmo doctor
```

Environment variables override `.kosmo` values:

- `KOSMO_API_URL`
- `KOSMO_WORKSPACE_ID`
- `KOSMO_PROJECT_ID`
- `KOSMO_TIMEOUT_SECONDS`
- `KOSMO_AUTH_TOKEN`
- `KOSMO_ADMIN_ENABLED`
- `KOSMO_DATABASE_URL`

Admin diagnostics are disabled unless `KOSMO_ADMIN_ENABLED=true`. Admin commands use a separate read-only database connection.

## CLI Examples

```bash
kosmo ask "What does this corpus say about Mithras?"
kosmo search chunks "solar symbolism" --limit 8
kosmo graph search "Mithras" --depth 1
kosmo documents list --limit 20
kosmo entities search --query Mithras
kosmo clusters list
kosmo export project --format markdown --out report.md
```

Use `--json` on any command to emit structured output.

## MCP Setup

Run the MCP server with:

```bash
kosmo-mcp
```

The MCP tools exposed to Cursor are:

- `ask_corpus`
- `compare_projects`
- `search_chunks`
- `search_graph`
- `get_document`
- `get_entity`
- `list_clusters`
- `get_cluster`
- `export_project_summary`

`ask_corpus` returns `insufficient_evidence` as an explicit boolean so Cursor can warn before presenting weak answers. `search_graph` excludes `co_occurs_with` by default.

## Smoke Test

1. Start the FastAPI backend.
2. Run `kosmo doctor`.
3. Run `kosmo ask "What does this corpus say about Mithras?"`.
4. Run `kosmo graph search "Mithras" --json` and verify no `co_occurs_with` edges appear unless explicitly requested.
5. Start `kosmo-mcp` through Cursor and call `ask_corpus`, `search_graph`, and `get_document`.
