"""Add Drive integration fields and TestDocuments table

Revision ID: dfdee94ac816
Revises: d651d436369f
Create Date: 2026-07-23 20:21:05.013880

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'dfdee94ac816'
down_revision: Union[str, Sequence[str], None] = 'd651d436369f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Drive columns to the existing 'tests' table
    op.add_column('tests', sa.Column('drive_folder_id', sa.String(length=255), nullable=True))
    op.add_column('tests', sa.Column('drive_folder_url', sa.String(length=1000), nullable=True))

    # 2. Create the new 'test_documents' table
    op.create_table('test_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('drive_file_id', sa.String(length=255), nullable=False),
        sa.Column('file_name', sa.String(length=500), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=True),
        sa.Column('file_url', sa.String(length=1000), nullable=True),
        sa.Column('last_modified', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('drive_file_id')
    )


def downgrade() -> None:
    # 1. Drop the table
    op.drop_table('test_documents')

    # 2. Drop the columns
    op.drop_column('tests', 'drive_folder_url')
    op.drop_column('tests', 'drive_folder_id')
