"""backfill sampling interval and protocol

Revision ID: 06cd1a59abd2
Revises: d27c39c2a76b
Create Date: 2026-10-06 17:49:55.499041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06cd1a59abd2'
down_revision: Union[str, Sequence[str], None] = 'd27c39c2a76b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Promote sampling_interval_seconds from default_config JSON to the column.
    op.execute(
        """
        UPDATE devices
        SET sampling_interval_seconds = round((default_config->>'sampling_interval_seconds')::numeric)::int
        WHERE jsonb_typeof(default_config->'sampling_interval_seconds') = 'number'
          AND (default_config->>'sampling_interval_seconds')::numeric >= 5
        """
    )

    # Normalise protocol values to the Phase 5 selector keys.
    op.execute(
        """
        UPDATE devices
        SET default_config = jsonb_set(default_config, '{protocol}', '"simulation"')
        WHERE device_family = 'simulation'
        """
    )
    op.execute(
        """
        UPDATE devices
        SET default_config = jsonb_set(default_config, '{protocol}', '"mqtt"')
        WHERE device_family = 'edge'
        """
    )


def downgrade() -> None:
    # Data-only revision: nothing structural to undo, and the old values are not used by any code.
    pass