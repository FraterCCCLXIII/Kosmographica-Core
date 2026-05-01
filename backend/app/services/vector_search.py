import uuid
import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import EmbeddingProvider


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    text: str
    citation: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    project_id: uuid.UUID | None = None


class VectorSearchService:
    def __init__(self, db: AsyncSession, embedding_provider: EmbeddingProvider) -> None:
        self.db = db
        self.embedding_provider = embedding_provider

    async def search(
        self,
        query_text: str,
        project_id: uuid.UUID,
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        results = await self._search_projects(query_text, [project_id], k, filters)
        return [result for result in results if result.project_id == project_id]

    async def multi_project_search(
        self,
        query_text: str,
        project_ids: list[uuid.UUID],
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        if not project_ids:
            return []
        return await self._search_projects(query_text, project_ids, k, filters)

    async def _search_projects(
        self,
        query_text: str,
        project_ids: list[uuid.UUID],
        k: int,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        query_embedding = await self.embedding_provider.embed_text(query_text)
        requested_limit = max(1, k)
        candidate_limit = min(200, requested_limit * 4)
        params: dict[str, Any] = {
            "query_embedding": _format_vector(query_embedding),
            "project_ids": project_ids,
            "limit": candidate_limit,
        }
        where_clauses = ["c.project_id = ANY(:project_ids)"]
        filters = filters or {}

        if tradition := filters.get("tradition"):
            where_clauses.append("d.tradition = :tradition")
            params["tradition"] = tradition
        if region := filters.get("region"):
            where_clauses.append("d.region = :region")
            params["region"] = region
        if document_id := filters.get("document_id"):
            where_clauses.append("c.document_id = :document_id")
            params["document_id"] = uuid.UUID(str(document_id))
        if date_from := filters.get("date_from"):
            where_clauses.append("d.date >= :date_from")
            params["date_from"] = str(date_from)
        if date_to := filters.get("date_to"):
            where_clauses.append("d.date <= :date_to")
            params["date_to"] = str(date_to)

        sql = text(
            f"""
            SELECT
              c.id AS chunk_id,
              c.project_id AS project_id,
              c.document_id AS document_id,
              c.text AS text,
              c.citation AS citation,
              c.metadata AS chunk_metadata,
              d.title AS document_title,
              d.tradition AS tradition,
              d.region AS region,
              d.date AS date,
              1 - (ce.embedding <=> CAST(:query_embedding AS vector)) AS similarity_score
            FROM chunk c
            JOIN document d ON d.id = c.document_id
            JOIN chunk_embedding ce ON ce.chunk_id = c.id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY ce.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        )
        rows = (await self.db.execute(sql, params)).mappings().all()
        query_terms = _terms(query_text)
        results = [
            SearchResult(
                chunk_id=row["chunk_id"],
                project_id=row["project_id"],
                document_id=row["document_id"],
                text=row["text"],
                citation=row["citation"],
                similarity_score=_hybrid_score(float(row["similarity_score"]), query_terms, row["text"], row["document_title"]),
                metadata={
                    **(row["chunk_metadata"] or {}),
                    "vector_similarity_score": float(row["similarity_score"]),
                    "keyword_overlap_score": _keyword_overlap(query_terms, row["text"], row["document_title"]),
                    "document_title": row["document_title"],
                    "tradition": row["tradition"],
                    "region": row["region"],
                    "date": row["date"],
                    "source_project_id": str(row["project_id"]),
                },
            )
            for row in rows
        ]
        return sorted(results, key=lambda result: result.similarity_score, reverse=True)[:requested_limit]


def _format_vector(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def _terms(value: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", value)}


def _keyword_overlap(query_terms: set[str], text_value: str, title: str | None) -> float:
    if not query_terms:
        return 0.0
    haystack = _terms(f"{title or ''} {text_value}")
    if not haystack:
        return 0.0
    return len(query_terms.intersection(haystack)) / len(query_terms)


def _hybrid_score(vector_score: float, query_terms: set[str], text_value: str, title: str | None) -> float:
    keyword_score = _keyword_overlap(query_terms, text_value, title)
    return (vector_score * 0.75) + (keyword_score * 0.25)
