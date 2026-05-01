import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Chunk
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Claim, Entity
from app.models.workspace import Project

router = APIRouter(tags=["entities"])


@router.get("/projects/{project_id}/entities")
async def list_entities(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    if not await db.get(Project, project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    result = await db.execute(select(Entity).where(Entity.project_id == project_id).order_by(Entity.canonical_name))
    return {"message": "Entities listed.", "data": {"project_id": str(project_id), "items": [_serialize_entity(entity) for entity in result.scalars()]}}


@router.get("/entities/{entity_id}/detail")
async def get_entity_detail(entity_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    chunk_ids = _source_chunk_ids(entity)
    chunks = []
    claims = []
    if chunk_ids:
        chunk_result = await db.execute(select(Chunk).where(Chunk.id.in_(chunk_ids), Chunk.project_id == entity.project_id).order_by(Chunk.chunk_index))
        chunks = list(chunk_result.scalars().all())
        claim_result = await db.execute(
            select(Claim)
            .where(
                Claim.project_id == entity.project_id,
                Claim.chunk_id.in_([chunk.id for chunk in chunks]),
                or_(Claim.subject.ilike(f"%{entity.canonical_name}%"), Claim.object.ilike(f"%{entity.canonical_name}%")),
            )
            .order_by(Claim.confidence.desc(), Claim.created_at)
        )
        claims = list(claim_result.scalars().all())

    graph_node_result = await db.execute(
        select(GraphNode).where(GraphNode.project_id == entity.project_id, GraphNode.node_type == "entity", GraphNode.ref_id == entity.id)
    )
    graph_node = graph_node_result.scalar_one_or_none()
    edges = []
    connected_nodes = []
    if graph_node:
        edge_result = await db.execute(
            select(GraphEdge)
            .where(
                GraphEdge.project_id == entity.project_id,
                or_(GraphEdge.source_node_id == graph_node.id, GraphEdge.target_node_id == graph_node.id),
            )
            .order_by(GraphEdge.weight.desc(), GraphEdge.created_at)
            .limit(100)
        )
        edges = list(edge_result.scalars().all())
        connected_ids = {
            edge.target_node_id if edge.source_node_id == graph_node.id else edge.source_node_id
            for edge in edges
        }
        if connected_ids:
            node_result = await db.execute(select(GraphNode).where(GraphNode.project_id == entity.project_id, GraphNode.id.in_(connected_ids)))
            connected_nodes = list(node_result.scalars().all())

    return {
        "message": "Entity detail.",
        "data": {
            "entity": _serialize_entity(entity),
            "graph_node": _serialize_node(graph_node) if graph_node else None,
            "chunks": [_serialize_chunk(chunk) for chunk in chunks],
            "claims": [_serialize_claim(claim) for claim in claims],
            "connected_nodes": [_serialize_node(node) for node in connected_nodes],
            "edges": [_serialize_edge(edge) for edge in edges],
        },
    }


def _source_chunk_ids(entity: Entity) -> list[uuid.UUID]:
    chunk_ids: list[uuid.UUID] = []
    for value in entity.metadata_.get("source_chunk_ids", []):
        try:
            chunk_ids.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    return chunk_ids


def _serialize_entity(entity: Entity) -> dict[str, object]:
    return {
        "id": str(entity.id),
        "project_id": str(entity.project_id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "aliases": entity.aliases,
        "description": entity.description,
        "metadata": entity.metadata_,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }


def _serialize_chunk(chunk: Chunk) -> dict[str, object]:
    return {
        "id": str(chunk.id),
        "project_id": str(chunk.project_id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "citation": chunk.citation,
        "metadata": chunk.metadata_,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
    }


def _serialize_claim(claim: Claim) -> dict[str, object]:
    return {
        "id": str(claim.id),
        "project_id": str(claim.project_id),
        "chunk_id": str(claim.chunk_id),
        "subject": claim.subject,
        "predicate": claim.predicate,
        "object": claim.object,
        "confidence": claim.confidence,
        "evidence_text": claim.evidence_text,
        "metadata": claim.metadata_,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
    }


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
