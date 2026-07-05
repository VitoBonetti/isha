import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


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