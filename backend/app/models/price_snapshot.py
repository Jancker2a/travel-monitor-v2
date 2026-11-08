from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cohort_hash = Column(String(32), ForeignKey("offer_cohorts.cohort_hash", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    total_price_pln = Column(Float, nullable=False)
    price_per_night_per_pax = Column(Float, nullable=False, index=True)
    currency = Column(String(8), default="PLN")
    source = Column(String(32), default="fly_pl")

    # Relationship
    cohort = relationship("OfferCohort", back_populates="snapshots")

    __table_args__ = (
        Index("idx_snapshot_cohort_time", "cohort_hash", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<PriceSnapshot {self.id}: {self.total_price_pln:.0f} PLN ({self.price_per_night_per_pax:.0f}/night)>"

