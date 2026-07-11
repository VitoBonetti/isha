import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class ServiceLanes(Base):
    __tablename__ = 'services_lanes'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    max_concurrent_per_week = Column(Integer)
    theme_color = Column(String(20), default='#3b82f6')
    default_credits = Column(Numeric(4, 1), default=2.0)
    default_duration_weeks = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=99)

    # relationship
    service_categories = relationship('ServiceCategories', back_populates='services_lanes')
    raw_assets = relationship("RawAssets", back_populates="services_lanes")
    assets = relationship("Assets", back_populates="services_lanes")
    tests = relationship("Tests", back_populates="services_lanes")


class ServiceCategories(Base):
    __tablename__ = 'service_categories'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    service_lane_id = Column(UUID, ForeignKey('services_lanes.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), unique=True, nullable=False)
    target_goal = Column(Integer, default=0)

    # relationship
    services_lanes = relationship('ServiceLanes', back_populates='service_categories')
    raw_assets = relationship("RawAssets", back_populates="service_categories")
    assets = relationship("Assets", back_populates="service_categories")
    tests = relationship("Tests", back_populates="service_categories")