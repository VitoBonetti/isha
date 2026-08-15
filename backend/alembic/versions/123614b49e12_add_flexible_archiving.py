"""add flexible archiving

Revision ID: 123614b49e12
Revises: 9bacdbdb48bd
Create Date: 2026-08-15 22:53:47.453549

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '123614b49e12'
down_revision: Union[str, Sequence[str], None] = '9bacdbdb48bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('assets', 'archived_year')
    op.add_column('assets', sa.Column('is_archived', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('assets',
                  sa.Column('archived_years', postgresql.ARRAY(sa.Integer()), server_default='{}', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assets', 'archived_years')
    op.drop_column('assets', 'is_archived')
    op.add_column('assets', sa.Column('archived_year', sa.Integer(), nullable=True))
