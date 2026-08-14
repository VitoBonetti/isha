"""Add is_tentative to tests

Revision ID: 0e8aa0732fbb
Revises: d3417f5c2c3a
Create Date: 2026-07-24 22:56:23.859938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e8aa0732fbb'
down_revision: Union[str, Sequence[str], None] = 'd3417f5c2c3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tests', sa.Column('is_tentative', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tests', 'is_tentative')
