import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document import Chunk
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
        if get_settings().extraction_provider == "local":
            return self._extract_local(chunk.text)
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

        for extracted in extracted_entities:
            entity = await self._get_or_create_entity(chunk, extracted)
            stored_entities.append(entity)

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

    def _extract_local(self, chunk_text: str) -> list[ExtractedEntity]:
        known_entities = {
            "demiurge": "figure",
            "sophia": "figure",
            "jesus": "person",
            "christ": "figure",
            "buddha": "person",
            "mary": "person",
            "gnostic": "tradition",
        }
        candidates: dict[str, str] = {}
        for match in re.finditer(r"\b[A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,})*\b", chunk_text):
            candidates.setdefault(match.group(0), "entity")
        lower_text = chunk_text.lower()
        for name, entity_type in known_entities.items():
            if re.search(rf"\b{re.escape(name)}\b", lower_text):
                candidates.setdefault(name, entity_type)

        entities: list[ExtractedEntity] = []
        for text, entity_type in candidates.items():
            match = re.search(rf"\b{re.escape(text)}\b", chunk_text, flags=re.IGNORECASE)
            if not match:
                continue
            entities.append(
                ExtractedEntity(
                    text=chunk_text[match.start() : match.end()],
                    entity_type=entity_type,
                    start_char=match.start(),
                    end_char=match.end(),
                    confidence=0.7,
                )
            )
        return entities

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
            mentions = list(entity.metadata_.get("mentions", []))
            mention = {"chunk_id": str(chunk.id), "start_char": extracted.start_char, "end_char": extracted.end_char}
            if mention not in mentions:
                mentions.append(mention)
            confidence = max(float(entity.metadata_.get("confidence", 0.0)), extracted.confidence)
            entity.metadata_ = {**entity.metadata_, "source_chunk_ids": sorted(source_chunks), "mentions": mentions, "confidence": confidence}
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
