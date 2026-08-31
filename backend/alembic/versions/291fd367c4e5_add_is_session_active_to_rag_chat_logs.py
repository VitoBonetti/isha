"""add_is_session_active_to_rag_chat_logs

Revision ID: 291fd367c4e5
Revises: eafcf96afb8a
Create Date: 2026-08-30 21:11:48.165481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '291fd367c4e5'
down_revision: Union[str, Sequence[str], None] = 'eafcf96afb8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rag_chat_logs', sa.Column('is_session_active', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rag_chat_logs', 'is_session_active')
