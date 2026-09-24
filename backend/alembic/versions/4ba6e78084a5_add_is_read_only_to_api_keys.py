"""add is_read_only to api_keys

Revision ID: 4ba6e78084a5
Revises: 2712f0200430
Create Date: 2026-09-24 18:56:31.419191

"""
from typing import Sequence, Union
from sqlalchemy.engine.reflection import Inspector
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ba6e78084a5'
down_revision: Union[str, Sequence[str], None] = '2712f0200430'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely by checking if column exists first."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    existing_columns = [col['name'] for col in inspector.get_columns('api_keys')]

    if 'is_read_only' not in existing_columns:
        op.add_column('api_keys', sa.Column('is_read_only', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('api_keys')]

    if 'is_read_only' in existing_columns:
        op.drop_column('api_keys', 'is_read_only')
