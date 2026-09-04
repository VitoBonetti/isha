"""make test_id nullable to tests_documents and documents chuncks

Revision ID: 76f10d71b9c7
Revises: 57e4ee758197
Create Date: 2026-09-04 15:05:33.023509

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76f10d71b9c7'
down_revision: Union[str, Sequence[str], None] = '57e4ee758197'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('test_documents', 'test_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column('document_chunks', 'test_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('document_chunks', 'test_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column('test_documents', 'test_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
