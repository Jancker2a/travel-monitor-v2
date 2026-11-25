from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlists"

    watch_id = Column(String(32), primary_key=True)
    user_chat_id = Column(String(64), nullable=False, index=True)
    cohort_hash = Column(String(32), ForeignKey("offer_cohorts.cohort_hash", ondelete="CASCADE"), nullable=False, index=True)
    target_price_pln = Column(Float, nullable=True)
    notify_any_drop = Column(Boolean, default=True)
    alert_threshold_pct = Column(Float, nullable=True, default=5.0)
    min_deal_score = Column(Integer, nullable=True, default=None)
    min_days_to_dep = Column(Integer, nullable=True, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_notified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    cohort = relationship("OfferCohort", back_populates="watchlists")

    def __repr__(self) -> str:
        return f"<Watchlist {self.watch_id}: User {self.user_chat_id} -> Cohort {self.cohort_hash[:8]}>"

