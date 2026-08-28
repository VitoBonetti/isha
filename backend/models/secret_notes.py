from sqlalchemy import Column, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
from utils.timeaware import aware_utcnow


class SecretNotes(Base):
    __tablename__ = 'secret_notes'

    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), primary_key=True)
    encrypted_data = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=aware_utcnow)

    accesses = relationship('SecretNoteAccess', back_populates='note', cascade='all, delete-orphan')
    tests = relationship('Tests', back_populates='secret_notes')


class SecretNoteAccess(Base):
    __tablename__ = 'secret_note_access'
    test_id = Column(UUID(as_uuid=True), ForeignKey('secret_notes.test_id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    # The AES key, encrypted using this specific user's RSA Public Key
    encrypted_key = Column(Text, nullable=False)

    note = relationship('SecretNotes', back_populates='accesses')