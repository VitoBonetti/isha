"""add_kiss24_org_uuid_field_to_country

Revision ID: 6f4564eab385
Revises: 4e244895c8bc
Create Date: 2026-08-19 22:47:40.236272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f4564eab385'
down_revision: Union[str, Sequence[str], None] = '4e244895c8bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('countries', sa.Column('kiss24_uuid', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('countries', 'kiss24_uuid')
