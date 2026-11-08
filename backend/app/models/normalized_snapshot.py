from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class NormalizedPriceSnapshot(Base):
    """
    Dedicated store for normalized benchmark prices (1 adult, 8 nights).
    Separates standard normalized time series from raw cohort-specific data.
    """
    __tablename__ = "normalized_price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(String(128), ForeignKey("hotels.hotel_id", ondelete="CASCADE"), nullable=False, index=True)
    destination_code = Column(String(64), nullable=True, index=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Standardized metrics
    normalized_price_1p_8n = Column(Float, nullable=False, index=True)  # Standard benchmark: 1 pax, 8 nights
    pure_hotel_night_rate = Column(Float, nullable=False)               # H (daily pure hotel room rate)
    flight_estimate_seat = Column(Float, nullable=False)                # F (estimated flight benchmark)

    # Provenance tracking
    source_type = Column(String(64), default="renormalized_v1_cohort", index=True)  # 'renormalized_v1_cohort' or 'crawler_1p_8n'
    source_cohort_hash = Column(String(64), nullable=True)
    is_crawler_standard = Column(Boolean, default=False)

    # Relationship
    hotel = relationship("Hotel", backref="normalized_snapshots")

    __table_args__ = (
        Index("idx_norm_hotel_time", "hotel_id", "recorded_at"),
        Index("idx_norm_dest_price", "destination_code", "normalized_price_1p_8n"),
    )

    def __repr__(self) -> str:
        return f"<NormalizedSnapshot {self.hotel_id}: {self.normalized_price_1p_8n:.0f} zł (1p/8n)>"

