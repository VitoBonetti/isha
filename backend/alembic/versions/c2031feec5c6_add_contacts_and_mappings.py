"""add contacts and mappings

Revision ID: c2031feec5c6
Revises: 385002dc3899
Create Date: 2026-08-16 13:02:56.345196

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import uuid
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2031feec5c6'
down_revision: Union[str, Sequence[str], None] = '385002dc3899'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Central Contacts Table
    op.create_table('contacts',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                    sa.Column('email', sa.String(255), unique=True, nullable=False),
                    sa.Column('full_name', sa.String(255), nullable=True)
                    )

    # 2. Country Mapping Table
    op.create_table('country_contacts',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                    sa.Column('country_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('countries.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('contact_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('is_stakeholder', sa.Boolean(), server_default='false', nullable=False),
                    sa.Column('is_developer', sa.Boolean(), server_default='false', nullable=False),
                    sa.UniqueConstraint('country_id', 'contact_id', name='uix_country_contact')
                    )

    # 3. Raw Asset Mapping Table
    op.create_table('raw_asset_contacts',
                    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                    sa.Column('raw_asset_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('raw_assets.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('contact_id', postgresql.UUID(as_uuid=True),
                              sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('is_stakeholder', sa.Boolean(), server_default='false', nullable=False),
                    sa.Column('is_developer', sa.Boolean(), server_default='false', nullable=False),
                    sa.UniqueConstraint('raw_asset_id', 'contact_id', name='uix_raw_asset_contact')
                    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('raw_asset_contacts')
    op.drop_table('country_contacts')
    op.drop_table('contacts')
