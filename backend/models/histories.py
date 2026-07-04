import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
from utils.timeaware import aware_utcnow


class AssetHistory(Base):
    __tablename__ = 'asset_history'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_asset_id = Column(UUID(as_uuid=True), ForeignKey('raw_assets.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=aware_utcnow)

    # Relationships
    raw_assets = relationship("RawAssets", back_populates="asset_history")
    users = relationship("Users")


class TestHistory(Base):
    __tablename__ = 'test_history'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=aware_utcnow)

    # Relationships
    tests = relationship("Tests", back_populates="test_history")
    users = relationship("Users")