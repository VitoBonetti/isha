"""add_kiss24_asset_uuid_field_to_rawasset

Revision ID: 4e244895c8bc
Revises: c4446968844e
Create Date: 2026-08-19 20:33:13.670197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e244895c8bc'
down_revision: Union[str, Sequence[str], None] = 'c4446968844e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raw_assets', sa.Column('kiss24_asset_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raw_assets', 'kiss24_asset_id')
