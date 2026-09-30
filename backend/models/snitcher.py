import uuid
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SnitcherMetric(Base):
    __tablename__ = 'snitcher'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period = Column(String, nullable=False)
    newly_added = Column(Integer, default=0)
    start_new_open = Column(Integer, default=0)
    start_waiting_to_retest = Column(Integer, default=0)
    start_unable_to_retest = Column(Integer, default=0)
    start_parked = Column(Integer, default=0)
    end_new_open = Column(Integer, default=0)
    end_waiting_to_retest = Column(Integer, default=0)
    end_unable_to_retest = Column(Integer, default=0)
    end_parked = Column(Integer, default=0)
    solved = Column(Integer, default=0)
    parked = Column(Integer, default=0)
    unparked = Column(Integer, default=0)
    unable_to_waiting = Column(Integer, default=0)
    devoteam_waiting_to_retest = Column(Integer, default=0)
    devoteam_unable_to_retest = Column(Integer, default=0)
    total_unable_to_retest = Column(Integer, default=0)
    total_not_fixed_reopened = Column(Integer, default=0)
    total_closed = Column(Integer, default=0)

    am_utr = Column(Integer, default=0)
    am_nf = Column(Integer, default=0)
    am_c = Column(Integer, default=0)

    ipm_utr = Column(Integer, default=0)
    ipm_nf = Column(Integer, default=0)
    ipm_c = Column(Integer, default=0)

    rm_utr = Column(Integer, default=0)
    rm_nf = Column(Integer, default=0)
    rm_c = Column(Integer, default=0)

    ttal_utr = Column(Integer, default=0)
    ttal_nf = Column(Integer, default=0)
    ttal_c = Column(Integer, default=0)

    vb_utr = Column(Integer, default=0)
    vb_nf = Column(Integer, default=0)
    vb_c = Column(Integer, default=0)

    fe_utr = Column(Integer, default=0)
    fe_nf = Column(Integer, default=0)
    fe_c = Column(Integer, default=0)

    et_utr = Column(Integer, default=0)
    et_nf = Column(Integer, default=0)
    et_c = Column(Integer, default=0)

    ga_utr = Column(Integer, default=0)
    ga_nf = Column(Integer, default=0)
    ga_c = Column(Integer, default=0)

    hp_utr = Column(Integer, default=0)
    hp_nf = Column(Integer, default=0)
    hp_c = Column(Integer, default=0)