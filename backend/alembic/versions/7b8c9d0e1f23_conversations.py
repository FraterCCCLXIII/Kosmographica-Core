"""conversations

Revision ID: 7b8c9d0e1f23
Revises: 5d4e8c2b1a90
Create Date: 2026-05-01 18:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7b8c9d0e1f23"
down_revision: Union[str, None] = "5d4e8c2b1a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id", "workspace_id"], ["project.id", "project.workspace_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversation_project_id"), "conversation", ["project_id"], unique=False)
    op.create_index(op.f("ix_conversation_workspace_id"), "conversation", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_conversation_mode"), "conversation", ["mode"], unique=False)
    op.create_index(op.f("ix_conversation_status"), "conversation", ["status"], unique=False)
    op.create_index("ix_conversation_workspace_updated", "conversation", ["workspace_id", "updated_at"], unique=False)
    op.create_index("ix_conversation_workspace_project_updated", "conversation", ["workspace_id", "project_id", "updated_at"], unique=False)

    op.create_table(
        "conversation_message",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_chunks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_conversation_message_role"),
        sa.CheckConstraint("status IN ('queued', 'generating', 'complete', 'failed')", name="ck_conversation_message_status"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversation_message_conversation_id"), "conversation_message", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_conversation_message_role"), "conversation_message", ["role"], unique=False)
    op.create_index(op.f("ix_conversation_message_status"), "conversation_message", ["status"], unique=False)
    op.create_index("ix_conversation_message_conversation_created", "conversation_message", ["conversation_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_conversation_message_conversation_created", table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_status"), table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_role"), table_name="conversation_message")
    op.drop_index(op.f("ix_conversation_message_conversation_id"), table_name="conversation_message")
    op.drop_table("conversation_message")

    op.drop_index("ix_conversation_workspace_project_updated", table_name="conversation")
    op.drop_index("ix_conversation_workspace_updated", table_name="conversation")
    op.drop_index(op.f("ix_conversation_status"), table_name="conversation")
    op.drop_index(op.f("ix_conversation_mode"), table_name="conversation")
    op.drop_index(op.f("ix_conversation_workspace_id"), table_name="conversation")
    op.drop_index(op.f("ix_conversation_project_id"), table_name="conversation")
    op.drop_table("conversation")
