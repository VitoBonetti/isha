"""drop_and_recreate_snitcher

Revision ID: 8361f2095058
Revises: 542537b248f5
Create Date: 2026-09-27 21:51:22.436190

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8361f2095058'
down_revision: Union[str, Sequence[str], None] = '542537b248f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('snitcher')

    op.create_table(
        'snitcher',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period', sa.String(), nullable=False),
        sa.Column('newly_added', sa.Integer(), nullable=True),
        sa.Column('start_new_open', sa.Integer(), nullable=True),
        sa.Column('start_waiting_to_retest', sa.Integer(), nullable=True),
        sa.Column('start_unable_to_retest', sa.Integer(), nullable=True),
        sa.Column('start_parked', sa.Integer(), nullable=True),
        sa.Column('end_new_open', sa.Integer(), nullable=True),
        sa.Column('end_waiting_to_retest', sa.Integer(), nullable=True),
        sa.Column('end_unable_to_retest', sa.Integer(), nullable=True),
        sa.Column('end_parked', sa.Integer(), nullable=True),
        sa.Column('solved', sa.Integer(), nullable=True),
        sa.Column('parked', sa.Integer(), nullable=True),
        sa.Column('unparked', sa.Integer(), nullable=True),
        sa.Column('unable_to_waiting', sa.Integer(), nullable=True),
        sa.Column('devoteam_waiting_to_retest', sa.Integer(), nullable=True),
        sa.Column('devoteam_unable_to_retest', sa.Integer(), nullable=True),
        sa.Column('am_utr', sa.Integer(), nullable=True),
        sa.Column('am_nf', sa.Integer(), nullable=True),
        sa.Column('am_c', sa.Integer(), nullable=True),
        sa.Column('ipm_utr', sa.Integer(), nullable=True),
        sa.Column('ipm_nf', sa.Integer(), nullable=True),
        sa.Column('ipm_c', sa.Integer(), nullable=True),
        sa.Column('rm_utr', sa.Integer(), nullable=True),
        sa.Column('rm_nf', sa.Integer(), nullable=True),
        sa.Column('rm_c', sa.Integer(), nullable=True),
        sa.Column('ttal_utr', sa.Integer(), nullable=True),
        sa.Column('ttal_nf', sa.Integer(), nullable=True),
        sa.Column('ttal_c', sa.Integer(), nullable=True),
        sa.Column('vb_utr', sa.Integer(), nullable=True),
        sa.Column('vb_nf', sa.Integer(), nullable=True),
        sa.Column('vb_c', sa.Integer(), nullable=True),
        sa.Column('fe_utr', sa.Integer(), nullable=True),
        sa.Column('fe_nf', sa.Integer(), nullable=True),
        sa.Column('fe_c', sa.Integer(), nullable=True),
        sa.Column('et_utr', sa.Integer(), nullable=True),
        sa.Column('et_nf', sa.Integer(), nullable=True),
        sa.Column('et_c', sa.Integer(), nullable=True),
        sa.Column('ga_utr', sa.Integer(), nullable=True),
        sa.Column('ga_nf', sa.Integer(), nullable=True),
        sa.Column('ga_c', sa.Integer(), nullable=True),
        sa.Column('hp_utr', sa.Integer(), nullable=True),
        sa.Column('hp_nf', sa.Integer(), nullable=True),
        sa.Column('hp_c', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('snitcher')
