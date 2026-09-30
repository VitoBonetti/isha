"""add final total to snitcher

Revision ID: 8bbfd8adbefc
Revises: 8361f2095058
Create Date: 2026-09-28 14:49:06.275836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bbfd8adbefc'
down_revision: Union[str, Sequence[str], None] = '8361f2095058'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('snitcher', sa.Column('total_unable_to_retest', sa.Integer(), server_default='0'))
    op.add_column('snitcher', sa.Column('total_not_fixed_reopened', sa.Integer(), server_default='0'))
    op.add_column('snitcher', sa.Column('total_closed', sa.Integer(), server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('snitcher', 'total_closed')
    op.drop_column('snitcher', 'total_not_fixed_reopened')
    op.drop_column('snitcher', 'total_unable_to_retest')
