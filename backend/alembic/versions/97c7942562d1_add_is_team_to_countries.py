"""add_is_team_to_countries

Revision ID: 97c7942562d1
Revises: 1e24694bfdbb
Create Date: 2026-09-01 17:52:31.885299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97c7942562d1'
down_revision: Union[str, Sequence[str], None] = '1e24694bfdbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('countries', sa.Column('is_team', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('countries', 'is_team')

