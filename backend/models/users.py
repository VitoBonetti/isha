import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
from utils.timeaware import aware_utcnow


class Users(Base):
    __tablename__ = "users"

    # Using uuid4 to automatically generate the gen_random_uuid() equivalent in Python
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id = Column(String(255), unique=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    avatar_url = Column(String(500))
    role = Column(String(50), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete='SET NULL'), nullable=True)
    base_capacity = Column(Float, default=1.0)
    start_week = Column(Integer, default=1)
    start_year = Column(Integer, default=2024)
    end_week = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)

    # relationship
    locations = relationship("Locations", back_populates="users")
    assignments = relationship("Assignments", back_populates="users")
    events = relationship("Events", back_populates="users")
    notifications = relationship("Notifications", back_populates="users")


class ApiKeys(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    prefix = Column(String(50), nullable=False)
    hashed_key = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=aware_utcnow)
    is_active = Column(Boolean, default=True)