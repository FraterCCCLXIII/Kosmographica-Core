from __future__ import annotations

import uuid

import pytest

from app.providers.base import LLMProvider
from app.providers.local_provider import LocalEmbeddingProvider, LocalLLMProvider
from app.services.rag import RAGService
from app.services.vector_search import SearchResult


class InvalidCitationLLMProvider(LLMProvider):
    async def complete(self, prompt: str, system: str | None = None) -> str:
        return "Unsupported claim [00000000-0000-0000-0000-000000000999]"

    async def stream(self, prompt: str, system: str | None = None):
        yield await self.complete(prompt, system)


@pytest.mark.asyncio
async def test_local_rag_returns_retrieved_text_with_all_citations_and_low_confidence() -> None:
    chunks = [_result("00000000-0000-0000-0000-000000000001", "Retrieved evidence only.")]
    service = RAGService(None, LocalEmbeddingProvider(), LocalLLMProvider())  # type: ignore[arg-type]

    response = await service._answer("What is supported?", chunks, [], "single")

    assert response.answer == (
        "Local evidence summary:\n"
        "The local provider cannot synthesize beyond retrieved text, so this answer summarizes the strongest retrieved evidence.\n"
        f"- Retrieved evidence only. [{chunks[0].chunk_id}]"
    )
    assert [citation.chunk_id for citation in response.citations] == [chunks[0].chunk_id]
    assert response.confidence == "low"


@pytest.mark.asyncio
async def test_rag_rejects_unknown_citations_from_real_provider_path() -> None:
    chunks = [_result("00000000-0000-0000-0000-000000000001", "Known evidence.")]
    service = RAGService(None, LocalEmbeddingProvider(), InvalidCitationLLMProvider())  # type: ignore[arg-type]

    response = await service._answer("What is supported?", chunks, [], "single")

    assert response.citations == []
    assert response.confidence == "insufficient_evidence"
    assert "could not be validated" in response.answer


def _result(chunk_id: str, text: str) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.UUID(chunk_id),
        document_id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
        project_id=uuid.UUID("00000000-0000-0000-0000-000000000201"),
        text=text,
        citation="test#chunk-0",
        similarity_score=0.9,
        metadata={},
    )
