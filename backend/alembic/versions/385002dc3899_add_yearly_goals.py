"""add yearly goals

Revision ID: 385002dc3899
Revises: 123614b49e12
Create Date: 2026-08-16 10:24:19.810276

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision: str = '385002dc3899'
down_revision: Union[str, Sequence[str], None] = '123614b49e12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('service_lane_goals',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                    sa.Column('service_lane_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('services_lanes.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('year', sa.Integer(), nullable=False),
                    sa.Column('target_goal', sa.Integer(), server_default='0'),
                    sa.UniqueConstraint('service_lane_id', 'year', name='uix_lane_year')
                    )

    op.create_table('service_category_goals',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                    sa.Column('category_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('service_categories.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('year', sa.Integer(), nullable=False),
                    sa.Column('target_goal', sa.Integer(), server_default='0'),
                    sa.UniqueConstraint('category_id', 'year', name='uix_category_year')
                    )

    # 2. Migrate existing goals to 2026 so you don't lose data!
    op.execute("""
            INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal)
            SELECT gen_random_uuid(), id, 2026, target_goal FROM services_lanes WHERE target_goal > 0
        """)
    op.execute("""
            INSERT INTO service_category_goals (id, category_id, year, target_goal)
            SELECT gen_random_uuid(), id, 2026, target_goal FROM service_categories WHERE target_goal > 0
        """)

    # 3. Drop old flat columns
    op.drop_column('services_lanes', 'target_goal')
    op.drop_column('service_categories', 'target_goal')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('service_categories', sa.Column('target_goal', sa.Integer(), server_default='0'))
    op.add_column('services_lanes', sa.Column('target_goal', sa.Integer(), server_default='0'))

    op.drop_table('service_category_goals')
    op.drop_table('service_lane_goals')
