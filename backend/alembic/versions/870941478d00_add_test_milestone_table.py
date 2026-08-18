"""add test milestone table

Revision ID: 870941478d00
Revises: 475b762a8a10
Create Date: 2026-08-17 21:59:01.921892

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '870941478d00'
down_revision: Union[str, Sequence[str], None] = '475b762a8a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('test_milestones',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
                    sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('step_name', sa.String(), nullable=False),
                    sa.Column('is_completed', sa.Boolean(), server_default='false', nullable=False),
                    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE'),
                    sa.UniqueConstraint('test_id', 'step_name', name='uq_test_milestone_step')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('test_milestones')
