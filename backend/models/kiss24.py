import uuid
from sqlalchemy import Column, String, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


# Association Table for the Many-to-Many relationship
kiss24_vuln_context_association = Table(
    'kiss24_vuln_context_association',
    Base.metadata,
    Column('vuln_id', UUID(as_uuid=True), ForeignKey('kiss24_vuln_types.id', ondelete='CASCADE'), primary_key=True),
    Column('context_id', UUID(as_uuid=True), ForeignKey('kiss24_context.id', ondelete='CASCADE'), primary_key=True)
)


class Kiss24ContextType(Base):
    __tablename__ = "kiss24_context"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)

    # Relationship through the association table
    kiss24_vuln_types = relationship(
        "Kiss24VulnTypes",
        secondary=kiss24_vuln_context_association,
        back_populates="contexts"
    )


class Kiss24VulnTypes(Base):
    __tablename__ = "kiss24_vuln_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)

    # Relationship through the association table
    contexts = relationship(
        "Kiss24ContextType",
        secondary=kiss24_vuln_context_association,
        back_populates="kiss24_vuln_types"
    )