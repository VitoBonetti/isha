import uuid
import enum
from sqlalchemy import Column, String, Integer, ForeignKey, REAL, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class TestStages(enum.Enum):
    NOT_PLANNED = "Not Planned"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    STOPPED = "Stopped"
    DELETED = "Deleted"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"


class Tests(Base):
    __tablename__ = 'tests'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    service_lane_id = Column(UUID(as_uuid=True), ForeignKey('services_lanes.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey('service_categories.id', ondelete='SET NULL'), nullable=True)
    credits_per_week = Column(REAL)
    duration_weeks = Column(REAL)
    start_week = Column(Integer)
    start_year = Column(Integer)
    stages = Column(Enum(TestStages), default=TestStages.NOT_PLANNED, nullable=False)

    # relationship
    services_lanes = relationship("ServiceLanes", back_populates="tests")
    service_categories = relationship("ServiceCategories", back_populates="tests")
    assignments = relationship("Assignments", back_populates="tests")
    test_history = relationship("TestHistory", back_populates="tests", cascade="all, delete-orphan")
    secret_notes = relationship("SecretNotes", back_populates="tests")


class TestAssets(Base):
    __tablename__ = 'test_assets'
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), primary_key=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id', ondelete='CASCADE'), primary_key=True)



class Assignments(Base):
    __tablename__ = 'assignments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    week_number = Column(Integer)
    year = Column(Integer)
    allocated_credits = Column(REAL)

    # relationship
    tests = relationship("Tests", back_populates="assignments")
    users = relationship("Users", back_populates="assignments")