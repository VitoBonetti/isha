"""add_intro_email_template

Revision ID: 7fea715dde56
Revises: 870941478d00
Create Date: 2026-08-18 11:53:34.987716

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fea715dde56'
down_revision: Union[str, Sequence[str], None] = '870941478d00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('services_lanes', sa.Column('intro_email_template', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('services_lanes', 'intro_email_template')
