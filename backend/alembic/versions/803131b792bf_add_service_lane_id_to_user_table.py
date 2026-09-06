"""add service_lane_id to user table

Revision ID: 803131b792bf
Revises: 4102773db8ab
Create Date: 2026-09-05 21:13:04.812816

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '803131b792bf'
down_revision: Union[str, Sequence[str], None] = '4102773db8ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('service_lane_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_users_service_lane_id',
        source_table='users',
        referent_table='services_lanes',
        local_cols=['service_lane_id'],
        remote_cols=['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_users_service_lane_id', 'users', type_='foreignkey')
    op.drop_column('users', 'service_lane_id')
