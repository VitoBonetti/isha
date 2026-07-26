"""Add snow_number and team_note to raw_assets

Revision ID: 5dd58e70a5a3
Revises: 1f40f0f7973c
Create Date: 2026-07-26 12:09:29.513213

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dd58e70a5a3'
down_revision: Union[str, Sequence[str], None] = '1f40f0f7973c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raw_assets', sa.Column('snow_number', sa.String(length=100), nullable=True))
    op.add_column('raw_assets', sa.Column('team_note', sa.Text(), nullable=True))
    op.create_unique_constraint('uq_raw_assets_snow_number', 'raw_assets', ['snow_number'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_raw_assets_snow_number', 'raw_assets', type_='unique')
    op.drop_column('raw_assets', 'team_note')
    op.drop_column('raw_assets', 'snow_number')
