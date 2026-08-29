"""add_doc_type_to_test_documents

Revision ID: eafcf96afb8a
Revises: 5b8b5632d9bc
Create Date: 2026-08-29 17:41:58.713890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eafcf96afb8a'
down_revision: Union[str, Sequence[str], None] = '5b8b5632d9bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('test_documents', sa.Column('doc_type', sa.String(length=50), server_default='MANUAL_UPLOAD', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('test_documents', 'doc_type')
