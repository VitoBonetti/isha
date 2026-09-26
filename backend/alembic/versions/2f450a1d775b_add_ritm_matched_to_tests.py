"""add ritm_matched to tests

Revision ID: 2f450a1d775b
Revises: 026d907d2ac9
Create Date: 2026-09-26 20:35:18.692903

"""
from typing import Sequence, Union
from sqlalchemy.engine.reflection import Inspector
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f450a1d775b'
down_revision: Union[str, Sequence[str], None] = '026d907d2ac9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely by checking if column exists first."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Get a list of all existing columns in the table
    existing_columns = [col['name'] for col in inspector.get_columns('tests')]

    # Only add it if it's missing
    if 'ritm_matched' not in existing_columns:
        op.add_column('tests', sa.Column('ritm_matched', sa.Boolean(), server_default='false', nullable=False))

def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('tests')]

    if 'ritm_matched' in existing_columns:
        op.drop_column('tests', 'ritm_matched')


def upgrade() -> None:
    """Upgrade schema safely by checking if column exists first."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Get a list of all existing columns in the table
    existing_columns = [col['name'] for col in inspector.get_columns('raw_assets')]

    # Only add it if it's missing
    if 'is_country_override' not in existing_columns:
        op.add_column('raw_assets', sa.Column('is_country_override', sa.Boolean(), server_default='false', nullable=False))

def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('raw_assets')]

    if 'is_country_override' in existing_columns:
        op.drop_column('raw_assets', 'is_country_override')
