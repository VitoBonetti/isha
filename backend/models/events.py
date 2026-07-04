import uuid
from sqlalchemy import Column, String, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Events(Base):
    __tablename__ = 'events'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    event_type = Column(String(50))
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id', ondelete='CASCADE'))
    start_date = Column(Date)
    end_date = Column(Date)

    # relationship
    users = relationship('Users', back_populates='events')
    locations = relationship('Locations', back_populates='events')