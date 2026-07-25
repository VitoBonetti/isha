"""add_raw_assets_snow_metadata_table

Revision ID: 1f40f0f7973c
Revises: 0e8aa0732fbb
Create Date: 2026-07-26 00:01:55.217961

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1f40f0f7973c'
down_revision: Union[str, Sequence[str], None] = '0e8aa0732fbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'raw_assets_snow_metadata',
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('last_snow_sync', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('snow_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['correlation_id'], ['raw_assets.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('raw_assets_snow_metadata')
