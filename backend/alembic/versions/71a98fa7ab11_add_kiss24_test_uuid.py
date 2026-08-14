"""Add kiss24 test uuid

Revision ID: 71a98fa7ab11
Revises: ef57795bf611
Create Date: 2026-08-11 21:36:49.037511

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71a98fa7ab11'
down_revision: Union[str, Sequence[str], None] = 'ef57795bf611'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tests', sa.Column('kiss24', sa.UUID(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tests', 'kiss24')
