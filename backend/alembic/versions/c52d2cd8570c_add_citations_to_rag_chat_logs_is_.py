"""add_citations_to_rag_chat_logs_is_virtual_to_test_documents

Revision ID: c52d2cd8570c
Revises: 7f9fabe99813
Create Date: 2026-09-01 08:33:14.983184

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c52d2cd8570c'
down_revision: Union[str, Sequence[str], None] = '7f9fabe99813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('test_documents', sa.Column('is_virtual', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('rag_chat_logs', sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('test_documents', 'is_virtual')
    op.drop_column('rag_chat_logs', 'citations')
