"""add_kiss24_model_context_and_vuln_types

Revision ID: 1b3fdb5ccbfc
Revises: 6f4564eab385
Create Date: 2026-08-21 14:57:07.932541

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b3fdb5ccbfc'
down_revision: Union[str, Sequence[str], None] = '6f4564eab385'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create Contexts
    op.create_table('kiss24_context',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
                    sa.Column('name', sa.String(), nullable=False)
                    )

    # 2. Create Vuln Types (No context_id here)
    op.create_table('kiss24_vuln_types',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
                    sa.Column('name', sa.String(), nullable=False)
                    )

    # 3. Create the Association Table bridging them
    op.create_table('kiss24_vuln_context_association',
                    sa.Column('vuln_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('kiss24_vuln_types.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('context_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('kiss24_context.id', ondelete='CASCADE'), primary_key=True)
                    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('kiss24_vuln_context_association')
    op.drop_table('kiss24_vuln_types')
    op.drop_table('kiss24_context')
