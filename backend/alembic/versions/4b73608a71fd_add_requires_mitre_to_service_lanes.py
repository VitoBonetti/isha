"""add_requires_mitre_to_service_lanes

Revision ID: 4b73608a71fd
Revises: 1b08a4a4a27e
Create Date: 2026-08-25 20:43:30.228206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b73608a71fd'
down_revision: Union[str, Sequence[str], None] = '1b08a4a4a27e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('services_lanes', sa.Column('requires_mitre', sa.Boolean(), default=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('services_lanes', 'requires_mitre')
