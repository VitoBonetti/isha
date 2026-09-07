"""add_expires_at_to_api_keys

Revision ID: fe48c5dd75ef
Revises: 803131b792bf
Create Date: 2026-09-06 18:46:58.615862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe48c5dd75ef'
down_revision: Union[str, Sequence[str], None] = '803131b792bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('api_keys', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('api_keys', 'expires_at')
