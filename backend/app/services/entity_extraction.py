import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Entity
from app.models.workspace import Project
from app.providers.base import LLMProvider


@dataclass(frozen=True)
class ExtractedEntity:
    text: str
    entity_type: str
    start_char: int
    end_char: int
    confidence: float


class EntityExtractor:
    def __init__(self, db: AsyncSession, llm_provider: LLMProvider) -> None:
        self.db = db
        self.llm_provider = llm_provider

    async def extract(self, chunk: Chunk) -> list[ExtractedEntity]:
        project = await self.db.get(Project, chunk.project_id)
        valid_entity_types = self._valid_entity_types(project)
        prompt = self._build_prompt(chunk.text, valid_entity_types)
        response = await self.llm_provider.complete(prompt, system=self._system_prompt())
        payload = _parse_json_object(response)
        entities = payload.get("entities", [])
        return [entity for item in entities if (entity := self._coerce_entity(item, chunk.text))]

    async def extract_and_store(self, chunk: Chunk) -> list[Entity]:
        extracted_entities = await self.extract(chunk)
        stored_entities: list[Entity] = []
        chunk_node = await self._get_or_create_node("chunk", chunk.id, chunk.project_id, chunk.citation, {})

        for extracted in extracted_entities:
            entity = await self._get_or_create_entity(chunk, extracted)
            stored_entities.append(entity)
            entity_node = await self._get_or_create_node(
                "entity",
                entity.id,
                chunk.project_id,
                entity.canonical_name,
                {"entity_type": entity.entity_type},
            )
            await self._get_or_create_edge(
                chunk.project_id,
                chunk_node.id,
                entity_node.id,
                "chunk_mentions_entity",
                extracted.confidence,
                chunk.id,
                {"start_char": extracted.start_char, "end_char": extracted.end_char},
            )

        await self.db.commit()
        return stored_entities

    def _valid_entity_types(self, project: Project | None) -> list[str]:
        ontology_config = project.ontology_config if project else {}
        values = ontology_config.get("entity_types") or ontology_config.get("entities") or []
        return [str(value) for value in values] or ["person", "place", "organization", "text", "tradition", "event", "artifact"]

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You extract only explicitly mentioned entities from source text. "
            "Never invent entities, normalize cautiously, and return only valid JSON."
        )

    @staticmethod
    def _build_prompt(text: str, valid_entity_types: list[str]) -> str:
        return f"""
Extract entities from the chunk below.

Rules:
- Use only these entity_type values: {valid_entity_types}
- Return only entities explicitly mentioned in the text.
- Never invent entities or infer unstated entities.
- Include start_char and end_char offsets relative to the chunk text.
- Include confidence from 0.0 to 1.0.
- Return JSON only in this shape:
{{"entities":[{{"text":"...", "entity_type":"...", "start_char":0, "end_char":10, "confidence":0.95}}]}}

Chunk text:
{text}
""".strip()

    def _coerce_entity(self, item: dict[str, Any], chunk_text: str) -> ExtractedEntity | None:
        text = str(item.get("text", "")).strip()
        entity_type = str(item.get("entity_type", "")).strip()
        if not text or text not in chunk_text:
            return None
        start_char = int(item.get("start_char", chunk_text.find(text)))
        end_char = int(item.get("end_char", start_char + len(text)))
        if start_char < 0 or end_char <= start_char or chunk_text[start_char:end_char] != text:
            start_char = chunk_text.find(text)
            end_char = start_char + len(text)
        confidence = min(1.0, max(0.0, float(item.get("confidence", 0.0))))
        return ExtractedEntity(text=text, entity_type=entity_type, start_char=start_char, end_char=end_char, confidence=confidence)

    async def _get_or_create_entity(self, chunk: Chunk, extracted: ExtractedEntity) -> Entity:
        result = await self.db.execute(
            select(Entity).where(
                Entity.project_id == chunk.project_id,
                Entity.canonical_name == extracted.text,
                Entity.entity_type == extracted.entity_type,
            )
        )
        entity = result.scalar_one_or_none()
        if entity:
            source_chunks = set(entity.metadata_.get("source_chunk_ids", []))
            source_chunks.add(str(chunk.id))
            entity.metadata_ = {**entity.metadata_, "source_chunk_ids": sorted(source_chunks)}
            return entity
        entity = Entity(
            project_id=chunk.project_id,
            canonical_name=extracted.text,
            entity_type=extracted.entity_type,
            aliases=[],
            metadata_={
                "source_chunk_ids": [str(chunk.id)],
                "mentions": [{"chunk_id": str(chunk.id), "start_char": extracted.start_char, "end_char": extracted.end_char}],
                "confidence": extracted.confidence,
            },
        )
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def _get_or_create_node(self, node_type: str, ref_id: uuid.UUID, project_id: uuid.UUID, label: str, metadata: dict[str, Any]) -> GraphNode:
        result = await self.db.execute(
            select(GraphNode).where(GraphNode.project_id == project_id, GraphNode.node_type == node_type, GraphNode.ref_id == ref_id)
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
            return edge
        edge = GraphEdge(
            project_id=project_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            weight=1.0,
            confidence=confidence,
            evidence_chunk_id=evidence_chunk_id,
            metadata_=metadata,
        )
        self.db.add(edge)
        await self.db.flush()
        return edge


def _parse_json_object(response: str) -> dict[str, Any]:
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}
