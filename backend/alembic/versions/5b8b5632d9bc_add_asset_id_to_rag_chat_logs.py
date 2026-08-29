"""add_asset_id_to_rag_chat_logs

Revision ID: 5b8b5632d9bc
Revises: b20945f5189e
Create Date: 2026-08-29 11:28:21.660595

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b8b5632d9bc'
down_revision: Union[str, Sequence[str], None] = 'b20945f5189e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rag_chat_logs', sa.Column('asset_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rag_chat_logs', 'asset_id')
