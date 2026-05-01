import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Concept
from app.models.workspace import Project
from app.providers.base import LLMProvider
from app.services.entity_extraction import _parse_json_object


@dataclass(frozen=True)
class ExtractedConcept:
    text: str
    concept_type: str
    start_char: int
    end_char: int
    confidence: float


class ConceptExtractor:
    def __init__(self, db: AsyncSession, llm_provider: LLMProvider) -> None:
        self.db = db
        self.llm_provider = llm_provider

    async def extract(self, chunk: Chunk) -> list[ExtractedConcept]:
        project = await self.db.get(Project, chunk.project_id)
        concept_types = self._concept_types(project)
        prompt = self._build_prompt(chunk.text, concept_types)
        response = await self.llm_provider.complete(prompt, system=self._system_prompt())
        payload = _parse_json_object(response)
        concepts = payload.get("concepts", [])
        return [concept for item in concepts if (concept := self._coerce_concept(item, chunk.text))]

    async def extract_and_store(self, chunk: Chunk) -> list[Concept]:
        extracted_concepts = await self.extract(chunk)
        stored_concepts: list[Concept] = []
        chunk_node = await self._get_or_create_node("chunk", chunk.id, chunk.project_id, chunk.citation, {})

        for extracted in extracted_concepts:
            concept = await self._get_or_create_concept(chunk, extracted)
            stored_concepts.append(concept)
            concept_node = await self._get_or_create_node(
                "concept",
                concept.id,
                chunk.project_id,
                concept.name,
                {"concept_type": extracted.concept_type},
            )
            await self._get_or_create_edge(
                chunk.project_id,
                chunk_node.id,
                concept_node.id,
                "chunk_mentions_concept",
                extracted.confidence,
                chunk.id,
                {"start_char": extracted.start_char, "end_char": extracted.end_char, "concept_type": extracted.concept_type},
            )

        await self.db.commit()
        return stored_concepts

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You extract only abstract concepts explicitly present in source text. "
            "Do not infer unstated comparative concepts. Return only valid JSON."
        )

    @staticmethod
    def _concept_types(project: Project | None) -> list[str]:
        extraction_config = project.extraction_config if project else {}
        values = extraction_config.get("concept_types") or extraction_config.get("concepts") or []
        return [str(value) for value in values] or ["theme", "doctrine", "symbol", "motif", "practice", "relationship"]

    @staticmethod
    def _build_prompt(text: str, concept_types: list[str]) -> str:
        return f"""
Extract abstract concepts from the chunk below.

Rules:
- Use only these concept_type values: {concept_types}
- Return only concepts explicitly supported by wording in the text.
- Never invent concepts or collapse different traditions into vague sameness.
- Include start_char and end_char offsets for the textual evidence span.
- Include confidence from 0.0 to 1.0.
- Return JSON only in this shape:
{{"concepts":[{{"text":"...", "concept_type":"...", "start_char":0, "end_char":10, "confidence":0.95}}]}}

Chunk text:
{text}
""".strip()

    def _coerce_concept(self, item: dict[str, Any], chunk_text: str) -> ExtractedConcept | None:
        text = str(item.get("text", "")).strip()
        concept_type = str(item.get("concept_type", "")).strip()
        if not text or text not in chunk_text:
            return None
        start_char = int(item.get("start_char", chunk_text.find(text)))
        end_char = int(item.get("end_char", start_char + len(text)))
        if start_char < 0 or end_char <= start_char or chunk_text[start_char:end_char] != text:
            start_char = chunk_text.find(text)
            end_char = start_char + len(text)
        confidence = min(1.0, max(0.0, float(item.get("confidence", 0.0))))
        return ExtractedConcept(text=text, concept_type=concept_type, start_char=start_char, end_char=end_char, confidence=confidence)

    async def _get_or_create_concept(self, chunk: Chunk, extracted: ExtractedConcept) -> Concept:
        result = await self.db.execute(
            select(Concept).where(Concept.project_id == chunk.project_id, Concept.name == extracted.text)
        )
        concept = result.scalar_one_or_none()
        if concept:
            source_chunks = set(concept.metadata_.get("source_chunk_ids", []))
            source_chunks.add(str(chunk.id))
            concept.metadata_ = {**concept.metadata_, "source_chunk_ids": sorted(source_chunks)}
            return concept
        concept = Concept(
            project_id=chunk.project_id,
            name=extracted.text,
            aliases=[],
            metadata_={
                "concept_type": extracted.concept_type,
                "source_chunk_ids": [str(chunk.id)],
                "mentions": [{"chunk_id": str(chunk.id), "start_char": extracted.start_char, "end_char": extracted.end_char}],
                "confidence": extracted.confidence,
            },
        )
        self.db.add(concept)
        await self.db.flush()
        return concept

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
