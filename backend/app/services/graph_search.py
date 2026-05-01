import uuid
from collections import deque
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdge, GraphNode


class GraphNodeResult(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    node_type: str
    ref_id: uuid.UUID | None
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeResult(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: str
    weight: float
    confidence: float
    evidence_chunk_id: uuid.UUID
    metadata: dict[str, Any] = Field(default_factory=dict)


class Subgraph(BaseModel):
    nodes: list[GraphNodeResult] = Field(default_factory=list)
    edges: list[GraphEdgeResult] = Field(default_factory=list)


class GraphSearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_neighborhood(self, node_id: uuid.UUID, depth: int, project_id: uuid.UUID) -> Subgraph:
        max_depth = min(max(depth, 0), 5)
        visited_nodes = {node_id}
        visited_edges: dict[uuid.UUID, GraphEdge] = {}
        frontier = {node_id}

        for _ in range(max_depth):
            if not frontier:
                break
            result = await self.db.execute(
                select(GraphEdge).where(
                    GraphEdge.project_id == project_id,
                    or_(GraphEdge.source_node_id.in_(frontier), GraphEdge.target_node_id.in_(frontier)),
                )
            )
            next_frontier: set[uuid.UUID] = set()
            for edge in result.scalars().all():
                visited_edges[edge.id] = edge
                for candidate_id in (edge.source_node_id, edge.target_node_id):
                    if candidate_id not in visited_nodes:
                        visited_nodes.add(candidate_id)
                        next_frontier.add(candidate_id)
            frontier = next_frontier

        nodes = await self._load_nodes(visited_nodes, project_id)
        return Subgraph(
            nodes=[_node_result(node) for node in nodes],
            edges=[_edge_result(edge) for edge in visited_edges.values()],
        )

    async def find_entity_nodes(self, entity_name: str, project_id: uuid.UUID) -> list[GraphNode]:
        result = await self.db.execute(
            select(GraphNode).where(
                GraphNode.project_id == project_id,
                GraphNode.node_type == "entity",
                GraphNode.label.ilike(f"%{entity_name}%"),
            )
        )
        return list(result.scalars().all())

    async def get_evidence_path(
        self,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[GraphEdgeResult]:
        if source_node_id == target_node_id:
            return []

        queue: deque[tuple[uuid.UUID, list[GraphEdge]]] = deque([(source_node_id, [])])
        visited = {source_node_id}

        while queue:
            current_node_id, path = queue.popleft()
            if len(path) >= 5:
                continue

            result = await self.db.execute(
                select(GraphEdge).where(
                    GraphEdge.project_id == project_id,
                    or_(GraphEdge.source_node_id == current_node_id, GraphEdge.target_node_id == current_node_id),
                )
            )
            for edge in result.scalars().all():
                next_node_id = edge.target_node_id if edge.source_node_id == current_node_id else edge.source_node_id
                if next_node_id in visited:
                    continue
                next_path = [*path, edge]
                if next_node_id == target_node_id:
                    return [_edge_result(path_edge) for path_edge in next_path]
                visited.add(next_node_id)
                queue.append((next_node_id, next_path))

        return []

    async def _load_nodes(self, node_ids: set[uuid.UUID], project_id: uuid.UUID) -> list[GraphNode]:
        if not node_ids:
            return []
        result = await self.db.execute(
            select(GraphNode).where(GraphNode.project_id == project_id, GraphNode.id.in_(node_ids))
        )
        return list(result.scalars().all())


def _node_result(node: GraphNode) -> GraphNodeResult:
    return GraphNodeResult(
        id=node.id,
        project_id=node.project_id,
        node_type=node.node_type,
        ref_id=node.ref_id,
        label=node.label,
        metadata=node.metadata_,
    )


def _edge_result(edge: GraphEdge) -> GraphEdgeResult:
    return GraphEdgeResult(
        id=edge.id,
        project_id=edge.project_id,
        source_node_id=edge.source_node_id,
        target_node_id=edge.target_node_id,
        edge_type=edge.edge_type,
        weight=edge.weight,
        confidence=edge.confidence,
        evidence_chunk_id=edge.evidence_chunk_id,
        metadata=edge.metadata_,
    )
