"""add_fr24_fields_to_flight_cache

Revision ID: fr24_001
Revises: 5a1c9e7b2d44
Create Date: 2026-04-11

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fr24_001"
down_revision: Union[str, None] = "5a1c9e7b2d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add FR24-specific columns to flight_cache table
    op.add_column("flight_cache", sa.Column("fr24_id", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("squawk", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("vertical_rate", sa.Integer(), nullable=True))
    op.add_column("flight_cache", sa.Column("painted_as", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("operating_as", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("eta", sa.DateTime(timezone=True), nullable=True))
    op.add_column("flight_cache", sa.Column("origin_icao", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("origin_iata", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("destination_icao", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("destination_iata", sa.String(), nullable=True))
    op.add_column("flight_cache", sa.Column("flight_track", sa.JSON(), nullable=True))
    op.add_column("flight_cache", sa.Column("fr24_raw_message", sa.JSON(), nullable=True))
    op.add_column("flight_cache", sa.Column("data_sources", sa.JSON(), nullable=True))

    # Add index on fr24_id for faster lookups
    op.create_index("ix_flight_cache_fr24_id", "flight_cache", ["fr24_id"])


def downgrade() -> None:
    op.drop_index("ix_flight_cache_fr24_id", table_name="flight_cache")
    op.drop_column("flight_cache", "data_sources")
    op.drop_column("flight_cache", "fr24_raw_message")
    op.drop_column("flight_cache", "flight_track")
    op.drop_column("flight_cache", "destination_iata")
    op.drop_column("flight_cache", "destination_icao")
    op.drop_column("flight_cache", "origin_iata")
    op.drop_column("flight_cache", "origin_icao")
    op.drop_column("flight_cache", "eta")
    op.drop_column("flight_cache", "operating_as")
    op.drop_column("flight_cache", "painted_as")
    op.drop_column("flight_cache", "vertical_rate")
    op.drop_column("flight_cache", "squawk")
    op.drop_column("flight_cache", "fr24_id")
