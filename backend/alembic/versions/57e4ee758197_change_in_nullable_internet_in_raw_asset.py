"""change_in_nullable_internet_in_raw_asset

Revision ID: 57e4ee758197
Revises: ce0af9fc1278
Create Date: 2026-09-04 08:07:56.026617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57e4ee758197'
down_revision: Union[str, Sequence[str], None] = 'ce0af9fc1278'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('raw_assets', 'facing_internet', existing_type=sa.BOOLEAN(), server_default=None, nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('raw_assets', 'facing_internet', existing_type=sa.BOOLEAN(), server_default='false', nullable=True)
