import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk, Document
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Entity


class GraphBuilder:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_document_nodes(self, document_id: uuid.UUID) -> GraphNode:
        document = await self.db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")
        node = await self._get_or_create_node(
            document.project_id,
            "document",
            document.id,
            document.title,
            {"source_uri": document.source_uri, "source_type": document.source_type},
        )
        await self.db.commit()
        return node

    async def build_chunk_nodes(self, document_id: uuid.UUID) -> list[GraphNode]:
        document = await self.db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")
        document_node = await self.build_document_nodes(document_id)
        result = await self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        nodes: list[GraphNode] = []
        for chunk in chunks:
            chunk_node = await self._get_or_create_node(
                chunk.project_id,
                "chunk",
                chunk.id,
                chunk.citation,
                {"document_id": str(chunk.document_id), "chunk_index": chunk.chunk_index},
            )
            nodes.append(chunk_node)
            await self._get_or_create_edge(
                chunk.project_id,
                document_node.id,
                chunk_node.id,
                "contains",
                weight=1.0,
                confidence=1.0,
                evidence_chunk_id=chunk.id,
                metadata={"document_id": str(document.id), "chunk_index": chunk.chunk_index},
            )
        await self.db.commit()
        return nodes

    async def build_entity_nodes(self, project_id: uuid.UUID) -> list[GraphNode]:
        entity_result = await self.db.execute(select(Entity).where(Entity.project_id == project_id))
        entities = list(entity_result.scalars().all())
        nodes: list[GraphNode] = []
        for entity in entities:
            entity_node = await self._get_or_create_node(
                project_id,
                "entity",
                entity.id,
                entity.canonical_name,
                {"entity_type": entity.entity_type},
            )
            nodes.append(entity_node)
            for source_chunk_id in entity.metadata_.get("source_chunk_ids", []):
                chunk_id = uuid.UUID(source_chunk_id)
                chunk = await self.db.get(Chunk, chunk_id)
                if not chunk or chunk.project_id != project_id:
                    continue
                chunk_node = await self._get_or_create_node(project_id, "chunk", chunk.id, chunk.citation, {})
                await self._get_or_create_edge(
                    project_id,
                    chunk_node.id,
                    entity_node.id,
                    "mentions",
                    weight=1.0,
                    confidence=float(entity.metadata_.get("confidence", 1.0)),
                    evidence_chunk_id=chunk.id,
                    metadata={"entity_type": entity.entity_type},
                )
        await self.db.commit()
        return nodes

    async def build_semantic_edges(self, project_id: uuid.UUID, similarity_threshold: float = 0.85) -> list[GraphEdge]:
        result = await self.db.execute(
            text(
                """
                SELECT
                  c1.id AS source_chunk_id,
                  c2.id AS target_chunk_id,
                  1 - (ce1.embedding <=> ce2.embedding) AS similarity
                FROM chunk c1
                JOIN chunk_embedding ce1 ON ce1.chunk_id = c1.id
                JOIN chunk c2
                  ON c2.project_id = c1.project_id
                 AND c1.id::text < c2.id::text
                JOIN chunk_embedding ce2
                  ON ce2.chunk_id = c2.id
                 AND ce2.provider = ce1.provider
                 AND ce2.model = ce1.model
                WHERE c1.project_id = :project_id
                  AND 1 - (ce1.embedding <=> ce2.embedding) >= :similarity_threshold
                """
            ),
            {"project_id": project_id, "similarity_threshold": similarity_threshold},
        )
        edges: list[GraphEdge] = []
        for row in result.mappings():
            source_chunk = await self.db.get(Chunk, row["source_chunk_id"])
            target_chunk = await self.db.get(Chunk, row["target_chunk_id"])
            if not source_chunk or not target_chunk:
                continue
            source_node = await self._get_or_create_node(project_id, "chunk", source_chunk.id, source_chunk.citation, {})
            target_node = await self._get_or_create_node(project_id, "chunk", target_chunk.id, target_chunk.citation, {})
            edge = await self._get_or_create_edge(
                project_id,
                source_node.id,
                target_node.id,
                "semantically_similar",
                weight=float(row["similarity"]),
                confidence=float(row["similarity"]),
                evidence_chunk_id=source_chunk.id,
                metadata={"target_evidence_chunk_id": str(target_chunk.id), "undirected": True},
            )
            edges.append(edge)
        await self.db.commit()
        return edges

    async def build_cooccurrence_edges(self, project_id: uuid.UUID) -> list[GraphEdge]:
        entity_result = await self.db.execute(select(Entity).where(Entity.project_id == project_id))
        chunk_to_entities: dict[str, list[Entity]] = defaultdict(list)
        for entity in entity_result.scalars().all():
            for source_chunk_id in entity.metadata_.get("source_chunk_ids", []):
                chunk_to_entities[source_chunk_id].append(entity)

        pair_counts: dict[tuple[uuid.UUID, uuid.UUID], tuple[int, uuid.UUID]] = {}
        for source_chunk_id, entities in chunk_to_entities.items():
            sorted_entities = sorted(entities, key=lambda item: str(item.id))
            for index, source_entity in enumerate(sorted_entities):
                for target_entity in sorted_entities[index + 1 :]:
                    key = (source_entity.id, target_entity.id)
                    current_count, _ = pair_counts.get(key, (0, uuid.UUID(source_chunk_id)))
                    pair_counts[key] = (current_count + 1, uuid.UUID(source_chunk_id))

        edges: list[GraphEdge] = []
        for (source_entity_id, target_entity_id), (weight, evidence_chunk_id) in pair_counts.items():
            source_entity = await self.db.get(Entity, source_entity_id)
            target_entity = await self.db.get(Entity, target_entity_id)
            if not source_entity or not target_entity:
                continue
            source_node = await self._get_or_create_node(project_id, "entity", source_entity.id, source_entity.canonical_name, {})
            target_node = await self._get_or_create_node(project_id, "entity", target_entity.id, target_entity.canonical_name, {})
            edge = await self._get_or_create_edge(
                project_id,
                source_node.id,
                target_node.id,
                "co_occurs_with",
                weight=float(weight),
                confidence=1.0,
                evidence_chunk_id=evidence_chunk_id,
                metadata={"cooccurring_chunk_count": weight, "undirected": True},
            )
            edges.append(edge)
        await self.db.commit()
        return edges

    async def _get_or_create_node(
        self,
        project_id: uuid.UUID,
        node_type: str,
        ref_id: uuid.UUID,
        label: str,
        metadata: dict[str, Any],
    ) -> GraphNode:
        result = await self.db.execute(
            select(GraphNode).where(
                GraphNode.project_id == project_id,
                GraphNode.node_type == node_type,
                GraphNode.ref_id == ref_id,
            )
        )
        node = result.scalar_one_or_none()
        if node:
            return node
        node = GraphNode(project_id=project_id, node_type=node_type, ref_id=ref_id, label=label, metadata_=metadata)
        self.db.add(node)
        await self.db.flush()
        return node

    async def _get_or_create_edge(
        self,
        project_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        edge_type: str,
        weight: float,
        confidence: float,
        evidence_chunk_id: uuid.UUID,
        metadata: dict[str, Any],
    ) -> GraphEdge:
        result = await self.db.execute(
            select(GraphEdge).where(
                GraphEdge.project_id == project_id,
                GraphEdge.source_node_id == source_node_id,
                GraphEdge.target_node_id == target_node_id,
                GraphEdge.edge_type == edge_type,
                GraphEdge.evidence_chunk_id == evidence_chunk_id,
            )
        )
        edge = result.scalar_one_or_none()
        if edge:
            edge.weight = weight
            edge.confidence = confidence
            edge.metadata_ = {**edge.metadata_, **metadata}
            return edge
        edge = GraphEdge(
            project_id=project_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            weight=weight,
            confidence=confidence,
            evidence_chunk_id=evidence_chunk_id,
            metadata_=metadata,
        )
        self.db.add(edge)
        await self.db.flush()
        return edge
