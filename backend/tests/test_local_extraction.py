from __future__ import annotations

import inspect
import uuid

import pytest

from app.config import get_settings
from app.models.document import Chunk
from app.providers.base import LLMProvider
from app.services.claim_extraction import ClaimExtractor
from app.services.concept_extraction import ConceptExtractor
from app.services.entity_extraction import EntityExtractor


class NeverCalledLLMProvider(LLMProvider):
    async def complete(self, prompt: str, system: str | None = None) -> str:
        raise AssertionError("local extraction must not call the LLM provider")

    async def stream(self, prompt: str, system: str | None = None):
        raise AssertionError("local extraction must not call the LLM provider")


@pytest.fixture(autouse=True)
def local_extraction_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://example@example/example")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dev")
    monkeypatch.setenv("OPENAI_API_KEY", "dev")
    monkeypatch.setenv("EXTRACTION_PROVIDER", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_local_extractors_return_domain_candidates_without_llm() -> None:
    chunk = Chunk(
        project_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        document_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        chunk_index=0,
        text="The gnostic text describes a demiurge and layered cosmology. Sophia teaches wisdom and emanation.",
        token_count=15,
        citation="smoke#chunk-0",
        metadata_={},
    )
    llm = NeverCalledLLMProvider()

    entities = await EntityExtractor(None, llm).extract(chunk)  # type: ignore[arg-type]
    concepts = await ConceptExtractor(None, llm).extract(chunk)  # type: ignore[arg-type]
    claims = await ClaimExtractor(None, llm).extract(chunk)  # type: ignore[arg-type]

    assert {entity.text.lower() for entity in entities} >= {"demiurge", "sophia"}
    assert {concept.text.lower() for concept in concepts} >= {"cosmology", "wisdom", "emanation"}
    assert claims
    assert claims[0].evidence_text in chunk.text


def test_extractors_do_not_import_graph_tables() -> None:
    import app.services.concept_extraction as concept_extraction
    import app.services.entity_extraction as entity_extraction

    entity_source = inspect.getsource(entity_extraction)
    concept_source = inspect.getsource(concept_extraction)

    assert "GraphNode" not in entity_source
    assert "GraphEdge" not in entity_source
    assert "GraphNode" not in concept_source
    assert "GraphEdge" not in concept_source
