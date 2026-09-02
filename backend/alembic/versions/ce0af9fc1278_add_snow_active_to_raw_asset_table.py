"""add_snow_active_to_raw_asset_table

Revision ID: ce0af9fc1278
Revises: 97c7942562d1
Create Date: 2026-09-02 17:28:03.936339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce0af9fc1278'
down_revision: Union[str, Sequence[str], None] = '97c7942562d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raw_assets', sa.Column('snow_active', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raw_assets', 'snow_active')
