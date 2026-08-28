"""add_kpi_critical_booleans_to_raw_asset

Revision ID: d74094767739
Revises: 4b73608a71fd
Create Date: 2026-08-27 13:36:18.560676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd74094767739'
down_revision: Union[str, Sequence[str], None] = '4b73608a71fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raw_assets', sa.Column('is_kpi', sa.Boolean(), nullable=True))
    op.add_column('raw_assets', sa.Column('is_critical', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raw_assets', 'is_kpi')
    op.drop_column('raw_assets', 'is_critical')
