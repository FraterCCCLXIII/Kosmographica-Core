import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.jobs import ChunkCluster, Cluster, ProcessingJob, ProcessingJobStatus
from app.models.workspace import Project
from app.services.clustering import ClusteringService

router = APIRouter(tags=["clusters"])


@router.get("/projects/{project_id}/clusters")
async def list_clusters(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    if not await db.get(Project, project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    result = await db.execute(select(Cluster).where(Cluster.project_id == project_id).order_by(Cluster.label))
    return {"message": "Clusters listed.", "data": {"project_id": str(project_id), "items": [_serialize_cluster(cluster) for cluster in result.scalars()]}}


@router.post("/projects/{project_id}/clusters/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_clusters(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    if not await db.get(Project, project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    job = ProcessingJob(
        project_id=project_id,
        document_id=None,
        job_type="cluster_generation",
        status=ProcessingJobStatus.running,
        metadata_={"algorithm": "conservative_document_v1"},
    )
    db.add(job)
    await db.flush()
    try:
        clusters = await ClusteringService(db).generate_project_clusters(project_id)
        job.status = ProcessingJobStatus.succeeded
        job.metadata_ = {**job.metadata_, "cluster_count": len(clusters)}
        job_data = _serialize_job(job)
        cluster_items = [_serialize_cluster(cluster) for cluster in clusters]
        await db.commit()
        return {"message": "Clusters generated.", "data": {"job": job_data, "items": cluster_items}}
    except Exception as exc:
        job.status = ProcessingJobStatus.failed
        job.error_message = str(exc)
        await db.commit()
        raise


@router.get("/clusters/{cluster_id}")
async def get_cluster(cluster_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    cluster = await db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail=f"Cluster not found: {cluster_id}")
    members = list((await db.execute(select(ChunkCluster).where(ChunkCluster.cluster_id == cluster.id))).all())
    return {
        "message": "Cluster detail.",
        "data": {
            **_serialize_cluster(cluster),
            "member_count": len(members),
        },
    }


def _serialize_cluster(cluster: Cluster) -> dict[str, object]:
    return {
        "id": str(cluster.id),
        "project_id": str(cluster.project_id),
        "label": cluster.label,
        "description": cluster.description,
        "algorithm": cluster.algorithm,
        "metadata": cluster.metadata_,
        "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
    }


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
