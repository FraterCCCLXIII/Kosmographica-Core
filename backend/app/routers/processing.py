from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.jobs import ProcessingJob, ProcessingJobStatus
from app.workers.ingestion import process_document, process_document_now

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


@router.get("/jobs/{job_id}")
async def get_processing_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Processing job not found: {job_id}")
    return {"message": "Processing job status.", "data": _serialize_job(job)}


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
