import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.providers.factory import get_embedding_provider, get_llm_provider
from app.services.rag import RAGResponse, RAGService
from app.services.vector_search import SearchResult, VectorSearchService

router = APIRouter(prefix="/search", tags=["search"])


class VectorSearchRequest(BaseModel):
    query: str
    project_id: uuid.UUID
    k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    question: str
    project_id: uuid.UUID
    mode: str = "single"
    k: int = Field(default=10, ge=1, le=50)


class ComparativeQueryRequest(BaseModel):
    question: str
    project_ids: list[uuid.UUID]
    k: int = Field(default=10, ge=1, le=100)


@router.post("/vector")
async def vector_search(
    request: VectorSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    service = VectorSearchService(db, get_embedding_provider())
    return await service.search(request.query, request.project_id, request.k, request.filters)


@router.post("/query")
async def rag_query(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> RAGResponse:
    service = RAGService(db, get_embedding_provider(), get_llm_provider())
    return await service.query(request.question, request.project_id, request.mode, request.k)


@router.post("/comparative")
async def comparative_query(
    request: ComparativeQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> RAGResponse:
    service = RAGService(db, get_embedding_provider(), get_llm_provider())
    return await service.comparative_query(request.question, request.project_ids, request.k)
