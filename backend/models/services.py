import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class ServiceLaneGoals(Base):
    __tablename__ = 'service_lane_goals'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_lane_id = Column(UUID(as_uuid=True), ForeignKey('services_lanes.id', ondelete='CASCADE'), nullable=False)
    year = Column(Integer, nullable=False)
    target_goal = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint('service_lane_id', 'year', name='uix_lane_year'),)
    service_lane = relationship('ServiceLanes', back_populates='goals')


class ServiceCategoryGoals(Base):
    __tablename__ = 'service_category_goals'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey('service_categories.id', ondelete='CASCADE'), nullable=False)
    year = Column(Integer, nullable=False)
    target_goal = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint('category_id', 'year', name='uix_category_year'),)
    category = relationship('ServiceCategories', back_populates='goals')


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
    auto_provision_workspace = Column(Boolean, default=False)
    intro_email_template = Column(String, nullable=True)
    final_email_template = Column(String, nullable=True)

    # relationship
    service_categories = relationship('ServiceCategories', back_populates='services_lanes')
    raw_assets = relationship("RawAssets", back_populates="services_lanes")
    assets = relationship("Assets", back_populates="services_lanes")
    tests = relationship("Tests", back_populates="services_lanes")
    services_placeholders = relationship("ServicePlaceholders", back_populates="services_lane")
    goals = relationship('ServiceLaneGoals', back_populates='service_lane', cascade="all, delete")


class ServiceCategories(Base):
    __tablename__ = 'service_categories'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    service_lane_id = Column(UUID, ForeignKey('services_lanes.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), unique=True, nullable=False)

    # relationship
    services_lanes = relationship('ServiceLanes', back_populates='service_categories')
    raw_assets = relationship("RawAssets", back_populates="service_categories")
    assets = relationship("Assets", back_populates="service_categories")
    tests = relationship("Tests", back_populates="service_categories")
    goals = relationship('ServiceCategoryGoals', back_populates='category', cascade="all, delete")


class ServicePlaceholders(Base):
    __tablename__ = 'service_placeholders'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    service_lane_id = Column(UUID(as_uuid=True), ForeignKey('services_lanes.id', ondelete='CASCADE'), nullable=False)
    year = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    credits = Column(Integer, default=2)

    services_lane = relationship('ServiceLanes', back_populates='service_placeholders')