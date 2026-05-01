import re
import uuid
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk, Document
from app.models.jobs import ChunkCluster, Cluster
from app.models.knowledge import Claim, Entity


class ClusteringService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_project_clusters(self, project_id: uuid.UUID) -> list[Cluster]:
        existing = await self.db.execute(select(Cluster.id).where(Cluster.project_id == project_id, Cluster.algorithm == "conservative_document_v1"))
        existing_ids = list(existing.scalars().all())
        if existing_ids:
            await self.db.execute(delete(ChunkCluster).where(ChunkCluster.cluster_id.in_(existing_ids)))
            await self.db.execute(delete(Cluster).where(Cluster.id.in_(existing_ids)))
            await self.db.flush()

        documents = list((await self.db.execute(select(Document).where(Document.project_id == project_id).order_by(Document.title))).scalars().all())
        entities = list((await self.db.execute(select(Entity).where(Entity.project_id == project_id))).scalars().all())
        entity_by_chunk = _entities_by_chunk(entities)
        clusters: list[Cluster] = []
        for document in documents:
            chunks = list(
                (
                    await self.db.execute(
                        select(Chunk).where(Chunk.document_id == document.id, Chunk.project_id == project_id).order_by(Chunk.chunk_index)
                    )
                )
                .scalars()
                .all()
            )
            if not chunks:
                continue
            chunk_ids = [chunk.id for chunk in chunks]
            top_entities = Counter(
                entity_name
                for chunk_id in chunk_ids
                for entity_name in entity_by_chunk.get(str(chunk_id), [])
            ).most_common(8)
            top_terms = _top_terms(" ".join(chunk.text for chunk in chunks), limit=8)
            label_terms = [name for name, _ in top_entities[:3]] or top_terms[:3] or [document.title]
            label = " / ".join(label_terms)
            claims = list(
                (
                    await self.db.execute(
                        select(Claim).where(Claim.project_id == project_id, Claim.chunk_id.in_(chunk_ids)).order_by(Claim.confidence.desc()).limit(10)
                    )
                )
                .scalars()
                .all()
            )
            cluster = Cluster(
                project_id=project_id,
                label=label[:240],
                description=f"Document-centered theme from {document.title}.",
                algorithm="conservative_document_v1",
                metadata_={
                    "document_ids": [str(document.id)],
                    "document_titles": [document.title],
                    "chunk_ids": [str(chunk_id) for chunk_id in chunk_ids],
                    "top_entities": [{"name": name, "count": count} for name, count in top_entities],
                    "top_terms": top_terms,
                    "source_chunks": [{"id": str(chunk.id), "citation": chunk.citation} for chunk in chunks[:10]],
                    "claims": [
                        {
                            "id": str(claim.id),
                            "text": f"{claim.subject} {claim.predicate} {claim.object}",
                            "chunk_id": str(claim.chunk_id),
                            "confidence": claim.confidence,
                        }
                        for claim in claims
                    ],
                },
            )
            self.db.add(cluster)
            await self.db.flush()
            self.db.add_all(ChunkCluster(chunk_id=chunk.id, cluster_id=cluster.id, confidence=1.0) for chunk in chunks)
            clusters.append(cluster)
        await self.db.flush()
        return clusters


def _entities_by_chunk(entities: list[Entity]) -> dict[str, list[str]]:
    by_chunk: dict[str, list[str]] = {}
    for entity in entities:
        for chunk_id in entity.metadata_.get("source_chunk_ids", []):
            by_chunk.setdefault(str(chunk_id), []).append(entity.canonical_name)
    return by_chunk


def _top_terms(text: str, limit: int) -> list[str]:
    stop_words = {"about", "after", "also", "because", "between", "from", "have", "into", "their", "there", "these", "this", "that", "with", "were", "which"}
    terms = [
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{4,}", text)
        if term.lower() not in stop_words
    ]
    return [term for term, _ in Counter(terms).most_common(limit)]
