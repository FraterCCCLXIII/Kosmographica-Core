from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Chunk
from app.models.graph import GraphEdge, GraphNode
from app.models.workspace import Project

router = APIRouter(tags=["graph"])


@router.get("/projects/{project_id}/graph/nodes")
async def get_project_graph_nodes(
    project_id: UUID,
    limit: int = Query(500, ge=1, le=5_000),
    offset: int = Query(0, ge=0),
    node_type: str | None = None,
    query: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _list_nodes(project_id, db, limit=limit, offset=offset, node_type=node_type, query=query)


@router.get("/graph/nodes")
async def get_graph_nodes(
    project_id: UUID = Query(...),
    limit: int = Query(500, ge=1, le=5_000),
    offset: int = Query(0, ge=0),
    node_type: str | None = None,
    query: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _list_nodes(project_id, db, limit=limit, offset=offset, node_type=node_type, query=query)


@router.get("/projects/{project_id}/graph/edges")
async def get_project_graph_edges(
    project_id: UUID,
    edge_type: str | None = Query("mentions,contains,supports_claim"),
    limit: int = Query(500, ge=1, le=10_000),
    min_weight: float | None = Query(None),
    document_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _list_edges(project_id, db, edge_type=edge_type, limit=limit, min_weight=min_weight, document_id=document_id)


@router.get("/graph/edges")
async def get_graph_edges(
    project_id: UUID = Query(...),
    edge_type: str | None = Query("mentions,contains,supports_claim"),
    limit: int = Query(500, ge=1, le=10_000),
    min_weight: float | None = Query(None),
    document_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _list_edges(project_id, db, edge_type=edge_type, limit=limit, min_weight=min_weight, document_id=document_id)


@router.get("/projects/{project_id}/graph/stats")
async def get_project_graph_stats(project_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return await _graph_stats(project_id, db)


@router.get("/graph/stats")
async def get_graph_stats(project_id: UUID = Query(...), db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return await _graph_stats(project_id, db)


@router.get("/projects/{project_id}/graph/subgraph")
async def get_project_subgraph(
    project_id: UUID,
    node_id: UUID | None = None,
    depth: int = Query(1, ge=0, le=5),
    edge_type: str | None = Query("mentions,contains,supports_claim"),
    limit: int = Query(1_000, ge=1, le=10_000),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _subgraph(project_id, node_id, depth, db, edge_type=edge_type, limit=limit)


@router.get("/graph/subgraph")
async def get_subgraph(
    project_id: UUID = Query(...),
    node_id: UUID | None = None,
    depth: int = Query(1, ge=0, le=5),
    edge_type: str | None = Query("mentions,contains,supports_claim"),
    limit: int = Query(1_000, ge=1, le=10_000),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _subgraph(project_id, node_id, depth, db, edge_type=edge_type, limit=limit)


@router.get("/projects/{project_id}/graph/search")
async def search_project_graph(
    project_id: UUID,
    query: str = Query(..., min_length=1),
    node_type: str | None = None,
    edge_type: str | None = Query("mentions,contains,supports_claim"),
    depth: int = Query(1, ge=0, le=3),
    seed_limit: int = Query(25, ge=1, le=100),
    node_limit: int = Query(250, ge=1, le=1_000),
    edge_limit: int = Query(500, ge=1, le=2_000),
    min_weight: float | None = Query(None),
    document_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _search_graph(
        project_id,
        db,
        query=query,
        node_type=node_type,
        edge_type=edge_type,
        depth=depth,
        seed_limit=seed_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
        min_weight=min_weight,
        document_id=document_id,
    )


@router.get("/graph/search")
async def search_graph(
    project_id: UUID = Query(...),
    query: str = Query(..., min_length=1),
    node_type: str | None = None,
    edge_type: str | None = Query("mentions,contains,supports_claim"),
    depth: int = Query(1, ge=0, le=3),
    seed_limit: int = Query(25, ge=1, le=100),
    node_limit: int = Query(250, ge=1, le=1_000),
    edge_limit: int = Query(500, ge=1, le=2_000),
    min_weight: float | None = Query(None),
    document_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _search_graph(
        project_id,
        db,
        query=query,
        node_type=node_type,
        edge_type=edge_type,
        depth=depth,
        seed_limit=seed_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
        min_weight=min_weight,
        document_id=document_id,
    )


async def _list_nodes(
    project_id: UUID,
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    node_type: str | None,
    query: str | None,
) -> dict[str, object]:
    await _ensure_project(project_id, db)
    node_types = _parse_csv(node_type)
    statement = select(GraphNode).where(GraphNode.project_id == project_id)
    count_statement = select(func.count()).select_from(GraphNode).where(GraphNode.project_id == project_id)
    if node_types:
        statement = statement.where(GraphNode.node_type.in_(node_types))
        count_statement = count_statement.where(GraphNode.node_type.in_(node_types))
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(GraphNode.label.ilike(pattern), cast(GraphNode.metadata_, Text).ilike(pattern)))
        count_statement = count_statement.where(or_(GraphNode.label.ilike(pattern), cast(GraphNode.metadata_, Text).ilike(pattern)))
    result = await db.execute(statement.order_by(GraphNode.created_at).offset(offset).limit(limit))
    total = (await db.execute(count_statement)).scalar_one()
    nodes = list(result.scalars().all())
    return {
        "message": "Graph nodes listed.",
        "data": {
            "project_id": str(project_id),
            "items": await _serialize_nodes(nodes, db),
            "total": total,
            "limit": limit,
            "offset": offset,
            "node_types": node_types,
        },
    }


async def _list_edges(
    project_id: UUID,
    db: AsyncSession,
    *,
    edge_type: str | None,
    limit: int,
    min_weight: float | None,
    document_id: UUID | None,
) -> dict[str, object]:
    await _ensure_project(project_id, db)
    edge_types = _parse_csv(edge_type)
    statement = select(GraphEdge).where(GraphEdge.project_id == project_id)
    count_statement = select(func.count()).select_from(GraphEdge).where(GraphEdge.project_id == project_id)
    if edge_types:
        statement = statement.where(GraphEdge.edge_type.in_(edge_types))
        count_statement = count_statement.where(GraphEdge.edge_type.in_(edge_types))
    if min_weight is not None:
        statement = statement.where(GraphEdge.weight >= min_weight)
        count_statement = count_statement.where(GraphEdge.weight >= min_weight)
    if document_id is not None:
        statement = statement.join_from(GraphEdge, Chunk, GraphEdge.evidence_chunk_id == Chunk.id).where(Chunk.document_id == document_id)
        count_statement = count_statement.join_from(GraphEdge, Chunk, GraphEdge.evidence_chunk_id == Chunk.id).where(Chunk.document_id == document_id)
    result = await db.execute(statement.order_by(GraphEdge.weight.desc(), GraphEdge.created_at).limit(limit))
    total = (await db.execute(count_statement)).scalar_one()
    return {
        "message": "Graph edges listed.",
        "data": {
            "project_id": str(project_id),
            "items": [_serialize_edge(edge) for edge in result.scalars()],
            "total": total,
            "limit": limit,
            "edge_types": edge_types,
        },
    }


async def _graph_stats(project_id: UUID, db: AsyncSession) -> dict[str, object]:
    await _ensure_project(project_id, db)
    node_count = (await db.execute(select(func.count()).select_from(GraphNode).where(GraphNode.project_id == project_id))).scalar_one()
    edge_count = (await db.execute(select(func.count()).select_from(GraphEdge).where(GraphEdge.project_id == project_id))).scalar_one()
    edge_type_result = await db.execute(
        select(GraphEdge.edge_type, func.count()).where(GraphEdge.project_id == project_id).group_by(GraphEdge.edge_type)
    )
    return {
        "message": "Graph stats.",
        "data": {
            "project_id": str(project_id),
            "node_count": node_count,
            "edge_count": edge_count,
            "edge_types": {edge_type: count for edge_type, count in edge_type_result.all()},
        },
    }


async def _subgraph(
    project_id: UUID,
    node_id: UUID | None,
    depth: int,
    db: AsyncSession,
    *,
    edge_type: str | None,
    limit: int,
) -> dict[str, object]:
    await _ensure_project(project_id, db)
    edge_types = _parse_csv(edge_type)
    if node_id is None:
        nodes = (await db.execute(select(GraphNode).where(GraphNode.project_id == project_id))).scalars().all()
        edge_statement = select(GraphEdge).where(GraphEdge.project_id == project_id)
        if edge_types:
            edge_statement = edge_statement.where(GraphEdge.edge_type.in_(edge_types))
        edges = (await db.execute(edge_statement.order_by(GraphEdge.weight.desc(), GraphEdge.created_at).limit(limit))).scalars().all()
        return {
            "message": "Project subgraph.",
            "data": {
                "project_id": str(project_id),
                "nodes": await _serialize_nodes(list(nodes), db),
                "edges": [_serialize_edge(edge) for edge in edges],
            },
        }

    start = await db.get(GraphNode, node_id)
    if not start or start.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Graph node not found: {node_id}")

    visited = {node_id}
    frontier = {node_id}
    edge_ids: set[UUID] = set()
    for _ in range(depth):
        if not frontier:
            break
        edge_statement = select(GraphEdge).where(
                GraphEdge.project_id == project_id,
                or_(GraphEdge.source_node_id.in_(frontier), GraphEdge.target_node_id.in_(frontier)),
            )
        if edge_types:
            edge_statement = edge_statement.where(GraphEdge.edge_type.in_(edge_types))
        edge_result = await db.execute(edge_statement.order_by(GraphEdge.weight.desc(), GraphEdge.created_at).limit(limit))
        next_frontier: set[UUID] = set()
        for edge in edge_result.scalars():
            edge_ids.add(edge.id)
            for candidate in (edge.source_node_id, edge.target_node_id):
                if candidate not in visited:
                    visited.add(candidate)
                    next_frontier.add(candidate)
        frontier = next_frontier

    node_result = await db.execute(select(GraphNode).where(GraphNode.id.in_(visited), GraphNode.project_id == project_id))
    edge_result = await db.execute(select(GraphEdge).where(GraphEdge.id.in_(edge_ids), GraphEdge.project_id == project_id))
    nodes = list(node_result.scalars().all())
    return {
        "message": "Graph neighborhood.",
        "data": {
            "project_id": str(project_id),
            "node_id": str(node_id),
            "depth": depth,
            "nodes": await _serialize_nodes(nodes, db),
            "edges": [_serialize_edge(edge) for edge in edge_result.scalars()],
        },
    }


async def _search_graph(
    project_id: UUID,
    db: AsyncSession,
    *,
    query: str,
    node_type: str | None,
    edge_type: str | None,
    depth: int,
    seed_limit: int,
    node_limit: int,
    edge_limit: int,
    min_weight: float | None,
    document_id: UUID | None,
) -> dict[str, object]:
    await _ensure_project(project_id, db)
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(status_code=422, detail="Search query cannot be empty.")

    edge_types = _parse_csv(edge_type)
    node_types = _parse_csv(node_type)
    pattern = f"%{normalized_query}%"
    seed_statement = select(GraphNode).where(
        GraphNode.project_id == project_id,
        or_(GraphNode.label.ilike(pattern), cast(GraphNode.metadata_, Text).ilike(pattern)),
    )
    if node_types:
        seed_statement = seed_statement.where(GraphNode.node_type.in_(node_types))
    seed_result = await db.execute(seed_statement.order_by(GraphNode.created_at).limit(seed_limit))
    seed_nodes = list(seed_result.scalars().all())

    visited = {node.id for node in seed_nodes}
    frontier = set(visited)
    edge_ids: set[UUID] = set()
    for _ in range(depth):
        if not frontier or len(visited) >= node_limit or len(edge_ids) >= edge_limit:
            break
        edge_statement = select(GraphEdge).where(
            GraphEdge.project_id == project_id,
            or_(GraphEdge.source_node_id.in_(frontier), GraphEdge.target_node_id.in_(frontier)),
        )
        if edge_types:
            edge_statement = edge_statement.where(GraphEdge.edge_type.in_(edge_types))
        if min_weight is not None:
            edge_statement = edge_statement.where(GraphEdge.weight >= min_weight)
        if document_id is not None:
            edge_statement = edge_statement.join_from(GraphEdge, Chunk, GraphEdge.evidence_chunk_id == Chunk.id).where(Chunk.document_id == document_id)
        remaining_edges = edge_limit - len(edge_ids)
        edge_result = await db.execute(edge_statement.order_by(GraphEdge.weight.desc(), GraphEdge.created_at).limit(remaining_edges))
        next_frontier: set[UUID] = set()
        for edge in edge_result.scalars():
            edge_ids.add(edge.id)
            for candidate in (edge.source_node_id, edge.target_node_id):
                if candidate not in visited and len(visited) < node_limit:
                    visited.add(candidate)
                    next_frontier.add(candidate)
        frontier = next_frontier

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    if visited:
        node_result = await db.execute(select(GraphNode).where(GraphNode.id.in_(visited), GraphNode.project_id == project_id))
        nodes = list(node_result.scalars().all())
    if edge_ids:
        edge_result = await db.execute(select(GraphEdge).where(GraphEdge.id.in_(edge_ids), GraphEdge.project_id == project_id))
        edges = list(edge_result.scalars().all())

    return {
        "message": "Graph search results.",
        "data": {
            "project_id": str(project_id),
            "query": normalized_query,
            "seed_node_ids": [str(node.id) for node in seed_nodes],
            "nodes": await _serialize_nodes(nodes, db),
            "edges": [_serialize_edge(edge) for edge in edges],
            "limits": {"seed_limit": seed_limit, "node_limit": node_limit, "edge_limit": edge_limit, "depth": depth},
            "edge_types": edge_types,
            "min_weight": min_weight,
            "document_id": str(document_id) if document_id else None,
        },
    }


async def _ensure_project(project_id: UUID, db: AsyncSession) -> None:
    if not await db.get(Project, project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")


async def _serialize_nodes(nodes: list[GraphNode], db: AsyncSession) -> list[dict[str, object]]:
    chunk_metadata = await _chunk_metadata_by_ref_id(nodes, db)
    return [_serialize_node(node, chunk_metadata.get(node.ref_id)) for node in nodes]


async def _chunk_metadata_by_ref_id(nodes: list[GraphNode], db: AsyncSession) -> dict[UUID, dict[str, object]]:
    chunk_ids = [node.ref_id for node in nodes if node.node_type == "chunk" and node.ref_id is not None]
    if not chunk_ids:
        return {}
    result = await db.execute(select(Chunk).where(Chunk.id.in_(chunk_ids)))
    return {
        chunk.id: {
            "text": chunk.text,
            "citation": chunk.citation,
            "document_id": str(chunk.document_id),
            "chunk_index": chunk.chunk_index,
            "token_count": chunk.token_count,
        }
        for chunk in result.scalars().all()
    }


def _serialize_node(node: GraphNode, chunk_metadata: dict[str, object] | None = None) -> dict[str, object]:
    metadata = dict(node.metadata_)
    if chunk_metadata:
        metadata.update(chunk_metadata)
    return {
        "id": str(node.id),
        "project_id": str(node.project_id),
        "node_type": node.node_type,
        "ref_id": str(node.ref_id) if node.ref_id else None,
        "label": node.label,
        "metadata": metadata,
        "created_at": node.created_at.isoformat() if node.created_at else None,
    }


def _serialize_edge(edge: GraphEdge) -> dict[str, object]:
    return {
        "id": str(edge.id),
        "project_id": str(edge.project_id),
        "source_node_id": str(edge.source_node_id),
        "target_node_id": str(edge.target_node_id),
        "edge_type": edge.edge_type,
        "weight": edge.weight,
        "confidence": edge.confidence,
        "evidence_chunk_id": str(edge.evidence_chunk_id),
        "metadata": edge.metadata_,
        "created_at": edge.created_at.isoformat() if edge.created_at else None,
    }


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
