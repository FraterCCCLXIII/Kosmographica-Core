from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.jobs import ProcessingJob, ProcessingJobStatus
from app.workers.ingestion import process_document, process_document_now
from app.workers.graph import build_graph, build_graph_now

router = APIRouter(prefix="/processing", tags=["processing"])


@router.post("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_document_processing(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    job = ProcessingJob(
        project_id=document.project_id,
        document_id=document.id,
        job_type="document_ingestion",
        status=ProcessingJobStatus.queued,
        metadata_={"triggered_by": "manual"},
    )
    document.status = DocumentStatus.pending
    db.add(job)
    await db.commit()

    if settings.dramatiq_dev_mode:
        await process_document_now(document.id, job.id)
    else:
        process_document.send(str(document.id), str(job.id))

    return {
        "message": "Document processing queued.",
        "data": {"document_id": str(document.id), "job": _serialize_job(job)},
    }


@router.get("/jobs")
async def list_processing_jobs(
    project_id: UUID | None = Query(None),
    document_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    statement = select(ProcessingJob).order_by(ProcessingJob.created_at.desc())
    if project_id is not None:
        statement = statement.where(ProcessingJob.project_id == project_id)
    if document_id is not None:
        statement = statement.where(ProcessingJob.document_id == document_id)

    result = await db.execute(statement)
    return {"message": "Processing jobs listed.", "data": {"items": [_serialize_job(job) for job in result.scalars()]}}


@router.get("/documents/{document_id}/timeline")
async def get_document_processing_timeline(document_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at)
    )
    jobs = list(result.scalars().all())
    return {
        "message": "Document processing timeline.",
        "data": {
            "document_id": str(document.id),
            "document_status": document.status.value,
            "jobs": [_serialize_job(job) for job in jobs],
            "stages": _combine_stages(jobs),
        },
    }


@router.get("/jobs/{job_id}")
async def get_processing_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Processing job not found: {job_id}")
    return {"message": "Processing job status.", "data": _serialize_job(job)}


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_processing_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Processing job not found: {job_id}")
    if not job.document_id:
        raise HTTPException(status_code=400, detail="Only document processing jobs can be retried.")
    document = await db.get(Document, job.document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {job.document_id}")

    retry_job = ProcessingJob(
        project_id=job.project_id,
        document_id=job.document_id,
        job_type=job.job_type,
        status=ProcessingJobStatus.queued,
        metadata_={"triggered_by": "retry", "retry_of": str(job.id)},
    )
    job.status = ProcessingJobStatus.retrying
    document.status = DocumentStatus.pending
    db.add(retry_job)
    await db.commit()

    if retry_job.job_type == "graph_construction":
        if settings.dramatiq_dev_mode:
            await build_graph_now(document.id, retry_job.id)
        else:
            build_graph.send(str(document.id), str(retry_job.id))
    else:
        if settings.dramatiq_dev_mode:
            await process_document_now(document.id, retry_job.id)
        else:
            process_document.send(str(document.id), str(retry_job.id))

    return {"message": "Processing job retry queued.", "data": {"retry_job": _serialize_job(retry_job)}}


def _serialize_job(job: ProcessingJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "job_id": str(job.id),
        "project_id": str(job.project_id),
        "document_id": str(job.document_id) if job.document_id else None,
        "job_type": job.job_type,
        "status": job.status.value,
        "error_message": job.error_message,
        "metadata": job.metadata_,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _combine_stages(jobs: list[ProcessingJob]) -> list[dict[str, object]]:
    combined: dict[str, dict[str, object]] = {}
    for job in jobs:
        stages = (job.metadata_ or {}).get("stages") or {}
        for stage_name, stage in stages.items():
            combined[stage_name] = {"name": stage_name, "job_id": str(job.id), **stage}
        if not stages:
            fallback_names = ["parse", "chunk", "embed"] if job.job_type == "document_ingestion" else ["extract", "graph_build"]
            for stage_name in fallback_names:
                combined.setdefault(
                    stage_name,
                    {
                        "name": stage_name,
                        "job_id": str(job.id),
                        "status": job.status.value,
                        "started_at": job.created_at.isoformat() if job.created_at else None,
                        "completed_at": job.updated_at.isoformat() if job.updated_at and job.status in {ProcessingJobStatus.succeeded, ProcessingJobStatus.failed} else None,
                        "error": job.error_message,
                    },
                )
    return [combined[name] for name in ["upload", "parse", "chunk", "embed", "extract", "graph_build"] if name in combined]
