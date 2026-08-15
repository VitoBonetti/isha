"""add_service_placeholders

Revision ID: 666c63edd19d
Revises: 71a98fa7ab11
Create Date: 2026-08-15 09:55:43.395301

"""
from typing import Sequence, Union
from sqlalchemy.dialects.postgresql import UUID
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '666c63edd19d'
down_revision: Union[str, Sequence[str], None] = '71a98fa7ab11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'service_placeholders',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('service_lane_id', UUID(as_uuid=True), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('credits', sa.Integer(), server_default='2'),
        sa.ForeignKeyConstraint(['service_lane_id'], ['services_lanes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('service_placeholders')
