"""add_user_feedback_to_rag_chat_logs

Revision ID: 7f9fabe99813
Revises: 291fd367c4e5
Create Date: 2026-08-31 16:05:32.514195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f9fabe99813'
down_revision: Union[str, Sequence[str], None] = '291fd367c4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rag_chat_logs', sa.Column('user_feedback', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rag_chat_logs', 'user_feedback')
