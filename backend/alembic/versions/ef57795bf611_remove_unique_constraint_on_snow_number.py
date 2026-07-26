"""Remove unique constraint on snow_number

Revision ID: ef57795bf611
Revises: 5dd58e70a5a3
Create Date: 2026-07-26 12:33:16.543526

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef57795bf611'
down_revision: Union[str, Sequence[str], None] = '5dd58e70a5a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('uq_raw_assets_snow_number', 'raw_assets', type_='unique')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_unique_constraint('uq_raw_assets_snow_number', 'raw_assets', ['snow_number'])
