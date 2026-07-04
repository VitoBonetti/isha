import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
from utils.timeaware import aware_utcnow


class Notifications(Base):
    __tablename__ = 'notifications'

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=aware_utcnow)
    is_read = Column(Boolean, default=False)

    # relationship
    users = relationship("Users", back_populates="notifications")