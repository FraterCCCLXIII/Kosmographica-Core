import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GraphNode(Base):
    __tablename__ = "graph_node"
    __table_args__ = (UniqueConstraint("id", "project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GraphEdge(Base):
    __tablename__ = "graph_edge"
    __table_args__ = (
        ForeignKeyConstraint(["source_node_id", "project_id"], ["graph_node.id", "graph_node.project_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["target_node_id", "project_id"], ["graph_node.id", "graph_node.project_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["evidence_chunk_id", "project_id"], ["chunk.id", "chunk.project_id"], ondelete="RESTRICT"),
        CheckConstraint("source_node_id <> target_node_id"),
        CheckConstraint("weight >= 0"),
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    confidence: Mapped[float] = mapped_column(nullable=False)
    evidence_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrossProjectLink(Base):
    __tablename__ = "cross_project_link"
    __table_args__ = (
        ForeignKeyConstraint(["source_project_id", "workspace_id"], ["project.id", "project.workspace_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["target_project_id", "workspace_id"], ["project.id", "project.workspace_id"], ondelete="CASCADE"),
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True)
    source_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_ref_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_ref_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    link_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
