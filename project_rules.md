# Graph RAG Research OS — Project Rules

## What we are building
A local-first, multi-project knowledge graph system for large document corpora.
Each Project is an isolated research graph. Projects can later be linked into a
comparative "megagraph" without losing provenance or collapsing distinctions.

## Non-negotiable constraints
- Every claim, edge, and relationship must trace back to a source chunk and document.
- Never invent citations. If evidence is weak, say so explicitly.
- Project graphs are isolated by default. Cross-project queries are opt-in.
- The megagraph is a generated VIEW, not the source of truth.
- Speculative links must be stored with a confidence score and flagged in the UI.

## What to avoid
- Collapsing traditions into vague sameness (e.g., "all savior figures are the same")
- Treating low-confidence comparative links as established facts
- Losing provenance when merging across projects
- Building one giant graph before individual project graphs are solid
- Forcing all projects to share one ontology prematurely

## Stack decisions (locked for MVP)
- Frontend: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- Backend: Python 3.11, FastAPI
- Database: PostgreSQL 16 + pgvector
- Graph storage: Postgres edge tables (no Neo4j yet)
- Embeddings: OpenAI text-embedding-3-small (abstracted behind EmbeddingProvider)
- LLM: Anthropic Claude (abstracted behind LLMProvider)
- Background jobs: Dramatiq + RabbitMQ
- File parsing: PyMuPDF, python-docx, BeautifulSoup4
- Graph visualization: Sigma.js

## Resolved decisions (after Session 8)

MIGRATION STRATEGY: Use Alembic autogenerate from ORM models.
The Session 1 SQL files are reference only - Alembic is the
canonical migration tool going forward.

WORKER STRATEGY: Add `DRAMATIQ_DEV_MODE` env flag. When true,
ingestion runs synchronously. RabbitMQ is required only in
production mode.

GRAPH API SOURCE: Query persisted `graph_node`/`graph_edge` rows
directly. The graph builder populates those rows during ingestion.
The graph API reads from them - it does not call the graph builder.

## Deferred until post-MVP
- Qdrant adapter
- Neo4j / Kùzu adapter
- LangGraph / LlamaIndex integration
- OAuth / multi-user auth
- UMAP + HDBSCAN clustering (schema only, no implementation yet)

## Naming conventions
- Python: snake_case, Pydantic v2 models, async SQLAlchemy 2.0
- TypeScript: camelCase components, PascalCase types
- Database: snake_case tables and columns, UUID primary keys
- API routes: /api/v1/{resource}

## Open decisions log
Unresolved decisions must be listed at the end of each session output.
Format: "OPEN: [decision needed] — [options]"