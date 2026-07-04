import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Assets(Base):
    __tablename__ = 'assets'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_asset_id = Column(UUID(as_uuid=True), ForeignKey('raw_assets.id'), nullable=False, unique=True)
    asset_type_id = Column(UUID(as_uuid=True), ForeignKey('asset_types.id'), nullable=False)
    name = Column(String(500), nullable=False)
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id'), nullable=False)
    service_forecast_id = Column(UUID(as_uuid=True), ForeignKey('services_lanes.id'), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey('service_categories.id'), nullable=True)
    is_assigned = Column(Boolean, default=False)

    # relationship
    raw_assets = relationship("RawAssets", back_populates="assets")
    asset_types = relationship("AssetTypes", back_populates="assets")
    countries = relationship("Country", back_populates="assets")
    services_lanes = relationship("ServiceLanes", back_populates="assets")
    service_categories = relationship("ServiceCategories", back_populates="assets")

