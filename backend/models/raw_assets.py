import uuid
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base
from utils.timeaware import aware_utcnow


class AssetTypes(Base):
    __tablename__ = 'asset_types'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)

    # relashionship
    raw_assets = relationship("RawAssets", back_populates="asset_types")
    assets = relationship("Assets", back_populates="asset_types")



class RawAssets(Base):
    __tablename__ = 'raw_assets'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_type_id = Column(UUID(as_uuid=True), ForeignKey('asset_types.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    business_critical = Column(Integer)
    confidentiality_rating = Column(Integer)
    integrity_rating = Column(Integer)
    availability_rating = Column(Integer)
    facing_internet = Column(Boolean, default=False)
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id', ondelete='CASCADE'), nullable=False)
    service_forecast_id = Column(UUID(as_uuid=True), ForeignKey('services_lanes.id', ondelete='SET NULL'), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey('service_categories.id', ondelete='SET NULL'), nullable=True)
    create_date = Column(DateTime(timezone=True), default=aware_utcnow)
    update_date = Column(DateTime(timezone=True), nullable=True)
    duplicate_allowed = Column(Boolean, default=False)

    # relashionship
    asset_types = relationship("AssetTypes", back_populates="raw_assets")
    countries = relationship("Country", back_populates="raw_assets")
    services_lanes = relationship("ServiceLanes", back_populates="raw_assets")
    service_categories = relationship("ServiceCategories", back_populates="raw_assets")
    assets = relationship("Assets", back_populates="raw_assets")
    asset_history = relationship("AssetHistory", back_populates="raw_assets", cascade="all, delete-orphan")
    snow_metadata = relationship("RawAssetsSnowMetadata", back_populates="raw_asset", uselist=False,
                                 cascade="all, delete-orphan")


class RawAssetsSnowMetadata(Base):
    __tablename__ = 'raw_assets_snow_metadata'

    correlation_id = Column(UUID(as_uuid=True), ForeignKey('raw_assets.id', ondelete='CASCADE'), primary_key=True)
    last_snow_sync = Column(DateTime(timezone=True), default=aware_utcnow, onupdate=aware_utcnow)
    snow_data = Column(JSONB, nullable=True)

    # relashionship
    raw_asset = relationship("RawAssets", back_populates="snow_metadata")
