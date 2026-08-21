"""add_kiss24_fields_to_users_table

Revision ID: 155a181c840b
Revises: 1b3fdb5ccbfc
Create Date: 2026-08-21 15:50:46.462331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '155a181c840b'
down_revision: Union[str, Sequence[str], None] = '1b3fdb5ccbfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('kiss24_uuid', sa.String(), nullable=True))
    op.add_column('users', sa.Column('kiss24_api_key', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'kiss24_uuid')
    op.drop_column('users', 'kiss24_api_key')
