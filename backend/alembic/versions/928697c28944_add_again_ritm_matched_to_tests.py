"""add again ritm_matched to tests 

Revision ID: 928697c28944
Revises: 9c5451b534c4
Create Date: 2026-09-27 00:24:16.412874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '928697c28944'
down_revision: Union[str, Sequence[str], None] = '9c5451b534c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tests', sa.Column('ritm_matched', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tests', 'ritm_matched')
