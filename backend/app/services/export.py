import csv
import io
import uuid
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk, Document
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Claim, Concept, Entity
from app.models.workspace import Project


class ExportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def export_json(self, project_id: uuid.UUID) -> dict[str, Any]:
        project = await self._project(project_id)
        documents = await self._rows(Document, Document.project_id == project_id)
        chunks = await self._rows(Chunk, Chunk.project_id == project_id)
        entities = await self._rows(Entity, Entity.project_id == project_id)
        concepts = await self._rows(Concept, Concept.project_id == project_id)
        claims = await self._rows(Claim, Claim.project_id == project_id)
        nodes = await self._rows(GraphNode, GraphNode.project_id == project_id)
        edges = await self._rows(GraphEdge, GraphEdge.project_id == project_id)
        return {
            "project": _project_dict(project),
            "documents": [_document_dict(row) for row in documents],
            "chunks": [_chunk_dict(row) for row in chunks],
            "entities": [_entity_dict(row) for row in entities],
            "concepts": [_concept_dict(row) for row in concepts],
            "claims": [_claim_dict(row) for row in claims],
            "nodes": [_node_dict(row) for row in nodes],
            "edges": [_edge_dict(row) for row in edges],
        }

    async def export_graphml(self, project_id: uuid.UUID) -> str:
        nodes = await self._rows(GraphNode, GraphNode.project_id == project_id)
        edges = await self._rows(GraphEdge, GraphEdge.project_id == project_id)
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
            '  <key id="node_type" for="node" attr.name="node_type" attr.type="string"/>',
            '  <key id="ref_id" for="node" attr.name="ref_id" attr.type="string"/>',
            '  <key id="edge_type" for="edge" attr.name="edge_type" attr.type="string"/>',
            '  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
            '  <key id="confidence" for="edge" attr.name="confidence" attr.type="double"/>',
            '  <key id="evidence_chunk_id" for="edge" attr.name="evidence_chunk_id" attr.type="string"/>',
            '  <key id="metadata" for="all" attr.name="metadata" attr.type="string"/>',
            '  <graph edgedefault="directed">',
        ]
        for node in nodes:
            lines.extend(
                [
                    f'    <node id="{node.id}">',
                    f'      <data key="label">{escape(node.label)}</data>',
                    f'      <data key="node_type">{escape(node.node_type)}</data>',
                    f'      <data key="ref_id">{escape(str(node.ref_id or ""))}</data>',
                    f'      <data key="metadata">{escape(str(node.metadata_))}</data>',
                    "    </node>",
                ]
            )
        for edge in edges:
            lines.extend(
                [
                    f'    <edge id="{edge.id}" source="{edge.source_node_id}" target="{edge.target_node_id}">',
                    f'      <data key="edge_type">{escape(edge.edge_type)}</data>',
                    f'      <data key="weight">{edge.weight}</data>',
                    f'      <data key="confidence">{edge.confidence}</data>',
                    f'      <data key="evidence_chunk_id">{edge.evidence_chunk_id}</data>',
                    f'      <data key="metadata">{escape(str(edge.metadata_))}</data>',
                    "    </edge>",
                ]
            )
        lines.extend(["  </graph>", "</graphml>"])
        return "\n".join(lines)

    async def export_csv(self, project_id: uuid.UUID) -> dict[str, str]:
        nodes = await self._rows(GraphNode, GraphNode.project_id == project_id)
        edges = await self._rows(GraphEdge, GraphEdge.project_id == project_id)
        entities = await self._rows(Entity, Entity.project_id == project_id)
        chunks = await self._rows(Chunk, Chunk.project_id == project_id)
        return {
            "nodes.csv": _csv_string([_node_dict(row) for row in nodes]),
            "edges.csv": _csv_string([_edge_dict(row) for row in edges]),
            "entities.csv": _csv_string([_entity_dict(row) for row in entities]),
            "chunks.csv": _csv_string([_chunk_dict(row) for row in chunks]),
        }

    async def export_markdown(self, project_id: uuid.UUID) -> str:
        project = await self._project(project_id)
        documents = await self._rows(Document, Document.project_id == project_id)
        entities = await self._rows(Entity, Entity.project_id == project_id)
        concepts = await self._rows(Concept, Concept.project_id == project_id)
        claims = await self._rows(Claim, Claim.project_id == project_id)
        chunks_by_id = {chunk.id: chunk for chunk in await self._rows(Chunk, Chunk.project_id == project_id)}
        lines = [
            f"# {project.name}",
            "",
            "## Entities",
            "| Name | Type | Description |",
            "|---|---|---|",
            *[f"| {entity.canonical_name} | {entity.entity_type} | {entity.description or ''} |" for entity in entities],
            "",
            "## Concepts",
            "| Name | Description |",
            "|---|---|",
            *[f"| {concept.name} | {concept.description or ''} |" for concept in concepts],
            "",
            "## Claims",
            "| Subject | Predicate | Object | Confidence | Evidence |",
            "|---|---|---|---:|---|",
        ]
        for claim in claims:
            chunk = chunks_by_id.get(claim.chunk_id)
            citation = chunk.citation if chunk else str(claim.chunk_id)
            lines.append(
                f"| {claim.subject} | {claim.predicate} | {claim.object} | {claim.confidence:.2f} | {claim.evidence_text} [{citation}] |"
            )
        lines.extend(
            [
                "",
                "## Document list",
                "| Title | Source type | Source URI | Status |",
                "|---|---|---|---|",
                *[f"| {document.title} | {document.source_type} | {document.source_uri or ''} | {document.status.value} |" for document in documents],
            ]
        )
        return "\n".join(lines)

    async def _project(self, project_id: uuid.UUID) -> Project:
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        return project

    async def _rows(self, model: Any, where_clause: Any) -> list[Any]:
        result = await self.db.execute(select(model).where(where_clause))
        return list(result.scalars().all())


def _csv_string(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _project_dict(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "name": project.name,
        "description": project.description,
        "domain": project.domain,
        "ontology_config": project.ontology_config,
        "embedding_config": project.embedding_config,
        "extraction_config": project.extraction_config,
        "graph_config": project.graph_config,
    }


def _document_dict(document: Document) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "project_id": str(document.project_id),
        "title": document.title,
        "source_type": document.source_type,
        "source_uri": document.source_uri,
        "author": document.author,
        "date": document.date,
        "tradition": document.tradition,
        "region": document.region,
        "language": document.language,
        "metadata": document.metadata_,
        "status": document.status.value,
    }


def _chunk_dict(chunk: Chunk) -> dict[str, Any]:
    return {
        "id": str(chunk.id),
        "project_id": str(chunk.project_id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "citation": chunk.citation,
        "metadata": chunk.metadata_,
    }


def _entity_dict(entity: Entity) -> dict[str, Any]:
    return {
        "id": str(entity.id),
        "project_id": str(entity.project_id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "aliases": entity.aliases,
        "description": entity.description,
        "metadata": entity.metadata_,
    }


def _concept_dict(concept: Concept) -> dict[str, Any]:
    return {
        "id": str(concept.id),
        "project_id": str(concept.project_id),
        "name": concept.name,
        "description": concept.description,
        "aliases": concept.aliases,
        "metadata": concept.metadata_,
    }


def _claim_dict(claim: Claim) -> dict[str, Any]:
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
    }


def _node_dict(node: GraphNode) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "project_id": str(node.project_id),
        "node_type": node.node_type,
        "ref_id": str(node.ref_id) if node.ref_id else "",
        "label": node.label,
        "metadata": node.metadata_,
    }


def _edge_dict(edge: GraphEdge) -> dict[str, Any]:
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
    }
