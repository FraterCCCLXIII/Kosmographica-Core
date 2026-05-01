import io
import json
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.export import ExportService

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{project_id}/json")
async def export_json(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        data = await ExportService(db).export_json(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=json.dumps(data, default=str, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}.json"'},
    )


@router.get("/{project_id}/graphml")
async def export_graphml(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        graphml = await ExportService(db).export_graphml(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=graphml,
        media_type="application/graphml+xml",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}.graphml"'},
    )


@router.get("/{project_id}/csv")
async def export_csv(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        files = await ExportService(db).export_csv(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}-csv.zip"'},
    )


@router.get("/{project_id}/markdown")
async def export_markdown(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        markdown = await ExportService(db).export_markdown(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}.md"'},
    )
