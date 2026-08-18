"""add test requirements table

Revision ID: 475b762a8a10
Revises: 20b58a3ea495
Create Date: 2026-08-17 21:33:47.856546

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '475b762a8a10'
down_revision: Union[str, Sequence[str], None] = '20b58a3ea495'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('test_requirements',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
                    sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('description', sa.String(), nullable=False),
                    sa.Column('is_completed', sa.Boolean(), server_default='false', nullable=False),
                    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE')
                    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('test_requirements')
