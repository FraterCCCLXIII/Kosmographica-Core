"""graph query indexes

Revision ID: 9f2c1a7b4d30
Revises: 2329b33557bf
Create Date: 2026-05-01 11:15:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "9f2c1a7b4d30"
down_revision: Union[str, None] = "2329b33557bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_graph_edge_project_edge_type_weight", "graph_edge", ["project_id", "edge_type", "weight"], unique=False)
    op.create_index("ix_graph_node_project_node_type", "graph_node", ["project_id", "node_type"], unique=False)
    op.create_index("ix_graph_edge_project_evidence_chunk", "graph_edge", ["project_id", "evidence_chunk_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_graph_edge_project_evidence_chunk", table_name="graph_edge")
    op.drop_index("ix_graph_node_project_node_type", table_name="graph_node")
    op.drop_index("ix_graph_edge_project_edge_type_weight", table_name="graph_edge")
