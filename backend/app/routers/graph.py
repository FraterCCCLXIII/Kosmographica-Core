from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.graph import GraphEdge, GraphNode
from app.models.workspace import Project

router = APIRouter(tags=["graph"])


@router.get("/projects/{project_id}/graph/nodes")
async def get_project_graph_nodes(project_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return await _list_nodes(project_id, db)


@router.get("/graph/nodes")
async def get_graph_nodes(project_id: UUID = Query(...), db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return await _list_nodes(project_id, db)


@router.get("/projects/{project_id}/graph/edges")
async def get_project_graph_edges(project_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return await _list_edges(project_id, db)


@router.get("/graph/edges")
async def get_graph_edges(project_id: UUID = Query(...), db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return await _list_edges(project_id, db)


@router.get("/projects/{project_id}/graph/subgraph")
async def get_project_subgraph(
    project_id: UUID,
    node_id: UUID | None = None,
    depth: int = Query(1, ge=0, le=5),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _subgraph(project_id, node_id, depth, db)


@router.get("/graph/subgraph")
async def get_subgraph(
    project_id: UUID = Query(...),
    node_id: UUID | None = None,
    depth: int = Query(1, ge=0, le=5),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await _subgraph(project_id, node_id, depth, db)


async def _list_nodes(project_id: UUID, db: AsyncSession) -> dict[str, object]:
    await _ensure_project(project_id, db)
    result = await db.execute(select(GraphNode).where(GraphNode.project_id == project_id).order_by(GraphNode.created_at))
    return {
        "message": "Graph nodes listed.",
        "data": {"project_id": str(project_id), "items": [_serialize_node(node) for node in result.scalars()]},
    }


async def _list_edges(project_id: UUID, db: AsyncSession) -> dict[str, object]:
    await _ensure_project(project_id, db)
    result = await db.execute(select(GraphEdge).where(GraphEdge.project_id == project_id).order_by(GraphEdge.created_at))
    return {
        "message": "Graph edges listed.",
        "data": {"project_id": str(project_id), "items": [_serialize_edge(edge) for edge in result.scalars()]},
    }


async def _subgraph(project_id: UUID, node_id: UUID | None, depth: int, db: AsyncSession) -> dict[str, object]:
    await _ensure_project(project_id, db)
    if node_id is None:
        nodes = (await db.execute(select(GraphNode).where(GraphNode.project_id == project_id))).scalars().all()
        edges = (await db.execute(select(GraphEdge).where(GraphEdge.project_id == project_id))).scalars().all()
        return {
            "message": "Project subgraph.",
            "data": {
                "project_id": str(project_id),
                "nodes": [_serialize_node(node) for node in nodes],
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
        edge_result = await db.execute(
            select(GraphEdge).where(
                GraphEdge.project_id == project_id,
                or_(GraphEdge.source_node_id.in_(frontier), GraphEdge.target_node_id.in_(frontier)),
            )
        )
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
    return {
        "message": "Graph neighborhood.",
        "data": {
            "project_id": str(project_id),
            "node_id": str(node_id),
            "depth": depth,
            "nodes": [_serialize_node(node) for node in node_result.scalars()],
            "edges": [_serialize_edge(edge) for edge in edge_result.scalars()],
        },
    }


async def _ensure_project(project_id: UUID, db: AsyncSession) -> None:
    if not await db.get(Project, project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")


def _serialize_node(node: GraphNode) -> dict[str, object]:
    return {
        "id": str(node.id),
        "project_id": str(node.project_id),
        "node_type": node.node_type,
        "ref_id": str(node.ref_id) if node.ref_id else None,
        "label": node.label,
        "metadata": node.metadata_,
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
