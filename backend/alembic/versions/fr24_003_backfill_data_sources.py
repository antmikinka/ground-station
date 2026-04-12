"""backfill_data_sources

Revision ID: fr24_003
Revises: fr24_002
Create Date: 2026-04-11

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fr24_003"
down_revision: Union[str, None] = "fr24_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill data_sources column to ['opensky'] for all existing rows where it is NULL.

    This migration ensures that existing flight_cache records have a proper
    data_sources value, indicating they originated from OpenSky data.
    """
    # Get connection and execute raw SQL for efficiency
    conn = op.get_bind()

    # Update all rows where data_sources is NULL to have ["opensky"]
    result = conn.execute(
        sa.text("""
            UPDATE flight_cache
            SET data_sources = '["opensky"]'
            WHERE data_sources IS NULL
        """)
    )

    # Log the number of rows updated
    rows_updated = result.rowcount
    print(f"Backfilled data_sources to ['opensky'] for {rows_updated} rows")


def downgrade() -> None:
    """Revert data_sources back to NULL for rows that only have ['opensky'].

    This downgrade reverses the backfill by setting data_sources back to NULL
    for rows that have exactly ['opensky'] as their data source.
    """
    conn = op.get_bind()

    # Set data_sources back to NULL for rows with only opensky
    result = conn.execute(
        sa.text("""
            UPDATE flight_cache
            SET data_sources = NULL
            WHERE data_sources = '["opensky"]'
        """)
    )

    # Log the number of rows reverted
    rows_reverted = result.rowcount
    print(f"Reverted data_sources to NULL for {rows_reverted} rows")
