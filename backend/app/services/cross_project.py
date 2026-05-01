import hashlib
import importlib
import math
import uuid
from itertools import combinations
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk
from app.models.graph import CrossProjectLink
from app.models.knowledge import Entity
from app.models.workspace import Project
from app.providers.base import EmbeddingProvider

_global_models = importlib.import_module("app.models.global")
GlobalCanonicalEntity = _global_models.GlobalCanonicalEntity


class EntitySummary(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    canonical_name: str
    entity_type: str
    sample_chunks: list[dict[str, Any]] = Field(default_factory=list)


class LinkSuggestion(BaseModel):
    suggestion_id: str
    workspace_id: uuid.UUID
    source_project_id: uuid.UUID
    target_project_id: uuid.UUID
    source_entity: EntitySummary
    target_entity: EntitySummary
    link_type: str = "same_entity_candidate"
    confidence: float
    similarity_score: float


class CrossProjectService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: EmbeddingProvider,
        similarity_threshold: float = 0.85,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.similarity_threshold = similarity_threshold

    async def suggest_links(self, workspace_id: uuid.UUID) -> list[LinkSuggestion]:
        projects = await self._workspace_projects(workspace_id)
        rejected_ids = await self._rejected_suggestion_ids(workspace_id)
        suggestions: list[LinkSuggestion] = []

        for source_project, target_project in combinations(projects, 2):
            source_entities = await self._entities_by_name(source_project.id)
            target_entities = await self._entities_by_name(target_project.id)
            for name in sorted(set(source_entities).intersection(target_entities)):
                source_entity = source_entities[name]
                target_entity = target_entities[name]
                source_vector, target_vector = await self.embedding_provider.embed_batch(
                    [source_entity.canonical_name, target_entity.canonical_name]
                )
                similarity = _cosine_similarity(source_vector, target_vector)
                if similarity < self.similarity_threshold:
                    continue
                suggestion_id = _suggestion_id(workspace_id, source_entity.id, target_entity.id)
                if suggestion_id in rejected_ids:
                    continue
                if await self._confirmed_link_exists(workspace_id, source_entity.id, target_entity.id):
                    continue
                suggestions.append(
                    LinkSuggestion(
                        suggestion_id=suggestion_id,
                        workspace_id=workspace_id,
                        source_project_id=source_project.id,
                        target_project_id=target_project.id,
                        source_entity=await self._entity_summary(source_entity),
                        target_entity=await self._entity_summary(target_entity),
                        confidence=similarity,
                        similarity_score=similarity,
                    )
                )
        return suggestions

    async def confirm_link(self, suggestion: LinkSuggestion, rationale: str) -> CrossProjectLink:
        if not rationale.strip():
            raise ValueError("A rationale is required to confirm a cross-project link.")
        existing = await self._find_link_by_suggestion_id(suggestion.workspace_id, suggestion.suggestion_id)
        if existing and existing.link_type != "rejected_suggestion":
            return existing
        link = CrossProjectLink(
            workspace_id=suggestion.workspace_id,
            source_project_id=suggestion.source_project_id,
            target_project_id=suggestion.target_project_id,
            source_ref_type="entity",
            source_ref_id=suggestion.source_entity.id,
            target_ref_type="entity",
            target_ref_id=suggestion.target_entity.id,
            link_type=suggestion.link_type,
            confidence=suggestion.confidence,
            rationale=rationale,
            metadata_={
                "suggestion_id": suggestion.suggestion_id,
                "similarity_score": suggestion.similarity_score,
                "source_entity_name": suggestion.source_entity.canonical_name,
                "target_entity_name": suggestion.target_entity.canonical_name,
                "source_sample_chunks": suggestion.source_entity.sample_chunks,
                "target_sample_chunks": suggestion.target_entity.sample_chunks,
            },
        )
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def reject_link(self, suggestion_id: str) -> CrossProjectLink:
        result = await self.db.execute(
            select(CrossProjectLink).where(CrossProjectLink.metadata_["suggestion_id"].astext == suggestion_id)
        )
        existing_rejection = result.scalar_one_or_none()
        if existing_rejection:
            return existing_rejection
        suggestion = await self._suggestion_from_id(suggestion_id)
        link = CrossProjectLink(
            workspace_id=suggestion.workspace_id,
            source_project_id=suggestion.source_project_id,
            target_project_id=suggestion.target_project_id,
            source_ref_type="entity",
            source_ref_id=suggestion.source_entity.id,
            target_ref_type="entity",
            target_ref_id=suggestion.target_entity.id,
            link_type="rejected_suggestion",
            confidence=suggestion.confidence,
            rationale="Rejected by user.",
            metadata_={"suggestion_id": suggestion_id, "rejected": True},
        )
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def promote_to_canonical(self, entity_id: uuid.UUID, workspace_id: uuid.UUID) -> GlobalCanonicalEntity:
        entity = await self.db.get(Entity, entity_id)
        if not entity:
            raise ValueError(f"Entity not found: {entity_id}")
        project = await self.db.get(Project, entity.project_id)
        if not project or project.workspace_id != workspace_id:
            raise ValueError("Entity does not belong to the requested workspace.")

        result = await self.db.execute(
            select(GlobalCanonicalEntity).where(
                GlobalCanonicalEntity.workspace_id == workspace_id,
                GlobalCanonicalEntity.canonical_name == entity.canonical_name,
                GlobalCanonicalEntity.entity_type == entity.entity_type,
            )
        )
        canonical = result.scalar_one_or_none()
        if not canonical:
            canonical = GlobalCanonicalEntity(
                workspace_id=workspace_id,
                canonical_name=entity.canonical_name,
                entity_type=entity.entity_type,
                aliases=entity.aliases,
                description=entity.description,
                metadata_={"source_entity_id": str(entity.id), "source_project_id": str(entity.project_id)},
            )
            self.db.add(canonical)
            await self.db.flush()

        await self._link_entity_to_canonical(entity, canonical.id, workspace_id, "promote_to_canonical")

        peer_result = await self.db.execute(
            select(CrossProjectLink).where(
                CrossProjectLink.workspace_id == workspace_id,
                CrossProjectLink.link_type == "same_entity_candidate",
                ((CrossProjectLink.source_ref_id == entity.id) | (CrossProjectLink.target_ref_id == entity.id)),
            )
        )
        for link in peer_result.scalars().all():
            peer_entity_id = link.target_ref_id if link.source_ref_id == entity.id else link.source_ref_id
            peer_entity = await self.db.get(Entity, peer_entity_id)
            if peer_entity:
                await self._link_entity_to_canonical(peer_entity, canonical.id, workspace_id, "confirmed_cross_project_link")
        await self.db.commit()
        await self.db.refresh(canonical)
        return canonical

    async def confirmed_links(self, workspace_id: uuid.UUID) -> list[CrossProjectLink]:
        result = await self.db.execute(
            select(CrossProjectLink)
            .where(CrossProjectLink.workspace_id == workspace_id, CrossProjectLink.link_type != "rejected_suggestion")
            .order_by(CrossProjectLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def global_canonical_entities(self, workspace_id: uuid.UUID) -> list[GlobalCanonicalEntity]:
        result = await self.db.execute(
            select(GlobalCanonicalEntity)
            .where(GlobalCanonicalEntity.workspace_id == workspace_id)
            .order_by(GlobalCanonicalEntity.canonical_name)
        )
        return list(result.scalars().all())

    async def _link_entity_to_canonical(
        self,
        entity: Entity,
        canonical_id: uuid.UUID,
        workspace_id: uuid.UUID,
        source: str,
    ) -> None:
        link_result = await self.db.execute(
            select(CrossProjectLink).where(
                CrossProjectLink.workspace_id == workspace_id,
                CrossProjectLink.source_ref_id == entity.id,
                CrossProjectLink.target_ref_id == canonical_id,
                CrossProjectLink.link_type == "is_canonical_instance_of",
            )
        )
        if link_result.scalar_one_or_none():
            return
        self.db.add(
            CrossProjectLink(
                workspace_id=workspace_id,
                source_project_id=entity.project_id,
                target_project_id=entity.project_id,
                source_ref_type="entity",
                source_ref_id=entity.id,
                target_ref_type="global_canonical_entity",
                target_ref_id=canonical_id,
                link_type="is_canonical_instance_of",
                confidence=1.0,
                rationale="Explicit user promotion to global canonical entity.",
                metadata_={"source": source},
            )
        )

    async def _workspace_projects(self, workspace_id: uuid.UUID) -> list[Project]:
        result = await self.db.execute(select(Project).where(Project.workspace_id == workspace_id))
        return list(result.scalars().all())

    async def _entities_by_name(self, project_id: uuid.UUID) -> dict[str, Entity]:
        result = await self.db.execute(select(Entity).where(Entity.project_id == project_id))
        entities: dict[str, Entity] = {}
        for entity in result.scalars().all():
            entities.setdefault(entity.canonical_name.casefold(), entity)
        return entities

    async def _entity_summary(self, entity: Entity) -> EntitySummary:
        return EntitySummary(
            id=entity.id,
            project_id=entity.project_id,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type,
            sample_chunks=await self._sample_chunks(entity),
        )

    async def _sample_chunks(self, entity: Entity) -> list[dict[str, Any]]:
        sample_chunks: list[dict[str, Any]] = []
        for chunk_id_value in entity.metadata_.get("source_chunk_ids", [])[:3]:
            chunk = await self.db.get(Chunk, uuid.UUID(str(chunk_id_value)))
            if chunk:
                sample_chunks.append({"chunk_id": str(chunk.id), "citation": chunk.citation, "text": chunk.text[:500]})
        return sample_chunks

    async def _rejected_suggestion_ids(self, workspace_id: uuid.UUID) -> set[str]:
        result = await self.db.execute(
            select(CrossProjectLink).where(
                CrossProjectLink.workspace_id == workspace_id,
                CrossProjectLink.link_type == "rejected_suggestion",
            )
        )
        return {str(link.metadata_.get("suggestion_id")) for link in result.scalars().all() if link.metadata_.get("suggestion_id")}

    async def _confirmed_link_exists(self, workspace_id: uuid.UUID, source_entity_id: uuid.UUID, target_entity_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(CrossProjectLink.id).where(
                CrossProjectLink.workspace_id == workspace_id,
                CrossProjectLink.source_ref_id == source_entity_id,
                CrossProjectLink.target_ref_id == target_entity_id,
                CrossProjectLink.link_type != "rejected_suggestion",
            )
        )
        return result.scalar_one_or_none() is not None

    async def _find_link_by_suggestion_id(self, workspace_id: uuid.UUID, suggestion_id: str) -> CrossProjectLink | None:
        result = await self.db.execute(
            select(CrossProjectLink).where(
                CrossProjectLink.workspace_id == workspace_id,
                CrossProjectLink.metadata_["suggestion_id"].astext == suggestion_id,
            )
        )
        return result.scalar_one_or_none()

    async def _suggestion_from_id(self, suggestion_id: str) -> LinkSuggestion:
        for project in await self._workspace_projects_from_suggestion_id(suggestion_id):
            suggestions = await self.suggest_links(project.workspace_id)
            for suggestion in suggestions:
                if suggestion.suggestion_id == suggestion_id:
                    return suggestion
        raise ValueError(f"Suggestion not found: {suggestion_id}")

    async def _workspace_projects_from_suggestion_id(self, suggestion_id: str) -> list[Project]:
        result = await self.db.execute(select(Project))
        return list(result.scalars().all())


def _suggestion_id(workspace_id: uuid.UUID, source_entity_id: uuid.UUID, target_entity_id: uuid.UUID) -> str:
    key = f"{workspace_id}:{source_entity_id}:{target_entity_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
