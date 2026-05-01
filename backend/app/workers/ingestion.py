import asyncio
import uuid
from pathlib import Path

import dramatiq
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.document import Chunk as ChunkModel
from app.models.document import Document, DocumentStatus
from app.models.jobs import ProcessingJob, ProcessingJobStatus
from app.models.workspace import Project
from app.providers.factory import get_embedding_provider
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.parsing import DocumentParser
from app.workers.broker import broker


@dramatiq.actor(broker=broker, queue_name="ingestion")
def process_document(document_id: str, job_id: str | None = None) -> None:
    asyncio.run(_process_document(uuid.UUID(document_id), uuid.UUID(job_id) if job_id else None))


async def process_document_now(document_id: uuid.UUID, job_id: uuid.UUID | None = None) -> None:
    await _process_document(document_id, job_id)


async def _process_document(document_id: uuid.UUID, job_id: uuid.UUID | None) -> None:
    async with AsyncSessionLocal() as db:
        job = await _get_job(db, document_id, job_id)
        document = await db.get(Document, document_id)
        if not document:
            await _fail_job(db, job, f"Document not found: {document_id}")
            return

        try:
            await _mark_running(db, document, job)
            await _run_step(db, job, "parse", _parse_document(db, document))
            await _run_step(db, job, "chunk", _chunk_document(db, document))
            await _run_step(db, job, "embed", _embed_document(db, document))
            document.status = DocumentStatus.ready
            if job:
                job.status = ProcessingJobStatus.succeeded
                job.error_message = None
            await db.commit()
            await _enqueue_graph_build(db, document)
        except Exception as exc:
            document.status = DocumentStatus.failed
            if job:
                job.status = ProcessingJobStatus.failed
                job.error_message = str(exc)
            await db.commit()
            raise


async def _get_job(db: AsyncSession, document_id: uuid.UUID, job_id: uuid.UUID | None) -> ProcessingJob | None:
    if job_id:
        return await db.get(ProcessingJob, job_id)
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _mark_running(db: AsyncSession, document: Document, job: ProcessingJob | None) -> None:
    document.status = DocumentStatus.processing
    if job:
        job.status = ProcessingJobStatus.running
        job.error_message = None
    await db.commit()


async def _run_step(db: AsyncSession, job: ProcessingJob | None, step_name: str, awaitable: object) -> None:
    if job:
        job.metadata_ = {**(job.metadata_ or {}), "current_step": step_name}
        await db.commit()
    try:
        await awaitable
    except Exception as exc:
        if job:
            job.status = ProcessingJobStatus.failed
            job.error_message = f"{step_name} failed: {exc}"
            job.metadata_ = {**(job.metadata_ or {}), "failed_step": step_name}
            await db.commit()
        raise


async def _parse_document(db: AsyncSession, document: Document) -> None:
    if document.raw_text:
        return
    if not document.source_uri:
        raise ValueError(f"Document has no source_uri: {document.id}")
    parsed = DocumentParser().parse(Path(document.source_uri), document.source_type)
    document.raw_text = parsed.raw_text
    document.title = parsed.title or document.title
    document.author = parsed.author or document.author
    document.date = parsed.date or document.date
    document.language = parsed.language or document.language
    document.metadata_ = {**(document.metadata_ or {}), "parsed": parsed.metadata}
    await db.commit()


async def _chunk_document(db: AsyncSession, document: Document) -> None:
    existing_chunks = await db.execute(select(ChunkModel.id).where(ChunkModel.document_id == document.id).limit(1))
    if existing_chunks.scalar_one_or_none():
        return
    if not document.raw_text:
        raise ValueError(f"Document has no raw_text: {document.id}")

    project = await db.get(Project, document.project_id)
    chunking_config = {}
    if project and project.extraction_config:
        chunking_config = project.extraction_config.get("chunking", {})

    service = ChunkingService()
    chunks = service.chunk(
        document.raw_text,
        chunking_config,
        project_id=document.project_id,
        document_id=document.id,
        citation_prefix=document.title,
    )
    if not chunks:
        raise ValueError(f"Document produced no chunks: {document.id}")

    await db.execute(delete(ChunkModel).where(ChunkModel.document_id == document.id))
    db.add_all(
        ChunkModel(
            project_id=chunk.project_id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            token_count=chunk.token_count,
            citation=chunk.citation,
            metadata_=chunk.metadata,
        )
        for chunk in chunks
    )
    await db.commit()


async def _embed_document(db: AsyncSession, document: Document) -> None:
    provider = get_embedding_provider()
    service = EmbeddingService(db)
    await service.embed_document(document.id, provider)


async def _enqueue_graph_build(db: AsyncSession, document: Document) -> None:
    from app.workers.graph import build_graph, build_graph_now

    settings = get_settings()

    result = await db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.document_id == document.id,
            ProcessingJob.job_type == "graph_construction",
            ProcessingJob.status.in_([ProcessingJobStatus.queued, ProcessingJobStatus.running, ProcessingJobStatus.succeeded]),
        )
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    existing_job = result.scalar_one_or_none()
    if existing_job:
        if settings.dramatiq_dev_mode:
            if existing_job.status != ProcessingJobStatus.succeeded:
                await build_graph_now(document.id, existing_job.id)
            return
        if existing_job.status != ProcessingJobStatus.succeeded:
            build_graph.send(str(document.id), str(existing_job.id))
        return

    graph_job = ProcessingJob(
        project_id=document.project_id,
        document_id=document.id,
        job_type="graph_construction",
        status=ProcessingJobStatus.queued,
        metadata_={"triggered_by": "document_ingestion"},
    )
    db.add(graph_job)
    await db.commit()
    if settings.dramatiq_dev_mode:
        await build_graph_now(document.id, graph_job.id)
        return
    build_graph.send(str(document.id), str(graph_job.id))


async def _fail_job(db: AsyncSession, job: ProcessingJob | None, error_message: str) -> None:
    if job:
        job.status = ProcessingJobStatus.failed
        job.error_message = error_message
        await db.commit()
