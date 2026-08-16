import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Contacts(Base):
    __tablename__ = 'contacts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)

    # Relationships
    country_mappings = relationship('CountryContacts', back_populates='contact', cascade='all, delete-orphan')
    raw_asset_mappings = relationship('RawAssetContacts', back_populates='contact', cascade='all, delete-orphan')


class CountryContacts(Base):
    __tablename__ = 'country_contacts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id', ondelete='CASCADE'), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)

    is_stakeholder = Column(Boolean, default=False, nullable=False)
    is_developer = Column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint('country_id', 'contact_id', name='uix_country_contact'),)

    # Relationships
    country = relationship('Country', back_populates='contacts')  # Adjust 'Country' if your model is named differently
    contact = relationship('Contacts', back_populates='country_mappings')


class RawAssetContacts(Base):
    __tablename__ = 'raw_asset_contacts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_asset_id = Column(UUID(as_uuid=True), ForeignKey('raw_assets.id', ondelete='CASCADE'), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)

    is_stakeholder = Column(Boolean, default=False, nullable=False)
    is_developer = Column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint('raw_asset_id', 'contact_id', name='uix_raw_asset_contact'),)

    # Relationships
    raw_asset = relationship('RawAssets', back_populates='contacts')
    contact = relationship('Contacts', back_populates='raw_asset_mappings')

