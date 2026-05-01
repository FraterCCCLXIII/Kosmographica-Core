import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.jobs import ResearchNote
from app.models.workspace import Project

router = APIRouter(prefix="/research-notes", tags=["research-notes"])


class ResearchNoteCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1)
    body: str = Field(default="")
    query_text: str | None = None
    chunk_ids: list[uuid.UUID] = Field(default_factory=list)
    graph_node_ids: list[uuid.UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_research_note(request: ResearchNoteCreate, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    if not await db.get(Project, request.project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {request.project_id}")

    note = ResearchNote(
        project_id=request.project_id,
        title=request.title,
        body=request.body,
        query_text=request.query_text,
        chunk_ids=request.chunk_ids,
        graph_node_ids=request.graph_node_ids,
        metadata_=request.metadata,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return {"message": "Research note created.", "data": _serialize_note(note)}


@router.get("")
async def list_research_notes(project_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    if not await db.get(Project, project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    result = await db.execute(
        select(ResearchNote).where(ResearchNote.project_id == project_id).order_by(ResearchNote.created_at.desc())
    )
    return {
        "message": "Research notes listed.",
        "data": {"project_id": str(project_id), "items": [_serialize_note(note) for note in result.scalars()]},
    }


@router.delete("/{note_id}")
async def delete_research_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    note = await db.get(ResearchNote, note_id)
    if not note:
        raise HTTPException(status_code=404, detail=f"Research note not found: {note_id}")
    await db.execute(delete(ResearchNote).where(ResearchNote.id == note_id))
    await db.commit()
    return {"message": "Research note deleted.", "data": {"id": str(note_id)}}


def _serialize_note(note: ResearchNote) -> dict[str, object]:
    return {
        "id": str(note.id),
        "project_id": str(note.project_id),
        "title": note.title,
        "body": note.body,
        "query_text": note.query_text,
        "chunk_ids": [str(chunk_id) for chunk_id in note.chunk_ids],
        "graph_node_ids": [str(node_id) for node_id in note.graph_node_ids],
        "metadata": note.metadata_,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
