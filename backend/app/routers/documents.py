import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status as http_status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.document import Chunk, Document, DocumentStatus
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Claim, Concept, Entity
from app.models.jobs import ProcessingJob, ProcessingJobStatus
from app.models.workspace import Project
from app.workers.ingestion import process_document, process_document_now

router = APIRouter(tags=["documents"])

SUPPORTED_SOURCE_TYPES = {
    "pdf",
    "docx",
    "html",
    "epub",
    "txt",
    "md",
    "text",
    "log",
    "csv",
    "tsv",
    "json",
    "xml",
    "rst",
}
EXTENSION_TO_SOURCE_TYPE = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".epub": "epub",
    ".html": "html",
    ".htm": "html",
    ".txt": "txt",
    ".text": "text",
    ".md": "md",
    ".markdown": "md",
    ".log": "log",
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".xml": "xml",
    ".rst": "rst",
}


@router.post("/documents/upload", status_code=http_status.HTTP_202_ACCEPTED)
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
async def list_documents(
    project_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    status: DocumentStatus | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    filters = [Document.project_id == project_id]
    if status:
        filters.append(Document.status == status)

    result = await db.execute(
        select(Document).where(*filters).order_by(Document.created_at.desc()).offset(offset).limit(limit)
    )
    total = (await db.execute(select(func.count()).select_from(Document).where(*filters))).scalar_one()
    return {
        "message": "Documents listed.",
        "data": {
            "project_id": str(project_id),
            "items": [_serialize_document(document) for document in result.scalars()],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
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


@router.get("/documents/{document_id}/chunks")
async def list_document_chunks(
    document_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id, Chunk.project_id == document.project_id)
        .order_by(Chunk.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    total = (await db.execute(select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id))).scalar_one()
    return {
        "message": "Document chunks listed.",
        "data": {
            "document_id": str(document_id),
            "items": [_serialize_chunk(chunk) for chunk in result.scalars()],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/documents/{document_id}/graph-summary")
async def get_document_graph_summary(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    chunk_ids_result = await db.execute(select(Chunk.id).where(Chunk.document_id == document_id, Chunk.project_id == document.project_id))
    chunk_ids = list(chunk_ids_result.scalars().all())
    node_type_rows = await db.execute(
        select(GraphNode.node_type, func.count())
        .where(GraphNode.project_id == document.project_id, GraphNode.ref_id.in_([document_id, *chunk_ids]))
        .group_by(GraphNode.node_type)
    )
    edge_type_rows = await db.execute(
        select(GraphEdge.edge_type, func.count())
        .where(GraphEdge.project_id == document.project_id, GraphEdge.evidence_chunk_id.in_(chunk_ids))
        .group_by(GraphEdge.edge_type)
    )
    entity_result = await db.execute(select(Entity).where(Entity.project_id == document.project_id).order_by(Entity.canonical_name))
    chunk_id_strings = {str(chunk_id) for chunk_id in chunk_ids}
    entities = [
        entity
        for entity in entity_result.scalars().all()
        if chunk_id_strings.intersection({str(value) for value in entity.metadata_.get("source_chunk_ids", [])})
    ][:25]
    concepts = await db.execute(select(Concept).where(Concept.project_id == document.project_id).order_by(Concept.name).limit(25))
    claims = await db.execute(select(Claim).where(Claim.project_id == document.project_id, Claim.chunk_id.in_(chunk_ids)).order_by(Claim.confidence.desc()).limit(25))
    return {
        "message": "Document graph summary.",
        "data": {
            "document_id": str(document_id),
            "node_counts": {node_type: count for node_type, count in node_type_rows.all()},
            "edge_counts": {edge_type: count for edge_type, count in edge_type_rows.all()},
            "top_entities": [_serialize_entity(entity) for entity in entities],
            "top_concepts": [_serialize_concept(concept) for concept in concepts.scalars()],
            "top_claims": [_serialize_claim(claim) for claim in claims.scalars()],
        },
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    chunk_ids = list(
        (
            await db.execute(
                select(Chunk.id).where(Chunk.document_id == document_id, Chunk.project_id == document.project_id)
            )
        ).scalars()
    )
    ref_ids = [document_id, *chunk_ids]
    if chunk_ids:
        await db.execute(
            delete(GraphEdge).where(
                GraphEdge.project_id == document.project_id,
                GraphEdge.evidence_chunk_id.in_(chunk_ids),
            )
        )
    await db.execute(
        delete(GraphNode).where(
            GraphNode.project_id == document.project_id,
            GraphNode.ref_id.in_(ref_ids),
        )
    )
    source_uri = document.source_uri
    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()
    _delete_uploaded_source(source_uri, settings.upload_dir)
    return {"message": "Document deleted.", "data": {"document_id": str(document_id)}}


def _source_type_for_filename(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return EXTENSION_TO_SOURCE_TYPE.get(suffix, "")


def _delete_uploaded_source(source_uri: str | None, upload_dir: str) -> None:
    if not source_uri:
        return

    try:
        source_path = Path(source_uri).resolve()
        upload_root = Path(upload_dir).resolve()
    except (OSError, RuntimeError):
        return

    if upload_root != source_path and upload_root not in source_path.parents:
        return
    if not source_path.exists():
        return
    try:
        if source_path.is_dir():
            shutil.rmtree(source_path)
            return

        source_path.unlink()
        parent = source_path.parent
        if parent != upload_root and upload_root in parent.parents:
            parent.rmdir()
    except OSError:
        pass


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


def _serialize_chunk(chunk: Chunk) -> dict[str, object]:
    return {
        "id": str(chunk.id),
        "project_id": str(chunk.project_id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "citation": chunk.citation,
        "metadata": chunk.metadata_,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
    }


def _serialize_entity(entity: Entity) -> dict[str, object]:
    return {
        "id": str(entity.id),
        "project_id": str(entity.project_id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "aliases": entity.aliases,
        "description": entity.description,
        "metadata": entity.metadata_,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }


def _serialize_concept(concept: Concept) -> dict[str, object]:
    return {
        "id": str(concept.id),
        "project_id": str(concept.project_id),
        "name": concept.name,
        "description": concept.description,
        "aliases": concept.aliases,
        "metadata": concept.metadata_,
        "created_at": concept.created_at.isoformat() if concept.created_at else None,
    }


def _serialize_claim(claim: Claim) -> dict[str, object]:
    return {
        "id": str(claim.id),
        "project_id": str(claim.project_id),
        "chunk_id": str(claim.chunk_id),
        "subject": claim.subject,
        "predicate": claim.predicate,
        "object": claim.object,
        "confidence": claim.confidence,
        "evidence_text": claim.evidence_text,
        "metadata": claim.metadata_,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
    }
