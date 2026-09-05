"""add is evaluated to asset_criteria table

Revision ID: 9a6a4681e75a
Revises: 76f10d71b9c7
Create Date: 2026-09-05 12:25:29.728515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a6a4681e75a'
down_revision: Union[str, Sequence[str], None] = '76f10d71b9c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_criteria', sa.Column('is_evaluated', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_criteria', 'is_evaluated')

