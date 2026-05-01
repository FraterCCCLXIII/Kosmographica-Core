from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.workspace import Project, Workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    domain: str | None = None
    ontology_config: dict[str, object] = Field(default_factory=dict)
    embedding_config: dict[str, object] = Field(default_factory=dict)
    extraction_config: dict[str, object] = Field(default_factory=dict)
    graph_config: dict[str, object] = Field(default_factory=dict)


def _workspace_data(workspace: Workspace) -> dict[str, object]:
    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "description": workspace.description,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
    }


def _project_data(project: Project) -> dict[str, object]:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "name": project.name,
        "description": project.description,
        "domain": project.domain,
        "ontology_config": project.ontology_config,
        "embedding_config": project.embedding_config,
        "extraction_config": project.extraction_config,
        "graph_config": project.graph_config,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.post("")
async def create_workspace(request: WorkspaceCreate, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    workspace = Workspace(name=request.name, description=request.description)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return {"message": "Workspace created.", "data": _workspace_data(workspace)}


@router.get("")
async def list_workspaces(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result = await db.execute(select(Workspace).order_by(Workspace.created_at.desc()))
    return {"message": "Workspace listing.", "data": {"items": [_workspace_data(item) for item in result.scalars().all()]}}


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
    return {"message": "Workspace detail.", "data": _workspace_data(workspace)}


@router.put("/{workspace_id}")
async def update_workspace(workspace_id: UUID, request: WorkspaceUpdate, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
    if request.name is not None:
        workspace.name = request.name
    if request.description is not None:
        workspace.description = request.description
    await db.commit()
    await db.refresh(workspace)
    return {"message": "Workspace updated.", "data": _workspace_data(workspace)}


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
    await db.delete(workspace)
    await db.commit()
    return {"message": "Workspace deleted.", "data": {"workspace_id": str(workspace_id)}}


@router.post("/{workspace_id}/projects")
async def create_project(workspace_id: UUID, request: ProjectCreate, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
    project = Project(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        domain=request.domain,
        ontology_config=request.ontology_config,
        embedding_config=request.embedding_config,
        extraction_config=request.extraction_config,
        graph_config=request.graph_config,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"message": "Project created.", "data": _project_data(project)}


@router.get("/{workspace_id}/projects")
async def list_projects(workspace_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result = await db.execute(select(Project).where(Project.workspace_id == workspace_id).order_by(Project.created_at.desc()))
    return {
        "message": "Project listing.",
        "data": {"workspace_id": str(workspace_id), "items": [_project_data(item) for item in result.scalars().all()]},
    }
