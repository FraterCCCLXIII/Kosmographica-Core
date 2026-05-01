import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.providers.factory import get_embedding_provider
from app.services.cross_project import CrossProjectService, LinkSuggestion

router = APIRouter(prefix="/workspaces/{workspace_id}/cross-project", tags=["cross-project"])


class ConfirmLinkRequest(BaseModel):
    suggestion: LinkSuggestion
    rationale: str


class RejectLinkRequest(BaseModel):
    suggestion_id: str


class PromoteToCanonicalRequest(BaseModel):
    entity_id: uuid.UUID


def _serialize_link(link: Any) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "workspace_id": str(link.workspace_id),
        "source_project_id": str(link.source_project_id),
        "target_project_id": str(link.target_project_id),
        "source_ref_type": link.source_ref_type,
        "source_ref_id": str(link.source_ref_id),
        "target_ref_type": link.target_ref_type,
        "target_ref_id": str(link.target_ref_id),
        "link_type": link.link_type,
        "confidence": link.confidence,
        "rationale": link.rationale,
        "metadata": link.metadata_,
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


@router.get("/suggestions")
async def list_link_suggestions(workspace_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[LinkSuggestion]:
    return await CrossProjectService(db, get_embedding_provider()).suggest_links(workspace_id)


@router.get("/links")
async def list_confirmed_links(workspace_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    links = await CrossProjectService(db, get_embedding_provider()).confirmed_links(workspace_id)
    return [_serialize_link(link) for link in links]


@router.get("/canonical/entities")
async def list_global_canonical_entities(workspace_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    entities = await CrossProjectService(db, get_embedding_provider()).global_canonical_entities(workspace_id)
    return [
        {
            "id": str(entity.id),
            "workspace_id": str(entity.workspace_id),
            "canonical_name": entity.canonical_name,
            "entity_type": entity.entity_type,
            "aliases": entity.aliases,
            "description": entity.description,
            "metadata": entity.metadata_,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
        }
        for entity in entities
    ]


@router.post("/links/confirm")
async def confirm_link(
    workspace_id: uuid.UUID,
    request: ConfirmLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if request.suggestion.workspace_id != workspace_id:
        raise HTTPException(status_code=400, detail="Suggestion workspace does not match request workspace.")
    link = await CrossProjectService(db, get_embedding_provider()).confirm_link(request.suggestion, request.rationale)
    return _serialize_link(link)


@router.post("/links/reject")
async def reject_link(
    workspace_id: uuid.UUID,
    request: RejectLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    link = await CrossProjectService(db, get_embedding_provider()).reject_link(request.suggestion_id)
    if link.workspace_id != workspace_id:
        raise HTTPException(status_code=400, detail="Rejected suggestion belongs to a different workspace.")
    return _serialize_link(link)


@router.post("/canonical/promote")
async def promote_to_canonical(
    workspace_id: uuid.UUID,
    request: PromoteToCanonicalRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        canonical = await CrossProjectService(db, get_embedding_provider()).promote_to_canonical(request.entity_id, workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": str(canonical.id),
        "workspace_id": str(canonical.workspace_id),
        "canonical_name": canonical.canonical_name,
        "entity_type": canonical.entity_type,
        "aliases": canonical.aliases,
        "description": canonical.description,
        "metadata": canonical.metadata_,
        "created_at": canonical.created_at.isoformat() if canonical.created_at else None,
    }
