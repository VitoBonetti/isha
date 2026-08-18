"""add_final_email_template

Revision ID: c4446968844e
Revises: 7fea715dde56
Create Date: 2026-08-18 17:20:47.173152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4446968844e'
down_revision: Union[str, Sequence[str], None] = '7fea715dde56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('services_lanes', sa.Column('final_email_template', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('services_lanes', 'final_email_template')
