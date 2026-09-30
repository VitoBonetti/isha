"""rename_snitcher_table

Revision ID: 542537b248f5
Revises: 1bed60d12a12
Create Date: 2026-09-27 21:42:34.361848

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '542537b248f5'
down_revision: Union[str, Sequence[str], None] = '1bed60d12a12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('snitcher_', 'snitcher')


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table('snitcher', 'snitcher_')
