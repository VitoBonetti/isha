import uuid
import enum
from sqlalchemy import Column, String, Integer, ForeignKey, REAL, Enum, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from database import Base
from utils.timeaware import aware_utcnow


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
    is_tentative = Column(Boolean, default=False)
    drive_folder_id = Column(String(255), nullable=True)
    drive_folder_url = Column(String(1000), nullable=True)
    kiss24 = Column(UUID(as_uuid=True), nullable=True)

    # relationship
    services_lanes = relationship("ServiceLanes", back_populates="tests")
    service_categories = relationship("ServiceCategories", back_populates="tests")
    assignments = relationship("Assignments", back_populates="tests")
    test_history = relationship("TestHistory", back_populates="tests", cascade="all, delete-orphan")
    secret_notes = relationship("SecretNotes", back_populates="tests")
    documents = relationship("TestDocuments", back_populates="tests", cascade="all, delete-orphan")
    document_chunks = relationship("DocumentChunk", back_populates="tests")
    rag_chat_logs = relationship("RagChatLogs", back_populates="tests")


class TestDocuments(Base):
    __tablename__ = 'test_documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False)
    drive_file_id = Column(String(255), unique=True, nullable=False)
    file_name = Column(String(500), nullable=False)
    mime_type = Column(String(255), nullable=True)
    file_url = Column(String(1000), nullable=True)
    doc_type = Column(String(50), default='MANUAL_UPLOAD', nullable=False)
    last_modified = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), default=aware_utcnow)
    is_virtual = Column(Boolean, default=False, nullable=False)

    # relationships
    tests = relationship("Tests", back_populates="documents")
    document_chunks = relationship("DocumentChunk", back_populates="documents")


class DocumentChunk(Base):
    __tablename__ = 'document_chunks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('test_documents.id', ondelete='CASCADE'), nullable=False)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)  # 768 is the standard dimension output for gemini-embedding-2
    created_at = Column(DateTime(timezone=True), default=aware_utcnow)


    documents = relationship("TestDocuments", back_populates="document_chunks")
    tests = relationship("Tests", back_populates="document_chunks")


class RagChatLogs(Base):
    __tablename__ = 'rag_chat_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=True) # Nullable for global searches
    asset_id = Column(UUID(as_uuid=True), ForeignKey('assets.id', ondelete='CASCADE'), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=aware_utcnow)
    is_session_active = Column(Boolean, nullable=False, default=True)
    user_feedback = Column(Boolean, nullable=True)
    citations = Column(JSONB, nullable=True, default=list)

    # Optional relationships
    users = relationship("Users", back_populates="rag_chat_logs")
    tests = relationship("Tests", back_populates="rag_chat_logs")


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


class TestAnalysis(Base):
    __tablename__ = "test_analyses"

    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), primary_key=True)
    status = Column(String, nullable=False) # 'PENDING', 'COMPLETED', 'FAILED'
    analysis_text = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=aware_utcnow, onupdate=aware_utcnow)


class TestRequirement(Base):
    __tablename__ = "test_requirements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False)
    description = Column(String, nullable=False)
    is_completed = Column(Boolean, default=False)


class TestMilestone(Base):
    __tablename__ = "test_milestones"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False)
    step_name = Column(String, nullable=False)
    is_completed = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint('test_id', 'step_name', name='uq_test_milestone_step'),
    )