"""Add test_ritms and ritms_and_tests tables

Revision ID: 9c5451b534c4
Revises: 2f450a1d775b
Create Date: 2026-09-26 20:52:24.109556

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c5451b534c4'
down_revision: Union[str, Sequence[str], None] = '2f450a1d775b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'test_ritms',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('stage', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('requested_by', sa.String(), nullable=False),
        sa.Column('company', sa.String(), nullable=False),
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('onetrust_id', sa.String(), nullable=True),
        sa.Column('name_app', sa.String(), nullable=False),
        sa.Column('estimated_date', sa.Date(), nullable=True),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('closed', sa.DateTime(), nullable=True),
        sa.Column('closed_by', sa.String(), nullable=True),
        sa.Column('service_requested', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )

    op.create_table(
        'ritms_and_tests',
        sa.Column('ritm_id', sa.String(), nullable=False),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['ritm_id'], ['test_ritms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_id'], ['tests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('ritm_id', 'test_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ritms_and_tests')
    op.drop_table('test_ritms')
