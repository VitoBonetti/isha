"""Add auto_provision_workspace to services_lanes

Revision ID: d3417f5c2c3a
Revises: dfdee94ac816
Create Date: 2026-07-23 22:34:39.916139

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3417f5c2c3a'
down_revision: Union[str, Sequence[str], None] = 'dfdee94ac816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('services_lanes', sa.Column('auto_provision_workspace', sa.Boolean(), server_default='false', nullable=False))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('services_lanes', 'auto_provision_workspace')
