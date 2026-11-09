import hashlib
from datetime import date
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


def compute_cohort_hash(
    hotel_id: str,
    checkin_date: date,
    duration_nights: int,
    airport_code: str,
    adults: int = 2,
    board_basis: str = "All Inclusive",
    filter_id: Optional[str] = None,
) -> str:
    """Computes a deterministic SHA256 signature for this package cohort."""
    key = f"{filter_id or ''}|{hotel_id.strip().lower()}|{checkin_date.isoformat()}|{duration_nights}|{airport_code.strip().upper()}|{adults}|{board_basis.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


class OfferCohort(Base):
    __tablename__ = "offer_cohorts"

    cohort_hash = Column(String(32), primary_key=True, index=True)
    filter_id = Column(String(64), nullable=True, index=True)
    hotel_id = Column(String(128), ForeignKey("hotels.hotel_id", ondelete="CASCADE"), nullable=False, index=True)
    destination_code = Column(String(64), nullable=False, index=True)
    checkin_date = Column(Date, nullable=False, index=True)
    checkout_date = Column(Date, nullable=True)
    duration_nights = Column(Integer, nullable=False, index=True)
    airport_code = Column(String(64), nullable=False, index=True)
    board_basis = Column(String(64), default="All Inclusive")
    room_type = Column(String(128), nullable=True)
    adults = Column(Integer, default=2)
    children = Column(Integer, default=0)
    operator = Column(String(64), nullable=True)
    offer_url = Column(String(2048), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    hotel = relationship("Hotel", back_populates="cohorts")
    snapshots = relationship("PriceSnapshot", back_populates="cohort", cascade="all, delete-orphan", order_by="PriceSnapshot.recorded_at")
    watchlists = relationship("WatchlistItem", back_populates="cohort", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_cohort_filter_hotel", "filter_id", "hotel_id"),
        Index("idx_cohort_search", "hotel_id", "checkin_date", "duration_nights", "airport_code"),
    )

    def __repr__(self) -> str:
        return f"<Cohort {self.cohort_hash[:8]} [{self.filter_id}] {self.hotel_id} {self.checkin_date} ({self.duration_nights}n)>"

