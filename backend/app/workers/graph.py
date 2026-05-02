import asyncio
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime

import dramatiq
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.document import Chunk, Document, DocumentStatus
from app.models.jobs import ProcessingJob, ProcessingJobStatus
from app.providers.factory import get_llm_provider
from app.services.claim_extraction import ClaimExtractor
from app.services.concept_extraction import ConceptExtractor
from app.services.entity_extraction import EntityExtractor
from app.services.graph_builder import GraphBuilder
from app.workers.broker import broker


@dramatiq.actor(broker=broker, queue_name="build_graph")
def build_graph(document_id: str, job_id: str | None = None) -> None:
    asyncio.run(_build_graph(uuid.UUID(document_id), uuid.UUID(job_id) if job_id else None))


async def build_graph_now(document_id: uuid.UUID, job_id: uuid.UUID | None = None) -> None:
    await _build_graph(document_id, job_id)


async def _build_graph(document_id: uuid.UUID, job_id: uuid.UUID | None) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        job = await _get_job(db, document_id, job_id)
        if not document:
            await _fail_job(db, job, f"Document not found: {document_id}")
            return

        try:
            if job:
                job.status = ProcessingJobStatus.running
                job.error_message = None
                job.metadata_ = _with_stage({**(job.metadata_ or {}), "current_step": "extract"}, "extract", "running")
            await db.commit()

            llm_provider = get_llm_provider()
            chunk_result = await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document.id)
                .order_by(Chunk.chunk_index)
            )
            chunks = list(chunk_result.scalars().all())
            if not chunks:
                raise ValueError(f"Document has no chunks for graph construction: {document.id}")

            entity_extractor = EntityExtractor(db, llm_provider)
            concept_extractor = ConceptExtractor(db, llm_provider)
            claim_extractor = ClaimExtractor(db, llm_provider)
            for chunk in chunks:
                await _run_step(db, job, "extract_entities", entity_extractor.extract_and_store(chunk))
                await _run_step(db, job, "extract_concepts", concept_extractor.extract_and_store(chunk))
                await _run_step(db, job, "extract_claims", claim_extractor.extract_and_store(chunk))

            builder = GraphBuilder(db)
            await _run_step(db, job, "build_document_nodes", builder.build_document_nodes(document.id))
            await _run_step(db, job, "build_chunk_nodes", builder.build_chunk_nodes(document.id))
            await _run_step(db, job, "build_entity_nodes", builder.build_entity_nodes(document.project_id))
            await _run_step(db, job, "build_concept_nodes", builder.build_concept_nodes(document.project_id))
            await _run_step(db, job, "build_claim_nodes", builder.build_claim_nodes(document.id))
            await _run_step(db, job, "build_semantic_edges", builder.build_semantic_edges(document.project_id))
            await _run_step(db, job, "build_cooccurrence_edges", builder.build_cooccurrence_edges(document.project_id))

            document.status = DocumentStatus.graph_ready
            if job:
                job.status = ProcessingJobStatus.succeeded
                job.error_message = None
                metadata = _with_stage({**(job.metadata_ or {}), "current_step": "complete"}, "extract", "succeeded")
                job.metadata_ = _with_stage(metadata, "graph_build", "succeeded")
            await db.commit()
        except Exception as exc:
            await db.rollback()
            document.status = DocumentStatus.failed
            if job:
                job.status = ProcessingJobStatus.failed
                job.error_message = str(exc)
            await db.commit()
            raise


async def _get_job(db, document_id: uuid.UUID, job_id: uuid.UUID | None) -> ProcessingJob | None:
    if job_id:
        return await db.get(ProcessingJob, job_id)
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id, ProcessingJob.job_type == "graph_construction")
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _run_step(db, job: ProcessingJob | None, step_name: str, awaitable: Awaitable[object]) -> object:
    stage_name = "extract" if step_name.startswith("extract_") else "graph_build"
    if job:
        job.metadata_ = _with_stage({**(job.metadata_ or {}), "current_step": step_name}, stage_name, "running")
        await db.commit()
    try:
        return await awaitable
    except Exception as exc:
        await db.rollback()
        if job:
            job.status = ProcessingJobStatus.failed
            job.error_message = f"{step_name} failed: {exc}"
            job.metadata_ = _with_stage({**(job.metadata_ or {}), "failed_step": step_name}, stage_name, "failed", str(exc))
            await db.commit()
        raise


async def _fail_job(db, job: ProcessingJob | None, error_message: str) -> None:
    if job:
        job.status = ProcessingJobStatus.failed
        job.error_message = error_message
        job.metadata_ = _with_stage({**(job.metadata_ or {})}, "load_document", "failed", error_message)
        await db.commit()


def _with_stage(metadata: dict, stage_name: str, status: str, error: str | None = None) -> dict:
    now = datetime.now(UTC).isoformat()
    stages = dict(metadata.get("stages") or {})
    current = dict(stages.get(stage_name) or {})
    if status == "running":
        current.setdefault("started_at", now)
    if status in {"succeeded", "failed"}:
        current.setdefault("started_at", now)
        current["completed_at"] = now
    current["status"] = status
    if error:
        current["error"] = error
    stages[stage_name] = current
    return {**metadata, "stages": stages}
