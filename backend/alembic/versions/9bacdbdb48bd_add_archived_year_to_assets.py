"""add archived_year to assets

Revision ID: 9bacdbdb48bd
Revises: 666c63edd19d
Create Date: 2026-08-15 22:25:54.572882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bacdbdb48bd'
down_revision: Union[str, Sequence[str], None] = '666c63edd19d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('assets', sa.Column('archived_year', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assets', 'archived_year')
