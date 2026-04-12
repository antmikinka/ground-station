"""add_service_state_table

Revision ID: fr24_002
Revises: fr24_001
Create Date: 2026-04-11

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fr24_002"
down_revision: Union[str, None] = "fr24_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create service_state table for persisting service operational state
    op.create_table(
        "service_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("state_data", sa.JSON(), nullable=False, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create index on service_name for fast lookups
    op.create_index(
        op.f("ix_service_state_service_name"),
        "service_state",
        ["service_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_service_state_service_name"), table_name="service_state")
    op.drop_table("service_state")
