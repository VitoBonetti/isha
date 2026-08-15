import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from database import Base


class Assets(Base):
    __tablename__ = 'assets'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_asset_id = Column(UUID(as_uuid=True), ForeignKey('raw_assets.id', ondelete='CASCADE'), nullable=False, unique=True)
    asset_type_id = Column(UUID(as_uuid=True), ForeignKey('asset_types.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(500), nullable=False)
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id', ondelete='CASCADE'), nullable=False)
    service_forecast_id = Column(UUID(as_uuid=True), ForeignKey('services_lanes.id', ondelete='SET NULL'), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey('service_categories.id', ondelete='SET NULL'), nullable=True)
    is_assigned = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    archived_years = Column(ARRAY(Integer), default=list, nullable=True)

    # relationship
    raw_assets = relationship("RawAssets", back_populates="assets")
    asset_types = relationship("AssetTypes", back_populates="assets")
    countries = relationship("Country", back_populates="assets")
    services_lanes = relationship("ServiceLanes", back_populates="assets")
    service_categories = relationship("ServiceCategories", back_populates="assets")