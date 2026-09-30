"""add snitcher table

Revision ID: 1bed60d12a12
Revises: 928697c28944
Create Date: 2026-09-27 20:54:00.563159

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bed60d12a12'
down_revision: Union[str, Sequence[str], None] = '928697c28944'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'snitcher_',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('period', sa.String(), nullable=False),
        sa.Column('newly_added', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_new_open', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_waiting_to_retest', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_unable_to_retest', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_parked', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('end_new_open', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('end_waiting_to_retest', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('end_unable_to_retest', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('end_parked', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('solved', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('parked', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('unparked', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('unable_to_waiting', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('devoteam_waiting_to_retest', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('devoteam_unable_to_retest', sa.Integer(), nullable=True, server_default='0'),
        # User columns
        sa.Column('am_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('am_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('am_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ipm_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ipm_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ipm_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('rm_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('rm_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('rm_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ttal_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ttal_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ttal_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('vb_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('vb_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('vb_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('fe_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('fe_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('fe_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('et_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('et_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('et_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ga_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ga_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ga_c', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('hp_utr', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('hp_nf', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('hp_c', sa.Integer(), nullable=True, server_default='0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('snitcher')
