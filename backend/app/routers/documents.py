import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.jobs import ProcessingJob, ProcessingJobStatus
from app.models.workspace import Project
from app.workers.ingestion import process_document, process_document_now

router = APIRouter(tags=["documents"])

SUPPORTED_SOURCE_TYPES = {"pdf", "docx", "html", "txt", "md"}
EXTENSION_TO_SOURCE_TYPE = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
    ".txt": "txt",
    ".md": "md",
}


@router.post("/documents/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    project_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    source_type = _source_type_for_filename(file.filename)
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    document_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir) / str(project_id) / str(document_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / (file.filename or f"document.{source_type}")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {file.filename}")
    file_path.write_bytes(content)

    document = Document(
        id=document_id,
        project_id=project_id,
        title=title or Path(file.filename or "untitled").stem,
        source_type=source_type,
        source_uri=str(file_path),
        metadata_={
            "original_filename": file.filename,
            "content_type": file.content_type,
            "file_size_bytes": len(content),
        },
        status=DocumentStatus.pending,
    )
    db.add(document)
    await db.flush()

    job = ProcessingJob(
        project_id=project_id,
        document_id=document.id,
        job_type="document_ingestion",
        status=ProcessingJobStatus.queued,
        metadata_={"source_type": source_type},
    )
    db.add(job)
    await db.commit()

    if settings.dramatiq_dev_mode:
        await process_document_now(document.id, job.id)
    else:
        process_document.send(str(document.id), str(job.id))
    return {
        "message": "Document accepted for ingestion.",
        "data": {"document_id": str(document.id), "job_id": str(job.id), "status": document.status.value},
    }


@router.get("/projects/{project_id}/documents")
async def list_documents(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    result = await db.execute(
        select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc())
    )
    return {
        "message": "Documents listed.",
        "data": {"project_id": str(project_id), "items": [_serialize_document(document) for document in result.scalars()]},
    }


@router.get("/documents/{document_id}")
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return {"message": "Document detail.", "data": _serialize_document(document, include_text=True)}


@router.get("/documents/{document_id}/status")
async def get_document_status(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    return {
        "message": "Document status.",
        "data": {
            "document_id": str(document.id),
            "document_status": document.status.value,
            "job": _serialize_job(job) if job else None,
        },
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()
    return {"message": "Document deleted.", "data": {"document_id": str(document_id)}}


def _source_type_for_filename(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return EXTENSION_TO_SOURCE_TYPE.get(suffix, "")


def _serialize_job(job: ProcessingJob) -> dict[str, object]:
    return {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "status": job.status.value,
        "error_message": job.error_message,
        "metadata": job.metadata_,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _serialize_document(document: Document, *, include_text: bool = False) -> dict[str, object]:
    data: dict[str, object] = {
        "id": str(document.id),
        "project_id": str(document.project_id),
        "title": document.title,
        "source_type": document.source_type,
        "source_uri": document.source_uri,
        "author": document.author,
        "date": document.date,
        "tradition": document.tradition,
        "region": document.region,
        "language": document.language,
        "metadata": document.metadata_,
        "status": document.status.value,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }
    if include_text:
        data["raw_text"] = document.raw_text
    return data
