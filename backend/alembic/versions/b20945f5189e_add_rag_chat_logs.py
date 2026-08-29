"""add_rag_chat_logs

Revision ID: b20945f5189e
Revises: 864d645eef2e
Create Date: 2026-08-29 08:20:00.799582

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b20945f5189e'
down_revision: Union[str, Sequence[str], None] = '864d645eef2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rag_chat_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_chat_logs_session_id'), 'rag_chat_logs', ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rag_chat_logs_session_id'), table_name='rag_chat_logs')
    op.drop_table('rag_chat_logs')
