"""add_kiss24_validating_vulns_table

Revision ID: 1b08a4a4a27e
Revises: 433e3bcb56f8
Create Date: 2026-08-24 11:02:15.143703

"""
from typing import Sequence, Union
from sqlalchemy.dialects.postgresql import UUID
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b08a4a4a27e'
down_revision: Union[str, Sequence[str], None] = '433e3bcb56f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'kiss24_validating_vulns',
        sa.Column('uuid', UUID(as_uuid=True), primary_key=True),
        sa.Column('validating_team', sa.String(50), nullable=False),
        sa.Column('need_credentials', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('need_vpn', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('other_issue', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('action_taken', sa.Text(), nullable=True),
        sa.Column('ai_suggestion', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_name', sa.String(100), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('kiss24_validating_vulns')
