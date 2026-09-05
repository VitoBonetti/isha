"""add folder path to test_documents table

Revision ID: 4102773db8ab
Revises: 9a6a4681e75a
Create Date: 2026-09-05 19:14:56.817731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4102773db8ab'
down_revision: Union[str, Sequence[str], None] = '9a6a4681e75a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('test_documents', sa.Column('folder_path', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('test_documents', 'folder_path')
