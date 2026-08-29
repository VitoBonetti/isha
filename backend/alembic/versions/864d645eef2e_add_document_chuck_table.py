"""add_document_chuck_table

Revision ID: 864d645eef2e
Revises: d74094767739
Create Date: 2026-08-28 22:07:38.953141

"""
from typing import Sequence, Union
from pgvector.sqlalchemy import Vector
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '864d645eef2e'
down_revision: Union[str, Sequence[str], None] = 'd74094767739'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('document_chunks',
                    sa.Column('id', sa.UUID(), nullable=False),
                    sa.Column('document_id', sa.UUID(), nullable=False),
                    sa.Column('test_id', sa.UUID(), nullable=False),
                    sa.Column('chunk_index', sa.Integer(), nullable=False),
                    sa.Column('text_content', sa.Text(), nullable=False),
                    sa.Column('embedding', Vector(dim=768), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
                    sa.ForeignKeyConstraint(['document_id'], ['test_documents.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.execute('CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('document_chunks')
