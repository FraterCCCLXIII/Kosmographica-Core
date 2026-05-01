from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk
from app.models.knowledge import Claim
from app.providers.base import LLMProvider
from app.services.entity_extraction import _parse_json_object


@dataclass(frozen=True)
class ExtractedClaim:
    subject: str
    predicate: str
    object: str
    confidence: float
    evidence_text: str
    low_confidence: bool


class ClaimExtractor:
    def __init__(self, db: AsyncSession, llm_provider: LLMProvider, low_confidence_threshold: float = 0.6) -> None:
        self.db = db
        self.llm_provider = llm_provider
        self.low_confidence_threshold = low_confidence_threshold

    async def extract(self, chunk: Chunk) -> list[ExtractedClaim]:
        response = await self.llm_provider.complete(self._build_prompt(chunk.text), system=self._system_prompt())
        payload = _parse_json_object(response)
        claims = payload.get("claims", [])
        return [claim for item in claims if (claim := self._coerce_claim(item, chunk.text))]

    async def extract_and_store(self, chunk: Chunk) -> list[Claim]:
        extracted_claims = await self.extract(chunk)
        stored_claims: list[Claim] = []
        for extracted in extracted_claims:
            claim = await self._get_or_create_claim(chunk, extracted)
            stored_claims.append(claim)
        await self.db.commit()
        return stored_claims

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You extract evidence-backed subject-predicate-object claims from source text. "
            "Never invent facts or citations. Return only valid JSON."
        )

    @staticmethod
    def _build_prompt(text: str) -> str:
        return f"""
Extract factual claims as subject-predicate-object triples from the chunk below.

Rules:
- Extract only claims directly supported by the text.
- Every claim must include evidence_text copied exactly from the chunk.
- Never invent unstated subjects, predicates, objects, or citations.
- Include confidence from 0.0 to 1.0.
- Return JSON only in this shape:
{{"claims":[{{"subject":"...", "predicate":"...", "object":"...", "evidence_text":"...", "confidence":0.95}}]}}

Chunk text:
{text}
""".strip()

    def _coerce_claim(self, item: dict[str, Any], chunk_text: str) -> ExtractedClaim | None:
        subject = str(item.get("subject", "")).strip()
        predicate = str(item.get("predicate", "")).strip()
        object_ = str(item.get("object", "")).strip()
        evidence_text = str(item.get("evidence_text", "")).strip()
        if not subject or not predicate or not object_ or not evidence_text or evidence_text not in chunk_text:
            return None
        confidence = min(1.0, max(0.0, float(item.get("confidence", 0.0))))
        return ExtractedClaim(
            subject=subject,
            predicate=predicate,
            object=object_,
            confidence=confidence,
            evidence_text=evidence_text,
            low_confidence=confidence < self.low_confidence_threshold,
        )

    async def _get_or_create_claim(self, chunk: Chunk, extracted: ExtractedClaim) -> Claim:
        result = await self.db.execute(
            select(Claim).where(
                Claim.project_id == chunk.project_id,
                Claim.chunk_id == chunk.id,
                Claim.subject == extracted.subject,
                Claim.predicate == extracted.predicate,
                Claim.object == extracted.object,
            )
        )
        claim = result.scalar_one_or_none()
        if claim:
            return claim
        claim = Claim(
            project_id=chunk.project_id,
            chunk_id=chunk.id,
            subject=extracted.subject,
            predicate=extracted.predicate,
            object=extracted.object,
            confidence=extracted.confidence,
            evidence_text=extracted.evidence_text,
            metadata_={"low_confidence": extracted.low_confidence},
        )
        self.db.add(claim)
        await self.db.flush()
        return claim
