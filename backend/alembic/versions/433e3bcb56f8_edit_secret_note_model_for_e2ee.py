"""edit secret note model for e2ee

Revision ID: 433e3bcb56f8
Revises: 155a181c840b
Create Date: 2026-08-23 19:46:00.803595

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '433e3bcb56f8'
down_revision: Union[str, Sequence[str], None] = '155a181c840b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('public_key', sa.Text(), nullable=True))
    op.alter_column('secret_notes', 'encrypted_note', new_column_name='encrypted_data')
    op.create_table(
        'secret_note_access',
        sa.Column('test_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['test_id'], ['secret_notes.test_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('test_id', 'user_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('secret_note_access')
    op.alter_column('secret_notes', 'encrypted_data', new_column_name='encrypted_note')
    op.drop_column('users', 'public_key')
