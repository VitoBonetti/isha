"""add test analysis table

Revision ID: 20b58a3ea495
Revises: c2031feec5c6
Create Date: 2026-08-17 16:13:15.057071

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20b58a3ea495'
down_revision: Union[str, Sequence[str], None] = 'c2031feec5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('test_analyses',
                    sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('analysis_text', sa.Text(), nullable=True),
                    sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
                    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('test_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('test_analyses')
