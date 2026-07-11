from sqlalchemy import Column, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
from utils.timeaware import aware_utcnow


class SecretNotes(Base):
    __tablename__ = 'secret_notes'

    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), primary_key=True)
    encrypted_note = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=aware_utcnow)

    tests = relationship('Tests', back_populates='secret_notes')