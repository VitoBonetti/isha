"""add_table_asset_criteria

Revision ID: 1e24694bfdbb
Revises: c52d2cd8570c
Create Date: 2026-09-01 17:38:16.460457

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e24694bfdbb'
down_revision: Union[str, Sequence[str], None] = 'c52d2cd8570c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'asset_criteria',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('year', sa.Integer, unique=True, nullable=False),
        sa.Column('criticality_threshold', sa.Integer, nullable=False, server_default='8'),
        sa.Column('kpi_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('asset_criteria')
