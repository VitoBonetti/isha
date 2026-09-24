"""add is_reconcilable to raw_assets

Revision ID: 2712f0200430
Revises: fe48c5dd75ef
Create Date: 2026-09-24 17:09:20.501969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '2712f0200430'
down_revision: Union[str, Sequence[str], None] = 'fe48c5dd75ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely by checking if column exists first."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Get a list of all existing columns in the table
    existing_columns = [col['name'] for col in inspector.get_columns('raw_assets')]

    # Only add it if it's missing
    if 'is_reconcilable' not in existing_columns:
        op.add_column('raw_assets', sa.Column('is_reconcilable', sa.Boolean(), server_default='true'))

def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('raw_assets')]

    if 'is_reconcilable' in existing_columns:
        op.drop_column('raw_assets', 'is_reconcilable')