"""long term query indexes

Revision ID: 5d4e8c2b1a90
Revises: 9f2c1a7b4d30
Create Date: 2026-05-01 12:45:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "5d4e8c2b1a90"
down_revision: Union[str, None] = "9f2c1a7b4d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index("ix_graph_node_label_trgm", "graph_node", ["label"], unique=False, postgresql_using="gin", postgresql_ops={"label": "gin_trgm_ops"})
    op.create_index("ix_graph_edge_project_source", "graph_edge", ["project_id", "source_node_id"], unique=False)
    op.create_index("ix_graph_edge_project_target", "graph_edge", ["project_id", "target_node_id"], unique=False)
    op.create_index("ix_chunk_project_document_index", "chunk", ["project_id", "document_id", "chunk_index"], unique=False)
    op.create_index("ix_document_project_status_created", "document", ["project_id", "status", "created_at"], unique=False)
    op.create_index("ix_entity_project_name_type", "entity", ["project_id", "canonical_name", "entity_type"], unique=False)
    op.create_index("ix_claim_project_chunk_confidence", "claim", ["project_id", "chunk_id", "confidence"], unique=False)
    op.create_index("ix_cluster_project_algorithm_label", "cluster", ["project_id", "algorithm", "label"], unique=False)
    op.create_index("ix_processing_job_project_status_updated", "processing_job", ["project_id", "status", "updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_processing_job_project_status_updated", table_name="processing_job")
    op.drop_index("ix_cluster_project_algorithm_label", table_name="cluster")
    op.drop_index("ix_claim_project_chunk_confidence", table_name="claim")
    op.drop_index("ix_entity_project_name_type", table_name="entity")
    op.drop_index("ix_document_project_status_created", table_name="document")
    op.drop_index("ix_chunk_project_document_index", table_name="chunk")
    op.drop_index("ix_graph_edge_project_target", table_name="graph_edge")
    op.drop_index("ix_graph_edge_project_source", table_name="graph_edge")
    op.drop_index("ix_graph_node_label_trgm", table_name="graph_node")
