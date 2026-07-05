import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Locations(Base):
    __tablename__ = 'locations'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)

    # relashionship
    users = relationship('Users', back_populates='locations')
    events = relationship('Events', back_populates='locations')


class Region(Base):
    __tablename__ = 'regions'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)

    # relashionship
    countries = relationship("Country", back_populates="regions")


class Country(Base):
    __tablename__ = 'countries'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    region_id = Column(UUID(as_uuid=True), ForeignKey('regions.id', ondelete='CASCADE'), nullable=False)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)

    # relashionship
    regions = relationship("Region", back_populates="countries")
    raw_assets = relationship("RawAssets", back_populates="countries")
    assets = relationship("Assets", back_populates="countries")